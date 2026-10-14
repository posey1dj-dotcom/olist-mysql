"""Read the fixed CSV snapshot and verify it before any database writes."""
import csv
import gzip
import hashlib
import json
from pathlib import Path
from catalog import TABLES, PRIMARY_KEYS, FOREIGN_KEYS, source_columns, convert

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / 'data' / 'clean'
MANIFEST = ROOT / 'data' / 'manifest.json'


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def data_path(table, data_dir=DATA_DIR):
    plain = data_dir / f'{table}.csv'
    return plain if plain.exists() else plain.with_suffix('.csv.gz')


def source_sha256(path):
    digest = hashlib.sha256()
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rb') as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read_rows(table, data_dir=DATA_DIR):
    columns = source_columns(table)
    path = data_path(table, data_dir)
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', encoding='utf-8-sig', newline='') as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != [x.name for x in columns]:
            raise ValueError(f'{table}: CSV header differs from the reviewed schema')
        for line, raw in enumerate(reader, 2):
            if None in raw or None in raw.values():
                raise ValueError(f'{table}: malformed CSV record {line}')
            try:
                yield {col.name: convert(raw[col.name], col) for col in columns}
            except (ValueError, ArithmeticError) as exc:
                raise ValueError(f'{table}, record {line}: {exc}') from exc


def snapshot_manifest(data_dir=DATA_DIR):
    tables = {}
    for name in TABLES:
        file = data_dir / f'{name}.csv'
        tables[name] = {'file': f'data/clean/{name}.csv', 'sha256': sha256(file),
                        'bytes': file.stat().st_size,
                        'rows': sum(1 for _ in read_rows(name, data_dir)),
                        'columns': [x.name for x in source_columns(name)]}
    excluded = {}
    for name in ('fact_orders_wide', 'data_quality_report'):
        file = ROOT / 'analysis' / f'{name}.csv'
        excluded[name] = {'file': f'analysis/{name}.csv', 'sha256': sha256(file),
                          'bytes': file.stat().st_size, 'import_to_mysql': False}
    return {'snapshot_date': '2026-10-14', 'tables': tables, 'not_imported': excluded,
            'preprocess_sha256': sha256(ROOT / 'scripts' / 'olist_preprocess.py')}


def audit(data_dir=DATA_DIR):
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    if set(manifest['tables']) != set(TABLES):
        raise ValueError('Manifest must describe exactly the nine approved tables')
    source_keys = {}
    report = {'tables': {}, 'foreign_keys': {}, 'unmatched_geolocation': {}}
    # Read each file once for its keys and profile, then check referential integrity.
    reference_fields = {t: {PRIMARY_KEYS[t][0]} for t in TABLES}
    for child, field, parent, target in FOREIGN_KEYS:
        reference_fields[parent].add(target)
    references = []
    for table in TABLES:
        path = data_path(table, data_dir)
        expected = manifest['tables'][table]
        if source_sha256(path) != expected['sha256']:
            raise ValueError(f'{table}: source SHA-256 differs from data/manifest.json')
        archive = data_dir / f'{table}.csv.gz'
        if archive.exists() and sha256(archive) != expected['archive_sha256']:
            raise ValueError(f'{table}: compressed archive differs from data/manifest.json')
        rows = list(read_rows(table, data_dir))
        if len(rows) != expected['rows']:
            raise ValueError(f'{table}: source row count differs from manifest')
        keys = [tuple(row[x] for x in PRIMARY_KEYS[table]) for row in rows]
        if len(keys) != len(set(keys)) or any(any(x is None or x == '' for x in key) for key in keys):
            raise ValueError(f'{table}: duplicate or missing primary key')
        source_keys[table] = {field: {row[field] for row in rows} for field in reference_fields[table]}
        report['tables'][table] = {'rows': len(rows), 'source_sha256': expected['sha256'],
            'duplicate_primary_keys': 0,
            'nulls': {col.name: sum(row[col.name] is None for row in rows) for col in source_columns(table)}}
        for child, field, parent, target in FOREIGN_KEYS:
            if child == table and field != 'geo_zip_code_prefix':
                references.append((child, field, parent, target, [row[field] for row in rows]))
        if table in ('customers', 'sellers'):
            field = 'customer_zip_code_prefix' if table == 'customers' else 'seller_zip_code_prefix'
            geo = source_keys['geolocation']['zip_code_prefix']
            unmatched = [row[field] for row in rows if row[field] not in geo]
            report['unmatched_geolocation'][table] = {
                'rows': len(unmatched), 'distinct_prefixes': len(set(unmatched)),
                'handling': 'Original prefix preserved; added geo_zip_code_prefix is SQL NULL'}
    for child, field, parent, target, values in references:
        count = sum(x not in source_keys[parent][target] for x in values)
        report['foreign_keys'][f'{child}.{field} -> {parent}.{target}'] = count
        if count:
            raise ValueError(f'{child}.{field}: {count} orphan records')
    report['total_rows'] = sum(x['rows'] for x in report['tables'].values())
    report['status'] = 'PASS'
    return report


def expected_rows(table, geo_keys, data_dir=DATA_DIR):
    for row in read_rows(table, data_dir):
        if table in ('customers', 'sellers'):
            field = 'customer_zip_code_prefix' if table == 'customers' else 'seller_zip_code_prefix'
            row['geo_zip_code_prefix'] = row[field] if row[field] in geo_keys else None
        yield tuple(row[col.name] for col in TABLES[table])


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n', encoding='utf-8')
