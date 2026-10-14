"""Create, import and verify the nine-table MySQL snapshot without destructive resets."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal
from itertools import islice
import json
from pathlib import Path
import sys

from catalog import TABLES, PRIMARY_KEYS, FOREIGN_KEYS, checks_for, schema_sql
from data_contract import ROOT, DATA_DIR, MANIFEST, audit, expected_rows, read_rows, write_json
from db import connect, settings


def provision():
    config = settings()
    database = config['MYSQL_DATABASE']
    with connect('root', database=False) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT VERSION()')
            version = cur.fetchone()[0]
            if not version.startswith('8.4.'):
                raise ValueError(f'This project requires MySQL 8.4 LTS; connected server is {version}')
            cur.execute(f'CREATE DATABASE IF NOT EXISTS `{database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs')
            for user_key, pass_key, grants in [
                ('MYSQL_USER', 'MYSQL_PASSWORD', 'ALL PRIVILEGES'),
                ('MYSQL_ANALYST_USER', 'MYSQL_ANALYST_PASSWORD', 'SELECT')]:
                # Do not rotate passwords or revoke pre-existing accounts automatically.
                cur.execute('CREATE USER IF NOT EXISTS %s@%s IDENTIFIED BY %s',
                            (config[user_key], '%', config[pass_key]))
                cur.execute(f'GRANT {grants} ON `{database}`.* TO %s@%s', (config[user_key], '%'))
        conn.commit()


def verify_schema(conn):
    config = settings()
    database = config['MYSQL_DATABASE']
    with conn.cursor() as cur:
        cur.execute('SELECT TABLE_NAME, ENGINE, TABLE_COLLATION FROM information_schema.TABLES '
                    'WHERE TABLE_SCHEMA=%s AND TABLE_TYPE=%s', (database, 'BASE TABLE'))
        actual = cur.fetchall()
        if {x[0] for x in actual} != set(TABLES):
            raise ValueError('Database must contain exactly the nine approved base tables')
        if any(x[1] != 'InnoDB' or x[2] != 'utf8mb4_0900_as_cs' for x in actual):
            raise ValueError('Table engine or collation differs from the schema')
        for table, columns in TABLES.items():
            cur.execute('SELECT COLUMN_NAME,COLUMN_TYPE,IS_NULLABLE,COLLATION_NAME '
                        'FROM information_schema.COLUMNS WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s '
                        'ORDER BY ORDINAL_POSITION', (database, table))
            expected = []
            for col in columns:
                text = col.base_type.startswith(('char(', 'varchar(', 'text'))
                collation = 'ascii_bin' if 'ascii_bin' in col.sql else 'utf8mb4_0900_as_cs' if text else None
                expected.append((col.name, col.base_type, 'YES' if col.nullable else 'NO', collation))
            if list(cur.fetchall()) != expected:
                raise ValueError(f'{table}: SQL columns differ from the reviewed schema')
            cur.execute('SELECT COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE '
                        'WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND CONSTRAINT_NAME=%s '
                        'ORDER BY ORDINAL_POSITION', (database, table, 'PRIMARY'))
            if tuple(x[0] for x in cur.fetchall()) != PRIMARY_KEYS[table]:
                raise ValueError(f'{table}: primary key differs from the reviewed schema')
        cur.execute('SELECT TABLE_NAME,COLUMN_NAME,REFERENCED_TABLE_NAME,REFERENCED_COLUMN_NAME '
                    'FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=%s '
                    'AND REFERENCED_TABLE_NAME IS NOT NULL', (database,))
        if set(cur.fetchall()) != set(FOREIGN_KEYS):
            raise ValueError('Foreign keys differ from the reviewed schema')
        cur.execute('SELECT TABLE_NAME,CONSTRAINT_NAME,ENFORCED FROM information_schema.TABLE_CONSTRAINTS '
                    'WHERE CONSTRAINT_SCHEMA=%s AND CONSTRAINT_TYPE=%s', (database, 'CHECK'))
        expected_checks = {(t, f'ck_{t}_{i}', 'YES') for t in TABLES for i in range(1, len(checks_for(t)) + 1)}
        if set(cur.fetchall()) != expected_checks:
            raise ValueError('CHECK constraints differ from the reviewed schema')


def verify_database(conn, data_dir=DATA_DIR):
    import pymysql
    verify_schema(conn)
    geo = {row['zip_code_prefix'] for row in read_rows('geolocation', data_dir)}
    result = {'tables': {}, 'row_values_compared': 0}
    with conn.cursor() as cur:
        cur.execute('SELECT VERSION(), @@character_set_connection, @@session.foreign_key_checks')
        result['mysql_version'], result['connection_charset'], fk_enabled = cur.fetchone()
        if fk_enabled != 1:
            raise ValueError('Foreign key checks are disabled')
    for table, columns in TABLES.items():
        positions = [next(i for i, col in enumerate(columns) if col.name == name) for name in PRIMARY_KEYS[table]]
        expected = sorted(expected_rows(table, geo, data_dir), key=lambda row: tuple(row[i] for i in positions))
        names = ','.join(f'`{col.name}`' for col in columns)
        order_by = ','.join(f'`{col}`' for col in PRIMARY_KEYS[table])
        count = 0
        with conn.cursor(pymysql.cursors.SSCursor) as cur:
            cur.execute(f'SELECT {names} FROM `{table}` ORDER BY {order_by}')
            for row in cur:
                if count >= len(expected) or row != expected[count]:
                    raise ValueError(f'{table}: database differs from the CSV at sorted row {count + 1}')
                count += 1
        if count != len(expected):
            raise ValueError(f'{table}: database row count differs from CSV')
        result['tables'][table] = {'rows': count, 'all_values_match_csv': True}
        result['row_values_compared'] += count * len(columns)
        print(f'Verified {table}: {count:,} rows, every value matches', flush=True)
    with conn.cursor() as cur:
        cur.execute('SELECT SUM(price),SUM(freight_value),SUM(item_total) FROM order_items')
        price, freight, total = cur.fetchone()
        cur.execute('SELECT SUM(payment_value) FROM order_payments')
        payments = cur.fetchone()[0]
        result['brl_totals'] = dict(items_price=str(price), items_freight=str(freight),
                                   items_total=str(total), payments=str(payments))
        for table in ('customers', 'sellers'):
            cur.execute(f'SELECT COUNT(*) FROM `{table}` WHERE geo_zip_code_prefix IS NULL')
            result[f'{table}_without_geolocation'] = cur.fetchone()[0]
    result['total_rows'] = sum(x['rows'] for x in result['tables'].values())
    result['foreign_keys'] = len(FOREIGN_KEYS)
    result['status'] = 'PASS'
    return result


def verify_readonly():
    import pymysql
    with connect('analyst') as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) FROM orders')
            if cur.fetchone()[0] == 0:
                raise ValueError('Analyst cannot see imported orders')
            try:
                # Even if incorrectly granted, WHERE 1=0 cannot change any record.
                cur.execute('UPDATE orders SET order_status=order_status WHERE 1=0')
            except pymysql.err.OperationalError as exc:
                if exc.args[0] != 1142:
                    raise
            else:
                conn.rollback()
                raise ValueError('Analyst has UPDATE permission; use a separate SELECT-only account')
            # Detect wider grants too, including global privileges and roles.
            cur.execute('SHOW GRANTS FOR CURRENT_USER()')
            grants = [row[0] for row in cur.fetchall()]
            database = settings()['MYSQL_DATABASE']
            allowed = {f"GRANT USAGE ON *.* TO `{settings()['MYSQL_ANALYST_USER']}`@`%`",
                       f"GRANT SELECT ON `{database}`.* TO `{settings()['MYSQL_ANALYST_USER']}`@`%`"}
            if set(grants) != allowed:
                raise ValueError('Analyst grants are broader than the expected database-only SELECT access')
    return {'select': 'PASS', 'update_denied': True, 'grants': 'database-only SELECT'}


def setup(data_dir=DATA_DIR):
    source = audit(data_dir)
    write_json(ROOT / 'reports' / 'source_audit.json', source)
    ddl_path = ROOT / 'sql' / 'schema.sql'
    if ddl_path.read_text(encoding='utf-8') != schema_sql():
        raise ValueError('sql/schema.sql differs from catalog.py; regenerate and review before setup')
    provision()
    with connect('loader') as conn:
        with conn.cursor() as cur:
            # A named lock prevents two copies of this loader from racing.
            cur.execute('SELECT GET_LOCK(%s, 0)', (settings()['MYSQL_DATABASE'] + ':olist-setup',))
            if cur.fetchone()[0] != 1:
                raise ValueError('Another setup is already running')
            cur.execute('SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s',
                        (settings()['MYSQL_DATABASE'],))
            existing = {x[0] for x in cur.fetchall()}
            if existing - set(TABLES):
                raise ValueError('Target database contains unrelated objects; choose a new MYSQL_DATABASE')
            for statement in ddl_path.read_text(encoding='utf-8').split(';'):
                if statement.strip():
                    cur.execute(statement)
            verify_schema(conn)
            counts = []
            for table in TABLES:
                cur.execute(f'SELECT COUNT(*) FROM `{table}`')
                counts.append(cur.fetchone()[0])
        if any(counts):
            print('Existing data found; validating without overwriting it.', flush=True)
            result = verify_database(conn, data_dir)
            result['setup_action'] = 'existing snapshot verified; no rows changed'
        else:
            conn.begin()
            geo = {row['zip_code_prefix'] for row in read_rows('geolocation', data_dir)}
            try:
                with conn.cursor() as cur:
                    for table, columns in TABLES.items():
                        names = ','.join(f'`{x.name}`' for x in columns)
                        placeholders = ','.join(['%s'] * len(columns))
                        query = f'INSERT INTO `{table}` ({names}) VALUES ({placeholders})'
                        stream = iter(expected_rows(table, geo, data_dir))
                        count = 0
                        while batch := list(islice(stream, 1000)):
                            cur.executemany(query, batch)
                            count += len(batch)
                        print(f'Imported {table}: {count:,} rows', flush=True)
                result = verify_database(conn, data_dir)
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
            result['setup_action'] = 'all nine tables imported in one transaction'
    result['analyst_access'] = verify_readonly()
    result['verified_at_utc'] = datetime.now(timezone.utc).isoformat()
    write_json(ROOT / 'reports' / 'database_validation.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['audit', 'setup', 'verify', 'status'])
    parser.add_argument('--data-dir', type=Path, default=DATA_DIR)
    args = parser.parse_args()
    if args.command == 'audit':
        report = audit(args.data_dir)
        write_json(ROOT / 'reports' / 'source_audit.json', report)
        print(f"PASS: 9 CSV tables, {report['total_rows']:,} rows; source hashes, keys and references verified")
    elif args.command == 'setup':
        report = setup(args.data_dir)
        print(f"PASS: {report['total_rows']:,} rows ready for analysis. Connection details: .env (private).")
    elif args.command == 'verify':
        audit(args.data_dir)
        with connect('analyst') as conn:
            report = verify_database(conn, args.data_dir)
        report['analyst_access'] = verify_readonly()
        report['verified_at_utc'] = datetime.now(timezone.utc).isoformat()
        write_json(ROOT / 'reports' / 'database_validation.json', report)
        print('PASS: full database comparison and SELECT-only access verified')
    else:
        with connect('analyst') as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT VERSION(), DATABASE(), CURRENT_USER()')
                print(dict(zip(['mysql_version', 'database', 'account'], cur.fetchone())))
                for table in TABLES:
                    cur.execute(f'SELECT COUNT(*) FROM `{table}`')
                    print(f'{table}: {cur.fetchone()[0]:,}')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Avoid leaking SQL values/passwords from connector exception messages.
        if isinstance(exc, (ValueError, FileNotFoundError)):
            print(f'ERROR: {exc}', file=sys.stderr)
        else:
            number = exc.args[0] if exc.args and isinstance(exc.args[0], int) else 'see server log'
            print(f'ERROR: {type(exc).__name__}, code={number}. Check .env, database and reports; no data reset was performed.', file=sys.stderr)
        sys.exit(1)
