"""Restore the analysis-only wide CSV byte-for-byte without importing it."""
import gzip
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]

if __name__ == '__main__':
    entry = json.loads((ROOT / 'data' / 'manifest.json').read_text())['not_imported']['fact_orders_wide']
    target = ROOT / 'analysis' / 'fact_orders_wide.csv'
    archive = target.with_suffix('.csv.gz')
    if not target.exists():
        temporary = target.with_suffix('.csv.tmp')
        with gzip.open(archive, 'rb') as source, temporary.open('wb') as output:
            shutil.copyfileobj(source, output)
        if hashlib.sha256(temporary.read_bytes()).hexdigest() != entry['sha256']:
            temporary.unlink()
            raise SystemExit('Analysis CSV checksum mismatch')
        temporary.replace(target)
    if hashlib.sha256(target.read_bytes()).hexdigest() != entry['sha256']:
        raise SystemExit('Existing analysis CSV differs; it was not overwritten')
    print('analysis/fact_orders_wide.csv restored and SHA-256 verified. Not imported into MySQL.')

