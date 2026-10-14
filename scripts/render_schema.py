"""Regenerate the reviewable SQL file after an intentional catalog change."""
from pathlib import Path
from catalog import schema_sql

if __name__ == '__main__':
    path = Path(__file__).resolve().parents[1] / 'sql' / 'schema.sql'
    path.write_text(schema_sql(), encoding='utf-8')
    print('Wrote sql/schema.sql')
