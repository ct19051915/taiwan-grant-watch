"""可稽核規則分類；不修改原公告、不推論未知資格或日期。"""
import hashlib
import json
import re
from urllib.parse import urljoin, urlsplit
from .models import canonical_url, parse_date

RULE_VERSION = 'enterprise-grants-v1.1'
GRANT = '企業補助計畫'
NON_GRANT = '非補助公告'
REVIEW = '待人工確認'
DATE = r'(?:民國)?\d{3,4}年\d{1,2}月\d{1,2}日'
URL = re.compile(r'https?://[A-Za-z0-9._~:/?#\[\]@!$&\x27*+,;=%()\-]+')
TOP = re.compile(r'(?m)^[一二三四五六七八九十]{1,3}[、．.]')
PERIOD = re.compile(r'受理(?:申請)?(?:期間|時間)|申請(?:期限|期間)|店家帳號申請期間|方案上架受理期間')


def sections(body):
    if not body.strip():
        return []
    starts = list(TOP.finditer(body))
    if not starts:
        return [body]
    return [body[m.start():starts[i + 1].start() if i + 1 < len(starts) else len(body)].strip()
            for i, m in enumerate(starts)]


def application_windows(body):
    windows = []
    for section in sections(body):
        lines = section.splitlines()
        for index, line in enumerate(lines):
            if not PERIOD.search(line):
                continue
            if '執行期間' in line or '結案' in line:
                continue
            # 有些欄名與日期分行；只沿用本段，不跨入下一主條文。
            selected = line
            if not re.search(DATE, selected) and index + 1 < len(lines) and re.search(DATE, lines[index + 1]):
                selected += '\n' + lines[index + 1]
            if not re.search(DATE, selected) and not re.search(r'另行公告|隨到隨審|經費用罄', selected):
                continue
            end = re.search(r'(?:至|截止(?:日期)?[：:]?)\s*(' + DATE + ')', selected)
            start = re.search(r'(?:自|：|:)\s*(' + DATE + ')', selected)
            windows.append(dict(text=selected, start_on=parse_date(start[1]) if start else None,
                                deadline=parse_date(end[1]) if end else None))
    return list({w['text']: w for w in windows}.values())


def application_links(body, links, official_url):
    candidates = []
    for match in URL.finditer(body):
        url = match[0].rstrip(').,;')
        # 只在同一申請方式段落，或申請 URL 前緊鄰的明示文字中取值。
        headings = list(TOP.finditer(body[:match.start()]))
        section_start = headings[-1].start() if headings else 0
        context = body[max(section_start, match.start() - 150):match.start()]
        if re.search(r'申請(?:方式|網站|平台|平臺|管理系統)|官網申請|上傳至|網站[（(]網址', context):
            candidates.append((url, context[-150:] + url))
    for link in links:
        if re.search(r'申請|上傳', link.get('text', '')):
            candidates.append((urljoin(official_url, link['href']), link['text']))
    result = []
    seen = set()
    for url, text in candidates:
        try:
            url = canonical_url(url)
        except ValueError:
            continue
        if url not in seen:
            seen.add(url)
            result.append(dict(url=url, text=text))
    return result


def _round(text):
    m = re.search(r'第([0-9一二三四五六七八九十]+)梯次', text)
    if not m:
        return None
    digits = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
    return int(m[1]) if m[1].isdigit() else digits.get(m[1])


def extract_fields(body, links, official_url):
    blocks = sections(body)
    eligibility = next((s for s in blocks if re.search(r'^(?:[一二三四五六七八九十]{1,3}[、．.]\s*)?(?:申請資格|補助資格條件|補助對象|申請對象|適用對象)', s.splitlines()[0])), None)
    # 沒有專門資格段時保留明示補助對象的原文句，不依計畫名稱猜資格。
    scope_only = eligibility is None
    if eligibility is None:
        eligibility = next((line for line in body.splitlines() if re.search(r'本部補助(?:廠商|企業)|補助(?:具|國內|店家)|透過補助', line) and not line.startswith('主旨')), None)
    amount_lines = [line for line in body.splitlines()
                    if re.search(r'每案|每家|每一|上限|補助比例|補助比率|補助款不得超過', line)
                    and re.search(r'\d[\d,.，]*\s*(?:萬?元|％|%)', line)]
    amount = '\n'.join(amount_lines) or None
    windows = application_windows(body)
    urls = application_links(body, links, official_url)
    ends = {w['deadline'] for w in windows if w['deadline']}
    starts = {w['start_on'] for w in windows if w['start_on']}
    flags = ['eligibility_scope_only'] if eligibility and scope_only else []
    if len(windows) > 1:
        flags.append('multiple_application_windows')
    if len(urls) > 1:
        flags.append('multiple_application_urls')
    if not windows or not ends:
        flags.append('deadline_not_stated')
    return dict(eligibility=eligibility, amount=amount,
                application_period='\n'.join(w['text'] for w in windows) or None,
                application_start=next(iter(starts)) if len(windows) == 1 and len(starts) == 1 else None,
                deadline=next(iter(ends)) if len(windows) == 1 and len(ends) == 1 else None,
                application_url=urls[0]['url'] if len(urls) == 1 else None,
                application_windows=windows, application_links=urls, quality_flags=flags)


def classify(announcement, document):
    title = announcement['title']
    body = document.get('body') or ''
    original_url = announcement['official_url']
    usable = (not document.get('error') and document.get('http_status') == 200
              and len(body.strip()) >= 40 and document.get('official_url') == original_url)
    fields = extract_fields(body if usable else '', document.get('links', []) if usable else [], original_url)
    result = dict(classification=REVIEW, reason='官方內文不足，無法確認企業申請與資助條件',
                  document_kind='insufficient', rule_version=RULE_VERSION,
                  summary=body[:600] if usable else announcement.get('content'), **fields)
    evidence = dict(official_url=original_url, page_title=document.get('page_title'),
                    body_sha256=hashlib.sha256(body.encode()).hexdigest(),
                    raw_sha256=document.get('raw_sha256'), raw_path=document.get('raw_path'),
                    http_status=document.get('http_status'), fetched_at=document.get('fetched_at'),
                    title=title, quotes=[], fields={})
    result['evidence'] = evidence
    if document.get('error') or document.get('http_status') != 200 or len(body.strip()) < 40:
        result['quality_flags'].append('official_body_unavailable')
        result['reason'] = document.get('error') or '官方內文不足或尚未取得 HTTP 200'
        # 缺乏官方證據時不使用標題填入申請欄位。
        for key in ('eligibility', 'amount', 'application_period', 'application_start', 'deadline', 'application_url'):
            result[key] = None
        return result
    if document.get('official_url') != original_url:
        result['reason'] = '官方詳情快照與原始公告 URL 不符'
        result['quality_flags'].append('snapshot_url_mismatch')
        return result
    if re.search(r'招標|決標|採購公告|採購案', title) and re.search(r'採購|投標|政府採購法|決標', body):
        result.update(classification=NON_GRANT, document_kind='procurement', reason='政府採購或招決標，並非企業申請補助方案')
    elif re.search(r'入選名單|核定.*名單|受補助廠商名單|審查結果|獲獎名單', title) and re.search(r'入選|核定|獲選|受補助|獲補助|通過', body):
        result.update(classification=NON_GRANT, document_kind='result_notice', reason='純核定／入選／審查結果通知；與補助相關，但不是申請計畫或徵件規範')
    elif re.search(r'系統維護|徵才|職缺', title) and re.search(r'維護|人員|應徵|徵才', body):
        result.update(classification=NON_GRANT, document_kind='administration', reason='系統維護或行政人事資訊')
    else:
        support = re.search(r'補[（(]?捐?[）)]?助|獎勵|資助|經費支持', title + '\n' + body)
        business = re.search(r'公司|商號|企業|店家|商業服務業|營利事業|廠商|業者', body)
        application = re.search(r'申請|受理|資格條件', body)
        if '補助公協會' in title:
            result.update(document_kind='association_support', reason='申請主體為公協會；企業是否可直接申請需另確認，不推定企業資格')
        elif re.search(r'補助辦法第\s*4條', body) and not business:
            result.update(document_kind='referenced_eligibility', reason='資格僅引用補助辦法條款，需核對法規／附件後確認企業申請資格')
        elif support and business and application:
            result.update(classification=GRANT, document_kind='application_program', reason='官方內文明示企業或營業對象、資助措施及申請／資格資訊')
        elif re.search(r'新聞|成果發表|研討會|記者會|媒合活動', title) and (not (support and application) or re.search(r'沒有.{0,10}(?:資助|補助|申請)|不提供.{0,10}(?:補助|資助)', body)):
            result.update(classification=NON_GRANT, document_kind='news_or_event', reason='一般新聞或活動，內文未提供補助申請機制')
    title_round = _round(title)
    body_round = _round(result['application_period'] or '')
    if title_round and body_round and title_round != body_round:
        result.update(classification=REVIEW, document_kind='conflicting_round', reason='標題梯次與官方內文受理梯次不一致，需向主辦單位確認')
        result['quality_flags'].append('title_body_round_conflict')
    # 否定結果不提供看似可申請的欄位，原文及證據仍保留。
    if result['classification'] == NON_GRANT:
        for key in ('eligibility', 'amount', 'application_period', 'application_start', 'deadline', 'application_url'):
            result[key] = None
        result['application_windows'], result['application_links'], result['quality_flags'] = [], [], []
    for key in ('eligibility', 'amount', 'application_period'):
        if result.get(key):
            evidence['fields'][key] = dict(quote=result[key], official_url=original_url)
    if result['deadline']:
        evidence['fields']['deadline'] = dict(quote=result['application_period'], value=result['deadline'], official_url=original_url)
    if result['application_url']:
        evidence['fields']['application_url'] = dict(quote=result['application_links'][0]['text'], value=result['application_url'], official_url=original_url)
    # 所有判斷可回到官方全文；摘要不是 AI 生成，為原文前 600 字。
    evidence['quotes'] = [line for line in body.splitlines() if re.search(r'補助|申請|企業|公司|核定|入選|採購|新聞', line)][:6]
    if result['classification'] == GRANT:
        for key in ('eligibility', 'amount', 'application_url'):
            if result[key] is None:
                result['quality_flags'].append(key + '_not_stated')
    result['quality_flags'] = list(dict.fromkeys(result['quality_flags']))
    result['input_hash'] = hashlib.sha256(json.dumps(dict(title=title, url=original_url,
        source_content_hash=announcement.get('content_hash'), body=body, links=document.get('links', [])), ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    return result
