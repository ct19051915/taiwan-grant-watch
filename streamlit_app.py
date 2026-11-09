"""Local-only Traditional Chinese grant announcement browser."""
import os
from pathlib import Path
from urllib.parse import urlsplit

import streamlit as st
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


if st.sidebar.button('重新讀取本機資料'):
    st.rerun()
try:
    snapshot = read_snapshot(os.environ.get('GRANT_DB_PATH', 'var/grants.sqlite3'))
except DataError as exc:
    st.error(str(exc))
    st.info('請依 docs/windows-web.md 準備既有資料庫；網頁不會建立空白資料庫。')
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
status = choose('申請狀態', rows, 'application_status')
open_only = st.sidebar.checkbox('僅顯示目前開放申請的補助')
filtered = filter_announcements(rows, keyword, government, city, industry, status, open_only)
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
    report, warning = read_report(report_path)
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
    st.text('尚未涵蓋：未列於上方的中央部會、所屬機關、縣市與鄉鎮市區公所；未建立完整機關名冊，無法宣稱已全面涵蓋。')
