"""官方詳情留存；沿用原 HTTP client、robots、TLS 與限速。"""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from .http import Client
from .models import now

SELECTORS = {
    'www.moea.gov.tw': '#divPageDetail_Content .div-left-info',
    'www.sme.gov.tw': '.mainContent .contentGroup .floatBox',
}


def parse_detail(url, text):
    soup = BeautifulSoup(text, 'html.parser')
    title = soup.title.get_text(' ', strip=True) if soup.title else None
    selector = SELECTORS.get(urlsplit(url).hostname)
    node = soup.select_one(selector) if selector else None
    if node is None:
        raise ValueError('找不到已知官方詳情內文節點')
    for hidden in node.select('script,style,noscript'):
        hidden.decompose()
    links = [dict(text=a.get_text(' ', strip=True), href=a['href']) for a in node.select('a[href]')]
    for br in node.select('br'):
        br.replace_with('\n')
    body = '\n'.join(line.strip() for line in node.get_text('\n', strip=True).splitlines() if line.strip()) or None
    if not body:
        raise ValueError('官方詳情內文為空')
    return title, body, links


def load_snapshot(directory):
    documents = json.loads((Path(directory) / 'documents.json').read_text())
    for document in documents:
        if document.get('error'):
            continue
        raw = Path(document['raw_path']).read_bytes()
        if hashlib.sha256(raw).hexdigest() != document['raw_sha256']:
            raise ValueError('官方快照原始檔 SHA-256 不符')
        title, body, links = parse_detail(document.get('fetched_url', document['official_url']),
                                          raw.decode(document.get('encoding') or 'utf-8-sig'))
        if body != document['body'] or links != document['links'] or title != document['page_title']:
            raise ValueError('官方快照解析內容與原始 HTML 不符')
    return documents


def fetch_documents(rows, directory, client=None):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    client = client or Client()
    documents = []
    for index, row in enumerate(rows, 1):
        document = dict(announcement_id=row['id'], official_url=row['official_url'],
                        fetched_at=now(), http_status=None, body=None, links=[], error=None,
                        raw_path=None, raw_sha256=None, page_title=None)
        try:
            response = client.get(row['official_url'])
            document['http_status'] = response.status_code
            document['fetched_url'] = response.url
            path = directory / (row['id'] + '.html')
            path.write_bytes(response.content)
            document.update(raw_path=str(path), raw_sha256=hashlib.sha256(response.content).hexdigest())
            if response.encoding is None or response.encoding.lower() == 'iso-8859-1':
                response.encoding = response.apparent_encoding
            document['encoding'] = response.encoding
            title, body, links = parse_detail(response.url, response.text)
            document.update(page_title=title, body=body, links=links)
        except Exception as exc:
            document['error'] = str(exc)
        documents.append(document)
        print(f"[{index}/{len(rows)}] {document['http_status']} {row['official_url']} {document['error'] or 'OK'}", flush=True)
        (directory / 'documents.json').write_text(json.dumps(documents, ensure_ascii=False, indent=2) + '\n')
    return documents


def validate_snapshot_inputs(rows, originals):
    old = {row['id']: row for row in originals}
    if len(old) != len(originals) or set(old) != {row['id'] for row in rows}:
        raise ValueError('官方快照與目前公告集合不一致；請重新擷取')
    for row in rows:
        if any(row.get(key) != old[row['id']].get(key) for key in ('title', 'official_url', 'content_hash')):
            raise ValueError('原始公告已更新，不能以舊快照當作新評估；請重新擷取')
