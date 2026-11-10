import json
import sqlite3
from pathlib import Path
from uuid import uuid4
from .models import Announcement, now


class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS sources (
            id TEXT PRIMARY KEY, config TEXT NOT NULL,
            validation_status TEXT NOT NULL DEFAULT 'pending',
            last_checked_at TEXT, last_success_at TEXT, last_outcome TEXT, last_error TEXT
        );
        CREATE TABLE IF NOT EXISTS announcements (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, agency TEXT NOT NULL,
            government_level TEXT NOT NULL, city TEXT, official_url TEXT UNIQUE NOT NULL,
            announced_on TEXT, deadline TEXT, amount TEXT, eligibility TEXT, category TEXT,
            content TEXT, content_hash TEXT NOT NULL, fetched_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            source_validation_status TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS announcement_versions (
            id INTEGER PRIMARY KEY, announcement_id TEXT NOT NULL REFERENCES announcements(id),
            recorded_at TEXT NOT NULL, snapshot_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS version_announcement_index ON announcement_versions(announcement_id);
        CREATE INDEX IF NOT EXISTS hash_index ON announcements(content_hash);
        CREATE TABLE IF NOT EXISTS source_items (
            source_id TEXT NOT NULL REFERENCES sources(id),
            item_key TEXT NOT NULL, announcement_id TEXT NOT NULL REFERENCES announcements(id),
            PRIMARY KEY(source_id, item_key)
        );
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY, source_id TEXT NOT NULL REFERENCES sources(id),
            checked_at TEXT NOT NULL, outcome TEXT NOT NULL, count INTEGER NOT NULL,
            error TEXT
        );
        ''')

    def close(self):
        self.db.close()

    def sync_sources(self, sources):
        with self.db:
            for source in sources:
                previous = self.db.execute('SELECT config FROM sources WHERE id=?', (source['id'],)).fetchone()
                config = json.dumps(source, ensure_ascii=False)
                if previous:
                    old = json.loads(previous['config'])
                    changed = any(old.get(k) != source.get(k) for k in
                                  ('url', 'method', 'parser', 'agency', 'government_level', 'city', 'terms_reviewed', 'exclude_title_contains', 'include_title_contains', 'detail_selector', 'detail_fields', 'detail_exclude_selectors', 'detail_ignored_line_patterns', 'terms_url', 'allow_empty'))
                    self.db.execute('UPDATE sources SET config=? WHERE id=?', (config, source['id']))
                    if changed:
                        self.db.execute("UPDATE sources SET validation_status='pending',last_success_at=NULL,last_checked_at=NULL,last_outcome=NULL,last_error=NULL WHERE id=?", (source['id'],))
                else:
                    self.db.execute('INSERT INTO sources(id,config,last_checked_at,last_outcome,last_error) VALUES (?,?,?,?,?)',
                                    (source['id'], config, source.get('last_checked_at'),
                                     source.get('last_check_outcome'), source.get('last_error')))


    def _upsert(self, source_id: str, item: Announcement, timestamp: str):
        values = item.normalized()
        external_id = values.pop('external_id')
        key = 'id:' + external_id if external_id else 'url:' + values['official_url']
        digest = item.fingerprint()
        linked = self.db.execute('''SELECT a.* FROM announcements a JOIN source_items s
            ON a.id=s.announcement_id WHERE s.source_id=? AND s.item_key=?''', (source_id, key)).fetchone()
        url_row = self.db.execute('SELECT * FROM announcements WHERE official_url=?', (values['official_url'],)).fetchone()
        if linked and url_row and linked['id'] != url_row['id']:
            raise ValueError('來源 ID 與網址指向不同公告，拒絕自動合併')
        row = linked or url_row
        if row is None and not item.external_id and values['content'] and values['announced_on']:
            # 只在同一來源內以完整標準化內容雜湊折疊 URL 別名。
            row = self.db.execute('''SELECT a.* FROM announcements a JOIN source_items s
                ON a.id=s.announcement_id WHERE s.source_id=? AND a.content_hash=? LIMIT 1''',
                (source_id, digest)).fetchone()
        if row is None:
            uid, outcome = str(uuid4()), 'inserted'
            data = dict(id=uid, **values, content_hash=digest, fetched_at=timestamp,
                        last_seen_at=timestamp, updated_at=timestamp, source_validation_status='verified')
            columns = ','.join(data)
            self.db.execute(f'INSERT INTO announcements ({columns}) VALUES ({",".join("?" for _ in data)})', tuple(data.values()))
        else:
            uid = row['id']
            changed = row['content_hash'] != digest or (linked is not None and row['official_url'] != values['official_url'])
            outcome = 'updated' if changed else 'unchanged'
            # 相同內容的別名不造成 canonical URL 來回切換。
            data = dict(values, content_hash=digest, updated_at=timestamp) if changed else {}
            data.update(last_seen_at=timestamp, source_validation_status='verified')
            self.db.execute(f'UPDATE announcements SET {",".join(k+"=?" for k in data)} WHERE id=?', (*data.values(), uid))
        if outcome in {'inserted', 'updated'}:
            # 舊資料庫首次修改時也先保存修改前全文；所有版本與公告更新同一交易。
            if row is not None and not self.db.execute(
                    'SELECT 1 FROM announcement_versions WHERE announcement_id=?', (uid,)).fetchone():
                self.db.execute('INSERT INTO announcement_versions(announcement_id,recorded_at,snapshot_json) VALUES (?,?,?)',
                                (uid, row['updated_at'], json.dumps(dict(row), ensure_ascii=False)))
            current = dict(self.db.execute('SELECT * FROM announcements WHERE id=?', (uid,)).fetchone())
            self.db.execute('INSERT INTO announcement_versions(announcement_id,recorded_at,snapshot_json) VALUES (?,?,?)',
                            (uid, timestamp, json.dumps(current, ensure_ascii=False)))
        self.db.execute('INSERT OR IGNORE INTO source_items VALUES (?,?,?)', (source_id, key, uid))
        return outcome

    def save_batch(self, source_id, items):
        counts = dict(inserted=0, updated=0, unchanged=0)
        timestamp = now()
        with self.db:
            for item in items:
                counts[self._upsert(source_id, item, timestamp)] += 1
            self._record(source_id, 'success', len(items), None, timestamp)
        return counts

    def _record(self, source_id, outcome, count, error, timestamp):
        self.db.execute('INSERT INTO runs(source_id,checked_at,outcome,count,error) VALUES (?,?,?,?,?)',
                        (source_id, timestamp, outcome, count, error))
        self.db.execute('UPDATE sources SET last_checked_at=?,last_outcome=?,last_error=? WHERE id=?',
                        (timestamp, outcome, error, source_id))
        if outcome == 'success':
            self.db.execute("UPDATE sources SET validation_status='verified',last_success_at=? WHERE id=?", (timestamp, source_id))

    def record_failure(self, source_id, error):
        with self.db:
            self._record(source_id, 'failed', 0, error, now())

    def announcements(self):
        return [dict(row) for row in self.db.execute('SELECT * FROM announcements ORDER BY id')]

    def sources(self):
        return [dict(row) for row in self.db.execute('SELECT * FROM sources ORDER BY id')]
