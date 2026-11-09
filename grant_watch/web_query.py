"""Read-only presentation adapter. Never initializes, migrates or writes a database."""
from contextlib import contextmanager
from datetime import datetime
import json
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

from .phase_two import application_status


class DataError(Exception):
    pass


@contextmanager
def connect_readonly(path):
    db = None
    try:
        db = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')  # consistent snapshot across all queries
        yield db
    except (sqlite3.Error, OSError, ValueError) as exc:
        raise DataError('無法唯讀讀取資料庫，請確認檔案、權限與 SQLite 格式。') from exc
    finally:
        if db is not None:
            db.close()


def object_json(value):
    try:
        result = json.loads(value or '{}')
        return result if isinstance(result, dict) else {}
    except (ValueError, TypeError):
        return {}


def read_snapshot(path, as_of=None):
    warnings = []
    with connect_readonly(path) as db:
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}

        def rows(table, required=()):
            if table not in tables:
                warnings.append(f'缺少 {table}；相關資料待確認。')
                return []
            result = [dict(r) for r in db.execute(f'SELECT * FROM "{table}"')]
            columns = {r[1] for r in db.execute(f'PRAGMA table_info("{table}")')}
            if not set(required) <= columns:
                warnings.append(f'{table} 缺少必要欄位；相關資料待確認。')
                return []
            return result

        originals = rows('announcements', ('id', 'title'))
        states = {r['announcement_id']: r for r in rows('application_states', ('announcement_id',))}
        quality = rows('quality_assessments', ('announcement_id', 'assessed_at')) if 'quality_assessments' in tables else []
        quality.sort(key=lambda r: str(r.get('assessed_at') or ''))
        quality = {r['announcement_id']: r for r in quality}
        documents = {r['official_url']: object_json(r.get('document_json'))
                     for r in rows('daily_documents', ('official_url',))}
        sources = rows('sources', ('id',))
        for source in sources:
            source['config'] = object_json(source.get('config'))
        results = []
        for original in originals:
            row = dict(original)
            candidate = quality.get(row['id']) or states.get(row['id']) or {}
            assessment = object_json(candidate.get('assessment_json'))
            fresh = bool(row.get('content_hash') and candidate.get('source_content_hash') == row['content_hash'])
            if candidate.get('source_official_url') and candidate['source_official_url'] != row.get('official_url'):
                fresh = False
            verified = row.get('source_validation_status') == 'verified'
            if not fresh or not verified:
                assessment = {}
            # Malformed derived data must not make the entire page fail or certify a plan.
            try:
                if not isinstance(assessment.get('quality_flags', []), list) or not isinstance(assessment.get('application_windows', []), list):
                    raise ValueError('invalid assessment')
                status = application_status(assessment, as_of)
            except (ValueError, TypeError, AttributeError):
                assessment = {}
                status = dict(status='無法確認', reason='分類資料異常', as_of=str(as_of or ''))
                warnings.append('部分分類資料異常，已降級為待確認。')
            row.update(classification=assessment.get('classification') or '待人工確認',
                       application_status=status['status'], status_reason=status['reason'],
                       assessment=assessment, document=documents.get(row.get('official_url'), {}),
                       government_label={'central': '中央政府', 'local': '地方政府'}.get(row.get('government_level'), '待確認'),
                       industry=row.get('category') if row.get('category') not in ('企業補助計畫', '非補助公告', '待人工確認') else None)
            results.append(row)
        results.sort(key=lambda r: (str(r.get('announced_on') or ''), str(r.get('updated_at') or ''), str(r['id'])), reverse=True)
    return dict(announcements=results, sources=sources, warnings=list(dict.fromkeys(warnings)))


def filter_announcements(rows, keyword='', government=None, city=None, industry=None, status=None, open_only=False):
    needle = keyword.strip().casefold()
    return [r for r in rows if
            (not needle or needle in ' '.join(str(r.get(k) or '') for k in ('title', 'agency', 'content')).casefold())
            and (not government or r.get('government_label') == government)
            and (not city or (r.get('city') or '待確認') == city)
            and (not industry or (r.get('industry') or '待確認') == industry)
            and (not status or r.get('application_status') == status)
            and (not open_only or (r.get('classification') == '企業補助計畫' and r.get('application_status') == '開放申請'))]


def read_report(path):
    try:
        result = object_json(Path(path).read_text(encoding='utf-8'))
        return result, None if result else '更新報告格式異常，統計待確認。'
    except (OSError, UnicodeError):
        return {}, '無法讀取更新報告，統計待確認。'


def taipei_time(value):
    try:
        stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            return str(value) + '（時區待確認）'
        return stamp.astimezone(ZoneInfo('Asia/Taipei')).strftime('%Y-%m-%d %H:%M:%S 台灣時間')
    except (ValueError, TypeError, AttributeError):
        return '待確認'
