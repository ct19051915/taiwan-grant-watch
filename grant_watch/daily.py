"""Atomic daily collection: publish a candidate database only after complete success."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time

from .export import export_rows
from .phase_two import assess_announcement, refresh_derived, enriched_rows
from .service import load_sources
from .storage import Store
from scripts.verify_phase_two import EvidenceClient, verify_source


def check_database(path):
    with sqlite3.connect(f'{Path(path).resolve().as_uri()}?mode=ro', uri=True) as db:
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('SQLite integrity / foreign key check failed')


@contextmanager
def database_lock(path):
    with open(str(path) + '.lock', 'a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def run(db_path, sources, output, initialize=False, verifier=verify_source):
    db_path, output = Path(db_path), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    report = dict(started_at=datetime.now(timezone.utc).isoformat(), status='failed',
                  inserted=0, updated=0, unchanged=0, failed_sources=[], sources={}, published=False)
    try:
        with database_lock(db_path), tempfile.TemporaryDirectory(dir=db_path.parent) as temp:
            candidate = Path(temp) / 'grants.sqlite3'
            if db_path.exists():
                check_database(db_path)
                with sqlite3.connect(db_path) as old, sqlite3.connect(candidate) as new:
                    old.backup(new)
            elif not initialize:
                raise ValueError('Missing database: explicit initialization required; refusing silent reset')
            store = Store(candidate)
            try:
                if not sources:
                    raise ValueError('No enabled sources')
                store.sync_sources(sources)
                documents = {}
                client = EvidenceClient(output)
                for source in sources:
                    record, items = verifier(source, output, client)
                    detail_errors = [d.get('error') for d in record['documents'].values() if d.get('error')]
                    if record['status'] != 'verified' or detail_errors:
                        error = record.get('error') or '; '.join(detail_errors) or record['status']
                        report['failed_sources'].append(dict(id=source['id'], error=error))
                        report['sources'][source['id']] = dict(error=error)
                        continue
                    counts = store.save_batch(source['id'], items)
                    report['sources'][source['id']] = counts
                    for key in ('inserted', 'updated', 'unchanged'):
                        report[key] += counts[key]
                    documents.update(record['documents'])
                # Preserve prior evidence for announcements absent from today's listing.
                store.db.executescript('''CREATE TABLE IF NOT EXISTS daily_documents (
                    official_url TEXT PRIMARY KEY, document_json TEXT NOT NULL);''')
                with store.db:
                    for url, doc in documents.items():
                        store.db.execute('INSERT OR REPLACE INTO daily_documents VALUES (?,?)',
                                         (url, json.dumps(doc, ensure_ascii=False)))
                documents = {r[0]: json.loads(r[1]) for r in store.db.execute('SELECT * FROM daily_documents')}
                assessments = {r['id']: assess_announcement(r, documents.get(r['official_url'], dict(error='無官方詳情')))
                               for r in store.announcements()}
                refresh_derived(store, assessments)
                rows = enriched_rows(store)
                export_rows(rows, output / 'announcements.xlsx')
                export_rows([r for r in rows if r['category'] == '企業補助計畫'], output / 'enterprise-grants.xlsx')
                report['announcement_count'] = len(rows)
            finally:
                store.close()
            check_database(candidate)
            if report['failed_sources']:
                raise ValueError('One or more sources failed; original database preserved')
            os.replace(candidate, db_path)
            report.update(status='success', published=True)
    except Exception as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
    finally:
        report['duration_seconds'] = round(time.monotonic() - started, 3)
        report['completed_at'] = datetime.now(timezone.utc).isoformat()
        (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        summary = (f"## 每日補助追蹤：{report['status']}\n\n"
                   f"新增 {report['inserted']}；更新 {report['updated']}；未變 {report['unchanged']}；"
                   f"失敗來源 {len(report['failed_sources'])}；耗時 {report['duration_seconds']} 秒。\n\n"
                   '失敗執行的 Excel 為未保存的候選結果。新增／更新數為候選寫入次數。\n\n')
        summary += '\n'.join(f"- {s['id']}: {s['error']}" for s in report['failed_sources'])
        summary += '\n\n' + report.get('error', '') + '\n'
        (output / 'summary.md').write_text(summary)
        print(summary)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default='var/grants.sqlite3')
    parser.add_argument('--output', default='var/daily')
    parser.add_argument('--sources', default='data/phase-two-sources.json')
    parser.add_argument('--initialize', action='store_true')
    args = parser.parse_args()
    sources = [s for s in load_sources(args.sources) if s.get('validation_status') == 'verified']
    raise SystemExit(0 if run(args.db, sources, args.output, args.initialize)['status'] == 'success' else 1)


if __name__ == '__main__':
    main()
