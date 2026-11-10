"""Exercise the actual workflow publish shell against an isolated local Git remote."""
import os
from pathlib import Path
import subprocess
import textwrap

import pytest


WORKFLOW = Path('.github/workflows/daily.yml').read_text()
PUBLISH = textwrap.dedent(WORKFLOW.split('      - name: Persist successful snapshot (no force push)\n')[1].split('        run: |\n')[1])


def git(path, *args):
    return subprocess.check_output(['git', '-C', str(path), *args], text=True).strip()


@pytest.fixture
def remote_repo(tmp_path):
    remote, checkout = tmp_path/'remote.git', tmp_path/'checkout'
    subprocess.run(['git', 'init', '--bare', str(remote)], check=True, capture_output=True)
    subprocess.run(['git', 'clone', str(remote), str(checkout)], check=True, capture_output=True)
    git(checkout, 'config', 'user.name', 'Synthetic Test')
    git(checkout, 'config', 'user.email', 'synthetic@example.test')
    git(checkout, 'checkout', '-b', 'main')
    (checkout/'README.md').write_text('synthetic source')
    git(checkout, 'add', '.')
    git(checkout, 'commit', '-m', 'source')
    git(checkout, 'push', 'origin', 'main')
    git(checkout, 'checkout', '--orphan', 'grant-data')
    git(checkout, 'rm', '-rf', '.')
    (checkout/'grants.sqlite3').write_bytes(b'synthetic old database')
    git(checkout, 'add', '.')
    git(checkout, 'commit', '-m', 'old data')
    git(checkout, 'push', 'origin', 'grant-data')
    base = git(checkout, 'rev-parse', 'HEAD')
    git(checkout, 'checkout', 'main')
    (checkout/'candidate/var').mkdir(parents=True)
    (checkout/'candidate/reports').mkdir()
    (checkout/'candidate/var/grants.sqlite3').write_bytes(b'synthetic new database')
    (checkout/'candidate/reports/report.json').write_text('{"status":"success"}')
    (checkout/'candidate/reports/announcements.json').write_text('[]')
    return remote, checkout, base


def publish(checkout, base, initialize='false'):
    return subprocess.run(['bash', '-e', '-c', PUBLISH], cwd=checkout,
                          env=dict(os.environ, BASE_SHA=base, INITIALIZE=initialize,
                                   GITHUB_RUN_ID='synthetic', GITHUB_STEP_SUMMARY=str(checkout/'summary.md')),
                          capture_output=True, text=True)


def test_publish_same_commit_and_preserve_history(remote_repo):
    remote, checkout, base = remote_repo
    result = publish(checkout, base)
    assert result.returncode == 0, result.stderr
    assert git(remote, 'rev-parse', 'grant-data^') == base
    assert git(remote, 'ls-tree', '--name-only', 'grant-data').splitlines() == [
        'announcements.json', 'grants.sqlite3', 'latest-report.json']
    assert git(remote, 'show', 'grant-data:latest-report.json') == '{"status":"success"}'
    assert git(remote, 'show', 'main:README.md') == 'synthetic source'


def test_stale_candidate_cannot_overwrite(remote_repo):
    remote, checkout, base = remote_repo
    result = publish(checkout, '0'*40)
    assert result.returncode != 0
    assert 'Data changed' in result.stdout
    assert git(remote, 'rev-parse', 'grant-data') == base


def test_disappeared_branch_cannot_reset_even_with_initialize(remote_repo):
    remote, checkout, base = remote_repo
    git(checkout, 'push', 'origin', '--delete', 'grant-data')
    result = publish(checkout, base, 'true')
    assert result.returncode != 0
    assert 'refusing reset' in result.stdout
