"""逐筆擷取並分類現有公告，或以保存的真實官方快照重播（無合成資料）。"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from grant_watch.quality import classify, GRANT, NON_GRANT, REVIEW
from grant_watch.quality_documents import fetch_documents, load_snapshot, validate_snapshot_inputs
from grant_watch.quality_export import export_quality
from grant_watch.quality_store import QualityStore, digest_original


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default='var/grants.sqlite3')
    parser.add_argument('--snapshot', help='重播既有官方 documents.json 所在目錄；不發出網路請求')
    parser.add_argument('--output', default='var/quality')
    args = parser.parse_args()
    if not Path(args.db).is_file():
        parser.error('指定的原始 SQLite 資料庫不存在；不建立空資料庫')
    db = sqlite3.connect(args.db)
    db.row_factory = sqlite3.Row
    rows = [dict(r) for r in db.execute('SELECT * FROM announcements ORDER BY official_url')]
    before = digest_original(db)
    if args.snapshot:
        directory = Path(args.snapshot)
        originals = json.loads((directory / 'original-announcements.json').read_text())
        validate_snapshot_inputs(rows, originals)
        documents = load_snapshot(directory)
    else:
        directory = Path(args.output) / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        directory.mkdir(parents=True)
        with sqlite3.connect(directory / 'before.sqlite3') as destination:
            db.backup(destination)
        (directory / 'original-announcements.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n')
        documents = fetch_documents(rows, directory)
    db.close()
    by_id = {d['announcement_id']: d for d in documents}
    if len(by_id) != len(documents) or set(by_id) != {r['id'] for r in rows}:
        raise ValueError('官方快照與目前公告集合不一致；請重新擷取')
    results = {row['id']: classify(row, by_id[row['id']]) for row in rows}
    store = QualityStore(args.db)
    try:
        if digest_original(store.db) != before:
            raise RuntimeError('評估期間原始資料有變更，請重跑')
        run_id = store.save(rows, by_id, results)
        assert digest_original(store.db) == before
        stale = {r['announcement_id']: r['is_stale'] for r in store.db.execute('SELECT * FROM latest_announcement_assessments')}
        export_rows = [dict(announcement_id=r['id'], title=r['title'], agency=r['agency'], official_url=r['official_url'],
                            announced_on=r['announced_on'], is_stale=stale[r['id']], **results[r['id']]) for r in rows]
        paths = export_quality(export_rows, Path(args.output))
        summary = dict(run_id=run_id, snapshot=str(directory), count=len(rows),
                       counts=dict(Counter(r['classification'] for r in export_rows)),
                       official_http_200=sum(d.get('http_status') == 200 and not d.get('error') for d in documents),
                       originals_unchanged=True, original_digest=before, exports=paths,
                       manual_review=[dict(title=r['title'], url=r['official_url'], reason=r['reason']) for r in export_rows if r['classification'] == REVIEW],
                       field_gaps=[dict(title=r['title'], url=r['official_url'], flags=r['quality_flags']) for r in export_rows if r['classification'] == GRANT and r['quality_flags']])
        Path(args.output).mkdir(parents=True, exist_ok=True)
        (Path(args.output) / 'report.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
        (Path(args.output) / 'assessments.json').write_text(json.dumps(export_rows, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    finally:
        store.close()


if __name__ == '__main__':
    raise SystemExit(main())
