"""第二階段衍生資料：時間敏感申請狀態與可稽核跨站關聯，保留原公告。"""
from datetime import date, datetime
import json
import re
from zoneinfo import ZoneInfo
from .models import parse_date, now
from .quality import classify, DATE, GRANT


def assess_announcement(row, document):
    """沿用第一階段分類，僅補充官方明示的起日／徵求期間證據。"""
    result = classify(row, document)
    if result['classification'] != GRANT:
        return result
    period = result.get('application_period') or ''
    published = parse_date(row.get('announced_on'))
    if (not result.get('application_start') and published and '公告日起' in period
            and len(result['application_windows']) == 1):
        result['application_start'] = published
        result['application_windows'][0]['start_on'] = published
        result['evidence']['fields']['application_start'] = dict(value=published,
            quote=period, official_url=row['official_url'], rule='公告日起＝清單明示公告日')
    if not result.get('application_windows'):
        # 國科會詳情的欄位名稱為「徵求期間」，不當作公告日期。
        matches = list(re.finditer(r'徵求期間\s*(' + DATE + r')\s*至\s*(' + DATE + ')', document.get('body') or ''))
        if len(matches) == 1:
            m = matches[0]
            start, end = parse_date(m[1]), parse_date(m[2])
            if start and end:
                result.update(application_start=start,deadline=end,application_period=m[0],
                              application_windows=[dict(text=m[0],start_on=start,deadline=end)])
                for field,value in [('application_start',start),('deadline',end)]:
                    result['evidence']['fields'][field] = dict(value=value,quote=m[0],official_url=row['official_url'])
    return result


def application_status(assessment, as_of=None):
    """只使用官方明示的受理日期；截止日當日仍開放，未知起日不猜測。"""
    today = as_of or datetime.now(ZoneInfo('Asia/Taipei')).date()
    if isinstance(today, str):
        today = date.fromisoformat(today)
    if assessment.get('document_kind') == 'result_notice':
        return dict(status='核定結果', reason='官方核定／審查結果公告', as_of=today.isoformat())
    status, reason = '無法確認', '缺乏明確且一致的官方受理日期或企業補助分類'
    if (assessment.get('classification') == '企業補助計畫'
            and 'title_body_round_conflict' not in assessment.get('quality_flags', [])):
        windows = assessment.get('application_windows') or []
        # 多期間可能分別屬於不同方案或申請步驟，不自動選其中一個。
        if len(windows) <= 1:
            start = parse_date(assessment.get('application_start'))
            end = parse_date(assessment.get('deadline'))
            if not (start and end and start > end):
                if end and today.isoformat() > end:
                    status, reason = '已截止', '已超過官方明示截止日期'
                elif start and today.isoformat() < start:
                    status, reason = '即將開放', '尚未到官方明示開始日期'
                elif start and end and start <= today.isoformat() <= end:
                    status, reason = '開放申請', '目前日期位於官方明示受理區間（含截止日）'
    return dict(status=status, reason=reason, as_of=today.isoformat())


def plan_identity(title):
    """僅建立候選關聯；保留年度、梯次，避免不同期別被合併。"""
    year = re.search(r'(\d{3,4})年度', title)
    quoted = re.search(r'[「『]([^」』]+)[」』]', title)
    if not year or not quoted or not re.search(r'計畫|補助|獎勵', quoted[1]):
        return None
    label = re.sub(r'\s+', '', quoted[1])
    round_match = re.search(r'第[一二三四五六七八九十0-9]+梯次', title)
    key = f'{year[1]}年度:{label}:{round_match[0] if round_match else "期別未明"}'
    return key


def refresh_derived(store, assessments, as_of=None):
    db = store.db
    db.executescript('''
    CREATE TABLE IF NOT EXISTS application_states (
        announcement_id TEXT PRIMARY KEY REFERENCES announcements(id),
        source_content_hash TEXT NOT NULL, status TEXT NOT NULL,
        as_of TEXT NOT NULL, assessment_json TEXT NOT NULL, updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS plan_relations (
        left_id TEXT NOT NULL REFERENCES announcements(id),
        right_id TEXT NOT NULL REFERENCES announcements(id),
        relation TEXT NOT NULL, evidence_json TEXT NOT NULL,
        PRIMARY KEY(left_id,right_id)
    );
    ''')
    rows = store.announcements()
    with db:
        for row in rows:
            assessment = assessments[row['id']]
            state = application_status(assessment, as_of)
            data = dict(**assessment, application_state=state)
            db.execute('INSERT OR REPLACE INTO application_states VALUES (?,?,?,?,?,?)',
                       (row['id'], row['content_hash'], state['status'], state['as_of'], json.dumps(data, ensure_ascii=False), now()))
        # 重新建立可重算的候選關聯，絕不刪除或合併 announcements/source_items。
        db.execute('DELETE FROM plan_relations')
        groups = {}
        for row in rows:
            key = plan_identity(row['title'])
            if key:
                groups.setdefault(key, []).append(row)
        for key, group in groups.items():
            for i, left in enumerate(group):
                for right in group[i+1:]:
                    left_sources = {r[0] for r in db.execute('SELECT source_id FROM source_items WHERE announcement_id=?', (left['id'],))}
                    right_sources = {r[0] for r in db.execute('SELECT source_id FROM source_items WHERE announcement_id=?', (right['id'],))}
                    if left_sources == right_sources:
                        continue
                    a, b = sorted([left['id'], right['id']])
                    evidence = dict(rule='same-explicit-year-quoted-plan-and-round-v1', identity=key,
                                    titles=[left['title'], right['title']], official_urls=[left['official_url'],right['official_url']],
                                    source_content_hashes=[left['content_hash'],right['content_hash']], requires_review=True)
                    db.execute('INSERT INTO plan_relations VALUES (?,?,?,?)', (a,b,'possible_same_plan',json.dumps(evidence,ensure_ascii=False)))
    return len(db.execute('SELECT * FROM plan_relations').fetchall())


def enriched_rows(store):
    result = []
    for row in store.announcements():
        state = store.db.execute('SELECT * FROM application_states WHERE announcement_id=?', (row['id'],)).fetchone()
        if state and state['source_content_hash'] == row['content_hash']:
            assessment = json.loads(state['assessment_json'])
            row.update(application_status=state['status'], status_as_of=state['as_of'],
                       category=assessment['classification'], classification_reason=assessment['reason'],
                       classification_evidence=json.dumps(assessment.get('evidence', {}),ensure_ascii=False),
                       deadline=assessment.get('deadline') or row['deadline'])
        else:
            row.update(application_status='無法確認', classification_reason='尚未評估或原文已更新')
        row['related_announcements'] = ','.join(r[0] if r[0] != row['id'] else r[1] for r in store.db.execute(
            'SELECT left_id,right_id FROM plan_relations WHERE left_id=? OR right_id=?',(row['id'],row['id'])))
        result.append(row)
    return result
