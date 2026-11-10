"""Validate a candidate before publishing any files to grant-data."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3

from .daily import check_database
from .web_query import read_snapshot


def validate(db, report, announcements, baseline=None):
    check_database(db)
    metadata = json.loads(Path(report).read_text(encoding='utf-8'))
    rows = json.loads(Path(announcements).read_text(encoding='utf-8'))
    if metadata.get('status') != 'success' or metadata.get('published') is not True:
        raise ValueError('Refusing unsuccessful candidate')
    for field, path in [('database_sha256', db), ('announcements_sha256', announcements)]:
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() != metadata.get(field):
            raise ValueError('Snapshot digest mismatch')
    snapshot = read_snapshot(db)
    ids = {r['id'] for r in snapshot['announcements']}
    if len(rows) != len(ids) or {r['id'] for r in rows} != ids or metadata['announcement_count'] != len(ids):
        raise ValueError('Snapshot announcement IDs/count mismatch')
    if baseline:
        check_database(baseline)
        with sqlite3.connect(Path(baseline).resolve().as_uri() + '?mode=ro', uri=True) as old:
            old_ids = {r[0] for r in old.execute('SELECT id FROM announcements')}
        if not old_ids <= ids:
            raise ValueError('Historical announcements missing; refusing publish')
    print(f'Validated snapshot: {len(ids)} announcements; historical IDs preserved')
    return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True)
    parser.add_argument('--report', required=True)
    parser.add_argument('--announcements', required=True)
    parser.add_argument('--baseline')
    args = parser.parse_args()
    validate(args.db, args.report, args.announcements, args.baseline)


if __name__ == '__main__':
    main()
