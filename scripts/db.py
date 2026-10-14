"""Connection configuration shared by the loader and analysis examples."""
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def settings():
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env', override=False)
    names = ['MYSQL_HOST', 'MYSQL_PORT', 'MYSQL_DATABASE', 'MYSQL_USER', 'MYSQL_PASSWORD',
             'MYSQL_ROOT_PASSWORD', 'MYSQL_ANALYST_USER', 'MYSQL_ANALYST_PASSWORD']
    config = {key: os.environ.get(key, '') for key in names}
    for key in names:
        if not config[key] or config[key] == 'GENERATE_WITH_BOOTSTRAP':
            raise ValueError(f'{key} is missing; run scripts/bootstrap.py to create .env')
    for key in ('MYSQL_DATABASE', 'MYSQL_USER', 'MYSQL_ANALYST_USER'):
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{0,31}', config[key]):
            raise ValueError(f'{key}: only letters, digits and underscores are supported')
    if config['MYSQL_USER'] == config['MYSQL_ANALYST_USER'] or 'root' in (config['MYSQL_USER'], config['MYSQL_ANALYST_USER']):
        raise ValueError('Loader, analyst and root must be separate accounts')
    port = int(config['MYSQL_PORT'])
    if not 1 <= port <= 65535:
        raise ValueError('MYSQL_PORT must be between 1 and 65535')
    config['MYSQL_SSL_CA'] = os.environ.get('MYSQL_SSL_CA', '')
    if config['MYSQL_HOST'] not in ('127.0.0.1', 'localhost', 'mysql') and not config['MYSQL_SSL_CA']:
        raise ValueError('For a remote server set MYSQL_SSL_CA to its trusted CA certificate')
    return config


def connect(role='analyst', database=True):
    """Default to the SELECT-only account. Passwords are never printed."""
    import pymysql
    config = settings()
    if role == 'root':
        user, password = 'root', config['MYSQL_ROOT_PASSWORD']
    elif role == 'loader':
        user, password = config['MYSQL_USER'], config['MYSQL_PASSWORD']
    elif role == 'analyst':
        user, password = config['MYSQL_ANALYST_USER'], config['MYSQL_ANALYST_PASSWORD']
    else:
        raise ValueError(f'Unsupported role: {role}')
    options = dict(host=config['MYSQL_HOST'], port=int(config['MYSQL_PORT']),
                   user=user, password=password, charset='utf8mb4', autocommit=False,
                   connect_timeout=15, read_timeout=300, write_timeout=300,
                   local_infile=False,
                   init_command="SET SESSION sql_mode='STRICT_ALL_TABLES,NO_ZERO_DATE,NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION', time_zone='+00:00'")
    if database:
        options['database'] = config['MYSQL_DATABASE']
    if config['MYSQL_SSL_CA']:
        options.update(ssl_ca=config['MYSQL_SSL_CA'], ssl_verify_cert=True, ssl_verify_identity=True)
    return pymysql.connect(**options)

