"""Isolated MySQL for Apple Silicon macOS. No sudo, system installation or login item."""
import argparse
import hashlib
import os
from pathlib import Path
import platform
import socket
import subprocess
import tarfile
import time
import urllib.request

from db import ROOT, settings

VERSION = '8.4.11'
PACKAGE = f'mysql-{VERSION}-macos15-arm64'
URL = f'https://cdn.mysql.com/Downloads/MySQL-8.4/{PACKAGE}.tar.gz'
# Published by https://dev.mysql.com/downloads/mysql/8.4.html when pinned.
EXPECTED_MD5 = '6e89113f04f2af85d0a164573493db3a'
LOCAL = ROOT / '.local'
BASE = LOCAL / PACKAGE
DATADIR = LOCAL / 'mysql-data'
SOCKET = LOCAL / 'mysql.sock'
PID = LOCAL / 'mysql.pid'
LOG = LOCAL / 'mysql-error.log'


def download():
    if (BASE / 'bin' / 'mysqld').exists():
        return
    archive = LOCAL / f'{PACKAGE}.tar.gz'
    if not archive.exists():
        temporary = archive.with_suffix('.download')
        print('Downloading the official MySQL 8.4 ARM archive (about 160 MB).', flush=True)
        with urllib.request.urlopen(URL, timeout=60) as response, temporary.open('wb') as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        temporary.replace(archive)
    md5 = hashlib.md5()
    with archive.open('rb') as file:
        while chunk := file.read(1024 * 1024):
            md5.update(chunk)
    if md5.hexdigest() != EXPECTED_MD5:
        raise ValueError('MySQL archive checksum mismatch; remove the downloaded archive and retry')
    with tarfile.open(archive, 'r:gz') as source:
        # Reject archive members or links escaping the official package directory.
        for member in source.getmembers():
            dest = (LOCAL / member.name).resolve()
            if not dest.is_relative_to(BASE):
                raise ValueError('Unexpected MySQL archive path')
            if member.issym() or member.islnk():
                target = (dest.parent / member.linkname).resolve() if member.issym() else (LOCAL / member.linkname).resolve()
                if not target.is_relative_to(BASE):
                    raise ValueError('Unexpected archive link')
        if hasattr(tarfile, 'data_filter'):
            source.extractall(LOCAL, filter='data')
        else:
            source.extractall(LOCAL)


def socket_connect(password):
    import pymysql
    return pymysql.connect(unix_socket=str(SOCKET), user='root', password=password,
                           connect_timeout=2, charset='utf8mb4', autocommit=True)


def wait_socket(password, process):
    for _ in range(120):
        if process.poll() is not None:
            raise RuntimeError('MySQL stopped during startup; inspect .local/mysql-error.log')
        try:
            return socket_connect(password)
        except Exception:
            time.sleep(0.5)
    raise RuntimeError('Timed out starting MySQL; inspect .local/mysql-error.log')


def spawn(port, socket_only=False):
    args = [str(BASE / 'bin' / 'mysqld'), '--no-defaults', f'--basedir={BASE}', f'--datadir={DATADIR}',
            f'--socket={SOCKET}', f'--pid-file={PID}', f'--log-error={LOG}', f'--port={port}',
            '--bind-address=127.0.0.1', '--mysqlx=OFF', '--skip-log-bin',
            '--local-infile=OFF', '--secure-file-priv=NULL', '--innodb-buffer-pool-size=256M',
            '--character-set-server=utf8mb4', '--collation-server=utf8mb4_0900_as_cs',
            '--default-time-zone=+00:00']
    if socket_only:
        args.append('--skip-networking')
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            stdin=subprocess.DEVNULL, start_new_session=True)


def start():
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        raise ValueError('Native download is for Apple Silicon macOS; use Docker or an existing MySQL 8.4 server')
    config = settings()
    if config['MYSQL_HOST'] != '127.0.0.1':
        raise ValueError('Native mode requires MYSQL_HOST=127.0.0.1')
    LOCAL.mkdir(exist_ok=True, mode=0o700)
    os.chmod(LOCAL, 0o700)
    password = config['MYSQL_ROOT_PASSWORD']
    try:
        conn = socket_connect(password)
    except Exception:
        conn = None
    if conn:
        with conn:
            with conn.cursor() as cur:
                cur.execute('SELECT @@port, @@datadir, @@skip_networking')
                actual_port, actual_dir, skip_networking = cur.fetchone()
        if Path(actual_dir).resolve() != DATADIR.resolve() or actual_port != int(config['MYSQL_PORT']):
            raise ValueError('Running native server does not match this project configuration')
        if skip_networking:
            raise ValueError('Socket-only initialization is incomplete; stop the native server and rerun')
        print(f'MySQL already running on 127.0.0.1:{actual_port}', flush=True)
        return
    with socket.socket() as probe:
        if probe.connect_ex(('127.0.0.1', int(config['MYSQL_PORT']))) == 0:
            raise ValueError('MYSQL_PORT is in use by another server; choose another port in .env')
    if PID.exists():
        pid = int(PID.read_text().strip())
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            pass
        else:
            raise ValueError('A MySQL process is running but credentials do not match; restore the original .env')
    download()
    if not (DATADIR / 'mysql').exists():
        subprocess.run([str(BASE / 'bin' / 'mysqld'), '--no-defaults', '--initialize-insecure',
                        f'--basedir={BASE}', f'--datadir={DATADIR}', f'--log-error={LOG}'], check=True)
    marker = LOCAL / 'mysql-root-configured'
    if not marker.exists():
        # Passwordless initialization is available only through a socket in a 0700 directory.
        process = spawn(int(config['MYSQL_PORT']), socket_only=True)
        conn = wait_socket('', process)
        try:
            with conn.cursor() as cur:
                cur.execute("ALTER USER 'root'@'localhost' IDENTIFIED BY %s", (password,))
                cur.execute('SHUTDOWN')
        finally:
            conn.close()
        process.wait(timeout=45)
        marker.write_text(f'{VERSION}\n', encoding='utf-8')
    process = spawn(int(config['MYSQL_PORT']))
    conn = wait_socket(password, process)
    conn.close()
    print(f'MySQL {VERSION} running on 127.0.0.1:{config["MYSQL_PORT"]}', flush=True)


def stop():
    with socket_connect(settings()['MYSQL_ROOT_PASSWORD']) as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT @@datadir')
            if Path(cur.fetchone()[0]).resolve() != DATADIR.resolve():
                raise ValueError('Refusing to stop a server outside this project')
            cur.execute('SHUTDOWN')
    print('Native MySQL shutdown requested; data and .env are retained.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['start', 'stop'])
    args = parser.parse_args()
    start() if args.command == 'start' else stop()

