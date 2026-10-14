"""One-command setup: Docker where available; native MySQL on Apple Silicon macOS."""
import argparse
import os
from pathlib import Path
import platform
import secrets
import shutil
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parents[1]


def init_env():
    path = ROOT / '.env'
    if path.exists():
        return
    content = (ROOT / '.env.example').read_text(encoding='utf-8')
    while 'GENERATE_WITH_BOOTSTRAP' in content:
        content = content.replace('GENERATE_WITH_BOOTSTRAP', secrets.token_hex(24), 1)
    # O_EXCL prevents concurrent runs from replacing credentials.
    with path.open('x', encoding='utf-8') as file:
        os.chmod(path, 0o600)
        file.write(content)
    print('Created private .env with independent random passwords.', flush=True)


def local_python():
    path = ROOT / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not path.exists():
        venv.EnvBuilder(with_pip=True).create(ROOT / '.venv')
    subprocess.run([str(path), '-m', 'pip', 'install', '-r', str(ROOT / 'requirements.txt')], check=True)
    return str(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['auto', 'docker', 'native', 'existing'], default='auto')
    parser.add_argument('--env-only', action='store_true')
    args = parser.parse_args()
    if sys.version_info < (3, 10):
        raise SystemExit('Python 3.10+ is required. macOS /usr/bin/python3 may be older; use python3.12.')
    os.chdir(ROOT)
    init_env()
    if args.env_only:
        return
    mode = args.mode
    if mode == 'auto':
        docker_ready = bool(shutil.which('docker')) and subprocess.run(
            ['docker', 'info'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        if docker_ready:
            mode = 'docker'
        elif platform.system() == 'Darwin' and platform.machine() == 'arm64':
            mode = 'native'
        else:
            raise SystemExit('Start Docker Desktop / Docker Engine with Compose, then rerun. '
                             'For an existing MySQL 8.4 server, configure .env and use --mode existing.')
    if mode == 'docker':
        subprocess.run(['docker', 'compose', 'version'], check=True)
        subprocess.run(['docker', 'compose', 'up', '-d', '--wait', 'mysql'], check=True)
        subprocess.run(['docker', 'compose', 'run', '--rm', '--build', 'setup'], check=True)
    else:
        python = local_python()
        if mode == 'native':
            subprocess.run([python, 'scripts/native_mysql.py', 'start'], check=True)
        subprocess.run([python, 'scripts/manage.py', 'setup'], check=True)
    print('Database ready. See README.md for the SELECT-only connection and analysis examples.')


if __name__ == '__main__':
    main()

