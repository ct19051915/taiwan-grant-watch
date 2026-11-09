"""實際官方來源驗證；沿用現有擷取與儲存流程，不使用合成公告。

執行：python -m scripts.verify_official_sources
產物：var/verification/<UTC時間>/report.json、原始回應、真實公告 CSV/XLSX。
內容更新以真實清單與詳情的差異，在隔離資料庫重播；不是官網歷史改版證據。
"""
import csv
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from bs4 import BeautifulSoup
from openpyxl import load_workbook

from grant_watch.export import export_rows
from grant_watch.extractors import EXTRACTORS
from grant_watch.http import Client, FetchError
from grant_watch.models import now
from grant_watch.service import collect, load_sources
from grant_watch.storage import Store


def failure_category(message):
    if 'proxy CONNECT 403' in message:
        return 'proxy_denied'
    if 'TLS' in message:
        return 'tls_error'
    if 'robots.txt 不允許' in message:
        return 'robots_disallowed'
    if 'robots.txt' in message:
        return 'robots_unavailable'
    if 'HTTP' in message or 'connection failed' in message:
        return 'http_or_connection_error'
    return 'parse_or_configuration_error'


class AuditedClient(Client):
    def __init__(self, directory):
        super().__init__()
        self.directory, self.events, self.documents = directory, [], {}

    def _request(self, url, interval=None):
        event = dict(checked_at=now(), url=url)
        self.events.append(event)
        try:
            response = super()._request(url, interval)
        except FetchError as exc:
            event.update(http_status=None, failure_category=failure_category(str(exc)), error=str(exc))
            raise
        path = self.directory / f'response-{len(self.events):03d}.bin'
        path.write_bytes(response.content)
        event.update(http_status=response.status_code, bytes=len(response.content),
                     sha256=hashlib.sha256(response.content).hexdigest(),
                     response_file=str(path), content_type=response.headers.get('Content-Type'))
        self.documents[url] = response
        return response


def verify_update(store, sources, client, directory):
    """真實公告清單→真實官方詳情，隔離檔案不混入正式公告資料庫。"""
    source = next(s for s in sources if s['id'] == 'sme-business')
    listing = client.documents[source['url']]
    items = EXTRACTORS[source['method']]().parse(source, listing.text)
    target_url = 'https://www.sme.gov.tw/article-tw-2275-15216'
    item = next((i for i in items if i.official_url == target_url), None)
    if item is None:
        return dict(passed=False, reason='指定的真實公告已不在清單第一頁；需選擇新的詳情對照樣本')
    detail = client.get(target_url)
    detail.encoding = 'utf-8'
    node = BeautifulSoup(detail.text, 'html.parser').select_one('.mainContent .contentGroup .floatBox')
    if node is None:
        return dict(passed=False, reason='詳情頁內文 selector 已改變')
    content = node.get_text(' ', strip=True)
    if not content or '企業跨域研發補助' not in content:
        return dict(passed=False, reason='詳情內容與預期計畫不符')
    snapshot = directory / 'update-replay.sqlite3'
    # SQLite backup 保留全部正式資料；只在副本驗證內容變更。
    with sqlite3.connect(snapshot) as destination:
        store.db.backup(destination)
    replay = Store(snapshot)
    try:
        before = next(r for r in replay.announcements() if r['official_url'] == target_url)
        count_before = len(replay.announcements())
        enriched = replace(item, content=content)
        changed = replay.save_batch(source['id'], [enriched])
        after = next(r for r in replay.announcements() if r['official_url'] == target_url)
        repeated = replay.save_batch(source['id'], [enriched])
        passed = (changed == dict(inserted=0, updated=1, unchanged=0)
                  and repeated == dict(inserted=0, updated=0, unchanged=1)
                  and before['id'] == after['id']
                  and before['fetched_at'] == after['fetched_at']
                  and before['content_hash'] != after['content_hash']
                  and after['updated_at'] > before['updated_at']
                  and len(replay.announcements()) == count_before)
        return dict(passed=passed, mode='isolated_real_listing_to_real_detail_enrichment',
                    website_historical_change_observed=False, official_url=target_url,
                    detail_http_status=detail.status_code, isolated_db=str(snapshot),
                    changed=changed, repeat=repeated, same_id=before['id'] == after['id'],
                    before_hash=before['content_hash'], after_hash=after['content_hash'],
                    before_updated_at=before['updated_at'], after_updated_at=after['updated_at'],
                    production_unchanged=True)
    finally:
        replay.close()


def main():
    directory = Path('var/verification') / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    directory.mkdir(parents=True)
    sources = load_sources('data/active-sources.json')
    store = Store('var/grants.sqlite3')
    client = AuditedClient(directory)
    report = dict(started_at=now(), production_db='var/grants.sqlite3', sources={}, http_events=client.events)
    try:
        with sqlite3.connect(directory / 'before.sqlite3') as destination:
            store.db.backup(destination)
        first = collect(store, sources, client)
        count_after_first = len(store.announcements())
        second = collect(store, sources, client)
        rows = store.announcements()
        for source in sources:
            sid = source['id']
            count = store.db.execute('SELECT count(DISTINCT announcement_id) FROM source_items WHERE source_id=?', (sid,)).fetchone()[0]
            events = [e for e in client.events if e['url'] == source['url']]
            error = first[sid].get('error') or second[sid].get('error')
            report['sources'][sid] = dict(url=source['url'], agency=source['agency'],
                source_http_status=events[-1].get('http_status') if events else None,
                first_run=first[sid], second_run=second[sid], stored_announcements=count,
                failure_reason=error, failure_category=failure_category(error) if error else None,
                repeat_no_insert=second[sid].get('inserted') == 0 and not error)
        report['announcement_count'] = len(rows)
        report['repeat_count_unchanged'] = count_after_first == len(rows)
        try:
            report['content_update_verification'] = verify_update(store, sources, client, directory)
        except Exception as exc:
            report['content_update_verification'] = dict(passed=False, reason=str(exc))
        export_rows(rows, directory / 'announcements.csv')
        export_rows(rows, directory / 'announcements.xlsx')
        export_rows(rows, 'var/announcements.csv')
        export_rows(rows, 'var/announcements.xlsx')
        with (directory / 'announcements.csv').open(encoding='utf-8-sig', newline='') as handle:
            csv_rows = list(csv.DictReader(handle))
        book = load_workbook(directory / 'announcements.xlsx', read_only=True)
        try:
            values = list(book.active.values)
        finally:
            book.close()
        url_column = values[0].index('official_url')
        expected = {r['official_url'] for r in rows}
        report['exports'] = dict(csv=str(directory / 'announcements.csv'), xlsx=str(directory / 'announcements.xlsx'),
            rows=len(rows), passed=bool(rows) and len(csv_rows) == len(rows) == len(values)-1
            and {r['official_url'] for r in csv_rows} == expected
            and {r[url_column] for r in values[1:]} == expected)
        report['completed_at'] = now()
        report['passed'] = (len(report['sources']) >= 2
            and all(s['repeat_no_insert'] and s['stored_announcements'] > 0 for s in report['sources'].values())
            and report['repeat_count_unchanged'] and report['exports']['passed']
            and report['content_update_verification']['passed'])
        (directory / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps(dict(report_file=str(directory / 'report.json'), **{k: v for k, v in report.items() if k != 'http_events'}), ensure_ascii=False, indent=2))
        return 0 if report['passed'] else 1
    finally:
        store.close()


if __name__ == '__main__':
    raise SystemExit(main())
