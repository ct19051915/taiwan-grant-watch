"""Read-only Traditional Chinese grant announcement browser."""
import os
from pathlib import Path
from urllib.parse import urlsplit

import streamlit as st
from grant_watch.coverage import coverage_rows, coverage_summary
from grant_watch.service import load_sources
from grant_watch.topics import RULES
from grant_watch.web_query import DataError, filter_announcements, read_report, read_snapshot, taipei_time

st.set_page_config(page_title='台灣政府企業補助公告', page_icon='📋', layout='wide')
st.title('台灣政府企業補助公告')
st.caption('官方公告查詢｜規則式分類僅供查詢參考，申請請以官方最新公告為準。')


def display(value):
    return str(value) if value not in (None, '', [], {}) else '官方未提供'


def link(label, url):
    try:
        parsed = urlsplit(url or '')
        if parsed.scheme in ('https', 'http') and parsed.netloc:
            st.link_button(label, url)
            return
    except ValueError:
        pass
    st.text(label + '：待確認')


def choose(label, rows, key):
    return st.sidebar.selectbox(label, [None] + sorted({r.get(key) or '待確認' for r in rows}),
                                format_func=lambda v: '全部' if v is None else v)


# Secrets are consumed only on the server; no token enters rendered data or logs.
import hashlib
import logging
from grant_watch.cloud_data import SnapshotCache, config_from_secrets

logger = logging.getLogger(__name__)


@st.cache_resource(show_spinner=False)
def cloud_cache(repository, credential_key, ttl, _config):
    return SnapshotCache(_config)


cloud = None
refresh = st.sidebar.button('重新讀取資料')
try:
    try:
        cloud_config = config_from_secrets(st.secrets)
    except FileNotFoundError:
        cloud_config = None
    if cloud_config is not None:
        cloud = cloud_cache(cloud_config.repository, hashlib.sha256(cloud_config.token.encode()).hexdigest(), cloud_config.ttl, cloud_config).load(force=refresh)
        snapshot = read_snapshot(cloud['path'])
        if cloud['warning']:
            st.error(cloud['warning'])
        st.caption('最後成功保存：' + taipei_time(cloud['report']['completed_at']))
        st.caption('資料版本：' + cloud['sha'][:12] + '｜自動檢查間隔：' + str(cloud_config.ttl) + ' 秒')
    else:
        snapshot = read_snapshot(os.environ.get('GRANT_DB_PATH', 'var/grants.sqlite3'))
except (DataError, ValueError, TypeError):
    logger.warning("cloud_data ui_failed stage=config_or_snapshot category=validation")
    st.error('無法讀取資料。雲端請檢查 Streamlit Secrets 與私人來源權限；本機請依 docs/windows-web.md 準備既有資料庫。')
    st.stop()
for warning in snapshot['warnings']:
    st.warning(warning)
rows = snapshot['announcements']
st.sidebar.header('搜尋與篩選')
keyword = st.sidebar.text_input('關鍵字（名稱、機關、原文）')
government = choose('中央／地方政府', rows, 'government_label')
city = choose('縣市', rows, 'city')
industry = choose('產業類別', rows, 'industry')
st.sidebar.caption('產業僅採用資料庫既有類別；未提供時顯示待確認。')
topics = st.sidebar.multiselect('補助主題（可複選）', list(RULES))
status = choose('申請狀態', rows, 'application_status')
open_only = st.sidebar.checkbox('僅顯示目前開放申請的補助')
filtered = filter_announcements(rows, keyword, government, city, industry, status, open_only)
filtered = [r for r in filtered if not topics or set(topics).intersection(r.get('topics', []))]
latest = max((r.get('updated_at') or '' for r in rows), default='')
st.caption('最後資料更新：' + taipei_time(latest))
overview, updates = st.tabs(['公告總覽', '每日更新與來源涵蓋'])
with overview:
    st.write(f'符合條件 {len(filtered)} 則／全部 {len(rows)} 則公告')
    if not filtered:
        st.info('目前沒有符合條件的公告。')
    # Bounded rendering for desktop and mobile; no raw HTML from external content.
    page = st.number_input('頁碼（每頁 20 則）', min_value=1, max_value=max(1, (len(filtered) + 19) // 20), step=1)
    for row in filtered[(page-1)*20:page*20]:
        a = row['assessment']
        with st.expander(f"{display(row.get('title'))} ｜ {row['application_status']}"):
            st.text('分類：' + row['classification'])
            st.text('補助主題：' + ('、'.join(row.get('topics', [])) or '待確認'))
            st.text('主辦機關：' + display(row.get('agency')))
            st.text(row['government_label'] + ' ｜ 縣市：' + (row.get('city') or '待確認'))
            st.text('公告日期：' + display(row.get('announced_on')))
            for label, key in [('補助目的／官方節錄', 'summary'), ('補助金額或比例', 'amount'), ('申請資格', 'eligibility'), ('申請期間', 'application_period'), ('申請開始日', 'application_start'), ('申請截止日', 'deadline')]:
                st.text(label + '：' + display(a.get(key)))
            st.text('狀態依據：' + row['status_reason'])
            st.text('最後資料更新：' + taipei_time(row.get('updated_at')))
            link('開啟官方公告', row.get('official_url'))
            st.text('原始公告內容：' + display(row.get('content')))
            st.write('來源證據與分類依據')
            st.json(dict(source_validation_status=row.get('source_validation_status', '待確認'),
                         reason=a.get('reason', '待確認'), evidence=a.get('evidence', {}),
                         application_windows=a.get('application_windows', []), document=row['document']))
with updates:
    report_path = os.environ.get('GRANT_REPORT_PATH', str(Path(os.environ.get('GRANT_DB_PATH', 'var/grants.sqlite3')).with_name('latest-report.json')))
    report, warning = (cloud['report'], None) if cloud else read_report(report_path)
    if warning:
        st.warning(warning)
    st.text('報告狀態：' + display(report.get('status')))
    successful = report.get('status') == 'success' and report.get('published') is True
    last_success = max((s.get('last_success_at') or '' for s in snapshot['sources']), default='')
    st.text('最後成功抓取時間：' + taipei_time(report.get('completed_at') if successful else last_success))
    st.text('本次新增：' + display(report.get('inserted')) + '；更新：' + display(report.get('updated')))
    if report and not successful:
        st.warning('本次報告未確認成功保存；新增／更新數為候選寫入次數。')
    st.caption('grant-data 僅保存成功快照；失敗的每日執行須查看 GitHub Actions 報告，不能由成功快照推論後續執行成功。')
    source_report = report.get('sources') if isinstance(report.get('sources'), dict) else {}
    for source in snapshot['sources']:
        config = source['config']
        detail = source_report.get(source['id'])
        st.text(f"{display(config.get('agency'))}（{source['id']}）｜驗證：{display(source.get('validation_status'))}｜最近抓取：{display(source.get('last_outcome'))}")
        st.text('最後成功：' + taipei_time(source.get('last_success_at')))
        if detail is not None:
            st.json(detail)
        if source.get('last_error'):
            st.text('錯誤：' + str(source['last_error']))
    st.subheader('來源涵蓋範圍')
    st.info('僅涵蓋上列來源及其已追蹤公告，並非全台政府補助清單。驗證來源不等於公告已確認為企業補助。')
    catalog = load_sources(Path(__file__).parent / 'data/phase-eight-sources.json')
    coverage = coverage_rows(catalog, snapshot['sources'])
    summary = coverage_summary(coverage)
    st.caption('涵蓋率＝已啟用且目前資料庫曾成功抓取的名冊來源／名冊來源數。中央分母僅為本批盤點機關，非全部中央機關；地方分母為 22 縣市。')
    for level, label in [('central', '中央候選機關'), ('local', '22 縣市政府')]:
        counts = summary[level]
        st.metric(label + '涵蓋率', f"{counts['verified']}/{counts['total']}",
                  help='已啟用 ' + str(counts['enabled']) + ' 個；成功不代表目前所有補助均已收錄。')
    st.dataframe([dict(機關=r['agency'], 官方網址=r['url'], 蒐集方式=r['method'],
                       已啟用=r['enabled'], 曾成功抓取=r['verified'], 公告數=r['announcement_count'],
                       最近結果=r['last_outcome'], 尚未支援原因=r['reason']) for r in coverage],
                 hide_index=True, width='stretch')
    st.caption('公告數採來源關聯的不同公告數；同一公告可屬多個來源，故不可直接相加。未啟用來源的 0 筆不表示沒有補助。')

if cloud:
    @st.fragment(run_every=cloud_config.ttl)
    def poll_updates():
        import time
        cache = cloud_cache(cloud_config.repository, hashlib.sha256(cloud_config.token.encode()).hexdigest(), cloud_config.ttl, cloud_config)
        if cache.checked is not None and time.monotonic() - cache.checked >= cloud_config.ttl:
            st.rerun()
    poll_updates()
