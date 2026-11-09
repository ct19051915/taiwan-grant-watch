"""僅新增分類表與 view，不對既有來源／公告表執行 INSERT、UPDATE 或 DELETE。"""
import hashlib
import json
import sqlite3
from .models import now
from .quality import RULE_VERSION

ORIGINAL_TABLES = ('announcements', 'sources', 'source_items', 'runs')


def digest_original(db):
    result = {}
    for table in ORIGINAL_TABLES:
        result[table] = sorted([dict(row) for row in db.execute(f'SELECT * FROM {table}')],
                               key=lambda row: json.dumps(row, ensure_ascii=False, sort_keys=True))
    return hashlib.sha256(json.dumps(result, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


class QualityStore:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS quality_runs (
            id TEXT PRIMARY KEY, created_at TEXT NOT NULL, rule_version TEXT NOT NULL,
            original_digest TEXT NOT NULL, announcement_count INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS quality_documents (
            run_id TEXT NOT NULL REFERENCES quality_runs(id),
            announcement_id TEXT NOT NULL REFERENCES announcements(id),
            document_json TEXT NOT NULL,
            PRIMARY KEY(run_id,announcement_id)
        );
        CREATE TABLE IF NOT EXISTS quality_assessments (
            run_id TEXT NOT NULL REFERENCES quality_runs(id),
            announcement_id TEXT NOT NULL REFERENCES announcements(id),
            source_content_hash TEXT NOT NULL, source_official_url TEXT NOT NULL,
            classification TEXT NOT NULL CHECK(classification IN ('企業補助計畫','非補助公告','待人工確認')),
            document_kind TEXT NOT NULL, reason TEXT NOT NULL,
            summary TEXT, eligibility TEXT, amount TEXT, application_period TEXT,
            application_start TEXT, deadline TEXT, application_url TEXT,
            assessment_json TEXT NOT NULL, assessed_at TEXT NOT NULL,
            PRIMARY KEY(run_id,announcement_id)
        );
        CREATE VIEW IF NOT EXISTS latest_announcement_assessments AS
            SELECT ranked.*, CASE WHEN a.content_hash != ranked.source_content_hash
                OR a.official_url != ranked.source_official_url THEN 1 ELSE 0 END AS is_stale
            FROM (
                SELECT q.*, r.rule_version, ROW_NUMBER() OVER (
                    PARTITION BY q.announcement_id ORDER BY r.created_at DESC, r.id DESC) AS revision_rank
                FROM quality_assessments q JOIN quality_runs r ON r.id=q.run_id
            ) ranked JOIN announcements a ON a.id=ranked.announcement_id
            WHERE revision_rank=1;
        ''')

    def close(self):
        self.db.close()

    def save(self, rows, documents, assessments):
        if {r['id'] for r in rows} != set(documents) or set(documents) != set(assessments):
            raise ValueError('原始公告、官方快照與分類結果集合不一致')
        original_digest = digest_original(self.db)
        identity = dict(rule_version=RULE_VERSION, originals=rows, documents=documents)
        run_id = hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        timestamp = now()
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO quality_runs VALUES (?,?,?,?,?)',
                            (run_id, timestamp, RULE_VERSION, original_digest, len(rows)))
            for row in rows:
                result = assessments[row['id']]
                self.db.execute('INSERT OR IGNORE INTO quality_documents VALUES (?,?,?)',
                                (run_id, row['id'], json.dumps(documents[row['id']], ensure_ascii=False)))
                scalar = {key: result.get(key) for key in ('classification', 'document_kind', 'reason', 'summary',
                          'eligibility', 'amount', 'application_period', 'application_start', 'deadline', 'application_url')}
                data = dict(run_id=run_id, announcement_id=row['id'], source_content_hash=row['content_hash'],
                            source_official_url=row['official_url'], **scalar,
                            assessment_json=json.dumps(result, ensure_ascii=False), assessed_at=timestamp)
                self.db.execute(f'INSERT OR IGNORE INTO quality_assessments ({",".join(data)}) VALUES ({",".join("?" for _ in data)})', tuple(data.values()))
            if digest_original(self.db) != original_digest:
                raise RuntimeError('原始資料有變化；回滾分類交易')
        return run_id
