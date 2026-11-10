"""實網驗證 27 個候選，保留 robots/授權/清單/詳情證據；不使用測試 fixture。

python -m scripts.verify_phase_two [--sources ...] [--output var/phase-two]
多站並行、同站序列；沿用 TLS、robots、3 秒限速及 5MB 上限。
"""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urlsplit
from bs4 import BeautifulSoup
from grant_watch.extractors import EXTRACTORS
from grant_watch.http import Client, FetchError
from grant_watch.models import Announcement, now, parse_date
from grant_watch.phase_two import assess_announcement, refresh_derived, enriched_rows
from grant_watch.export import export_rows
from grant_watch.service import load_sources
from grant_watch.storage import Store


class EvidenceClient(Client):
    def __init__(self, directory, budget_seconds=None, max_requests=None):
        super().__init__(attempts=1)
        self.directory = directory
        self.events = []
        self.deadline = time.monotonic() + budget_seconds if budget_seconds else None
        self.max_requests = max_requests

    def _request(self, url, interval=None):
        if ((self.deadline is not None and time.monotonic() >= self.deadline)
                or (self.max_requests is not None and len(self.events) >= self.max_requests)):
            raise FetchError('本批次請求／時間預算已用盡；保留上次成功快照')
        event = dict(url=url, checked_at=now())
        self.events.append(event)
        try:
            response = super()._request(url, interval)
            path = self.directory / f'{len(self.events):03d}.bin'
            path.write_bytes(response.content)
            event.update(http_status=response.status_code, sha256=hashlib.sha256(response.content).hexdigest(),
                         raw_path=str(path), content_type=response.headers.get('Content-Type'))
            return response
        except FetchError as exc:
            event['error'] = str(exc)
            raise


def read_page(client, url):
    response = client.get(url)
    if response.encoding is None or response.encoding.lower() == 'iso-8859-1':
        response.encoding = response.apparent_encoding
    return response


def parse_document(row, source, response, event):
    soup = BeautifulSoup(response.text, 'html.parser')
    node = soup.select_one(source['detail_selector'])
    if node is None:
        raise ValueError('找不到已設定官方詳情節點；需重新審查 selector')
    for selector in source.get('detail_exclude_selectors', []):
        for excluded in node.select(selector):
            excluded.decompose()
    for hidden in node.select('script,style,noscript'):
        hidden.decompose()
    links = [dict(text=a.get_text(' ',strip=True),href=a['href']) for a in node.select('a[href]')]
    for br in node.select('br'):
        br.replace_with('\n')
    body = '\n'.join(line for line in node.get_text('\n',strip=True).splitlines()
                     if not any(re.fullmatch(pattern, line.strip())
                                for pattern in source.get('detail_ignored_line_patterns', [])))
    return dict(official_url=row['official_url'], http_status=response.status_code,
                page_title=soup.title.get_text(' ',strip=True) if soup.title else None,
                body=body,links=links,error=None,
                fetched_at=event['checked_at'],raw_sha256=event['sha256'],raw_path=event['raw_path'])


def verify_source(source, directory, client):
    record = dict(id=source['id'],candidate_id=source.get('candidate_id',source['id']),agency=source['agency'],
                  url=source['url'],checked_at=now(),status='pending',error=None,announcements=[],documents={},events=[])
    record['config_sha256'] = hashlib.sha256(json.dumps(source,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    start = len(client.events)
    items = []
    try:
        response = read_page(client, source['url'])
        record['listing_http_status'] = response.status_code
        if not source.get('terms_reviewed'):
            if source.get('terms_url'):
                read_page(client,source['terms_url'])
            record['error'] = '尚未完成可存取的授權條款審查或企業公告端點設定'
        else:
            terms = read_page(client,source['terms_url'])
            text = BeautifulSoup(terms.text,'html.parser').get_text(' ',strip=True)
            # 除既有人工審查外，重新確認授權頁仍含授權與出處敘述。
            government_license = '授權' in text and '出處' in text
            cc0_license = '公眾領域貢獻宣告' in text and 'CC0 1.0' in text
            if not (government_license or cc0_license):
                raise ValueError('授權頁內容改變，待重新人工審查')
            record['terms_url'] = source['terms_url']
            record['terms_excerpt'] = text[max(0,text.find('授權方式')):text.find('授權方式')+800] if '授權方式' in text else text[:800]
            items = EXTRACTORS[source['method']]().parse(source,response.text)
            if items or source.get('allow_empty', False):
                record['status']='verified'
                record['announcements']=[asdict(item) for item in items]
                for item in items:
                    row = item.normalized()
                    detail = None
                    try:
                        detail = read_page(client,item.official_url)
                        record['documents'][row['official_url']] = parse_document(row,source,detail,client.events[-1])
                        # 只依該站已驗證 selector 擷取詳情日期，不使用更新日或申請日替代。
                        detail_soup = BeautifulSoup(detail.text, 'html.parser')
                        for field in ('announced_on',):
                            selector = source.get('detail_fields', {}).get(field + '_selector')
                            node = detail_soup.select_one(selector) if selector else None
                            if node is not None:
                                setattr(item, field, parse_date(node.get_text(' ', strip=True)))
                        document = record['documents'][row['official_url']]
                        item.content = document['body']
                        fields = assess_announcement(item.normalized(), document)
                        for field in ('deadline', 'amount', 'eligibility'):
                            setattr(item, field, fields.get(field))
                    except Exception as exc:
                        record['documents'][row['official_url']] = dict(official_url=row['official_url'],
                            http_status=detail.status_code if detail is not None else None,
                            body=None,links=[],error=str(exc))
            else:
                record['error']='端點可連線及解析，但本頁／RSS 未取得補助關鍵字公告；不代表機關沒有補助'
    except Exception as exc:
        message = str(exc)
        # 權限／規範未知留待確認，明確 HTTP、格式或 robots 禁止則 failed。
        record['status'] = 'pending' if any(x in message for x in ['proxy CONNECT','TLS','robots.txt HTTP','robots.txt 回傳 HTML','尚未','授權頁']) else 'failed'
        record['error'] = message
    record['announcements'] = [asdict(item) for item in items]
    record['events']=client.events[start:]
    record['announcement_count']=len(items)
    saved = directory / (source['id'] + '-result.json')
    if saved.exists():
        history = directory / 'history'
        history.mkdir(exist_ok=True)
        (history / (source['id'] + '-' + now().replace(':','').replace('+','_') + '.json')).write_text(saved.read_text())
    saved.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    print(f"{source['id']}: {record['status']} {len(items)} {record['error'] or ''}",flush=True)
    return record,items


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources',default='data/phase-two-sources.json')
    parser.add_argument('--output',default='var/phase-two')
    parser.add_argument('--resume',help='沿用此目錄已完成且設定雜湊相同的逐站結果；保留原檢查時間')
    parser.add_argument('--retry-source',action='append',default=[],help='resume 時重新驗證指定來源，可重複')
    args=parser.parse_args()
    directory=Path(args.resume) if args.resume else Path(args.output)/now().replace(':','').replace('+','_')
    directory.mkdir(parents=True,exist_ok=bool(args.resume))
    sources=load_sources(args.sources)
    groups=defaultdict(list)
    for source in sources:groups[urlsplit(source['url']).netloc].append(source)
    def group_worker(group):
        path=directory/(group[0]['id']+'-'+now().replace(':','').replace('+','_'));path.mkdir()
        client=EvidenceClient(path)
        results=[]
        for source in group:
            saved=directory/(source['id']+'-result.json')
            digest=hashlib.sha256(json.dumps(source,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            if args.resume and saved.exists() and source['id'] not in args.retry_source:
                record=json.loads(saved.read_text())
                if record.get('config_sha256')==digest:
                    results.append((record,[Announcement(**item) for item in record['announcements']]))
                    continue
            results.append(verify_source(source,directory,client))
        return results
    records=[]
    with ThreadPoolExecutor(max_workers=8) as pool:
        for group in pool.map(group_worker,groups.values()):records.extend(group)
    store=Store(directory/'grants.sqlite3')
    store.sync_sources(sources)
    documents={};results={}
    try:
        for record,items in records:
            if record['status']=='verified':
                record['first_run']=store.save_batch(record['id'],items)
                record['replay']=store.save_batch(record['id'],items)
                documents.update(record['documents'])
            results[record['id']]=record
        rows=store.announcements()
        for record,_ in records:
            record['stored_announcement_count'] = store.db.execute(
                'SELECT count(DISTINCT announcement_id) FROM source_items WHERE source_id=?',(record['id'],)).fetchone()[0]
        assessments={row['id']:assess_announcement(row,documents.get(row['official_url'],dict(error='無官方詳情'))) for row in rows}
        relations=refresh_derived(store,assessments)
        enriched=enriched_rows(store)
        store.db.execute('''CREATE TABLE IF NOT EXISTS source_checks (
            source_id TEXT PRIMARY KEY REFERENCES sources(id), status TEXT NOT NULL,
            checked_at TEXT NOT NULL, evidence_json TEXT NOT NULL)''')
        with store.db:
            for record,_ in records:
                store.db.execute('INSERT OR REPLACE INTO source_checks VALUES (?,?,?,?)',
                                 (record['id'],record['status'],record['checked_at'],json.dumps(record,ensure_ascii=False)))
                store.db.execute('UPDATE sources SET validation_status=?,last_checked_at=?,last_outcome=?,last_error=? WHERE id=?',
                                 (record['status'],record['checked_at'],record['status'],record['error'],record['id']))
        export_rows(enriched,directory/'announcements.xlsx')
        export_rows(enriched,directory/'announcements.csv')
        import csv
        from openpyxl import load_workbook
        with (directory/'announcements.csv').open(encoding='utf-8-sig',newline='') as handle:
            csv_rows=list(csv.DictReader(handle))
        book=load_workbook(directory/'announcements.xlsx',read_only=True)
        try:
            sheet=list(book.active.values)
        finally:
            book.close()
        expected={r['official_url'] for r in rows}
        export_check=(len(csv_rows)==len(rows)==len(sheet)-1
            and {r['official_url'] for r in csv_rows}==expected
            and {r[sheet[0].index('official_url')] for r in sheet[1:]}==expected)
        if not export_check:
            raise RuntimeError('匯出讀回筆數或官方網址不一致')
        report=dict(started_at=directory.name,completed_at=now(),sources=results,announcement_count=len(rows),
                    classifications={label:sum(a['classification']==label for a in assessments.values()) for label in ['企業補助計畫','非補助公告','待人工確認']},
                    application_statuses={label:sum(r.get('application_status')==label for r in enriched) for label in ['開放申請','即將開放','已截止','核定結果','無法確認']},
                    plan_relations=relations,announcements=enriched,assessments=assessments,export_roundtrip=export_check,
                    integrity_check=store.db.execute('PRAGMA integrity_check').fetchone()[0])
        report_path = directory/'report.json'
        if report_path.exists():
            history=directory/'history'
            history.mkdir(exist_ok=True)
            (history/('report-'+now().replace(':','').replace('+','_')+'.json')).write_text(report_path.read_text())
        report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(json.dumps(dict(report_file=str(directory/'report.json'),announcement_count=len(rows),classifications=report['classifications'],application_statuses=report['application_statuses']),ensure_ascii=False),flush=True)
    finally:store.close()


if __name__=='__main__':main()
