"""全部為合成測試文字；不與正式官方公告混用，不修改既有測試。"""
import json
from pathlib import Path
import sqlite3
from dataclasses import replace
import pytest
from openpyxl import load_workbook
from grant_watch.models import Announcement
from grant_watch.quality import classify, extract_fields, GRANT, NON_GRANT, REVIEW
from grant_watch.quality_export import export_quality
from grant_watch.quality_store import QualityStore, digest_original

URL = 'https://unit.gov.tw/notices/fake'
BODY = '''一、計畫目的：本方案提供企業經費支持，鼓勵發展創新技術，依申請資格與條件提出申請。
二、申請資格：國內依法設立之公司，且不得為銀行拒絕往來戶。
三、補助額度：每案最高新臺幣100萬元，補助比例不得超過50％。
四、受理期間：自115年11月1日起至115年12月7日17時30分止。
五、申請方式：至申請網站https://apply.example.org/submit辦理。'''


def assess(title='合成企業技術方案', body=BODY, **overrides):
    row = dict(id='synthetic', title=title, official_url=URL, content=None, content_hash='fakehash')
    doc = dict(official_url=URL, http_status=200, body=body, links=[], error=None)
    doc.update(overrides)
    return classify(row, doc)


def test_grant_not_dependent_on_title_keywords():
    result = assess()
    assert result['classification'] == GRANT
    assert result['deadline'] == '2026-12-07'
    assert result['application_start'] == '2026-11-01'
    assert '國內依法設立之公司' in result['eligibility']
    assert '100萬元' in result['amount']
    assert result['application_url'] == 'https://apply.example.org/submit'
    assert result['evidence']['fields']['deadline']['quote'] in BODY


def test_general_news():
    result = assess('合成新聞：產業成果發表會', '本次成果發表會由各界來賓共同參與，現場展出多項技術成果並交流產業趨勢。活動內容僅供參考，沒有資助或申請方案。')
    assert result['classification'] == NON_GRANT
    assert result['document_kind'] == 'news_or_event'


def test_procurement_not_grant():
    result = assess('合成數位轉型補助平台採購案招標公告', '本採購案依政府採購法辦理公開招標，投標廠商應於期限內提出服務建議書，驗收通過後依契約支付價款。')
    assert result['classification'] == NON_GRANT
    assert result['document_kind'] == 'procurement'


def test_procurement_law_mentioned_in_grant_not_false_negative():
    result = assess('合成企業研發補助', BODY + '\n六、企業採購設備時應注意政府採購法相關規定。')
    assert result['classification'] == GRANT


@pytest.mark.parametrize('body', [None, '', '補助詳情請見附件。'])
def test_insufficient_information(body):
    result = assess('合成AI補助', body)
    assert result['classification'] == REVIEW
    assert result['deadline'] is None and result['amount'] is None


def test_results_related_but_not_open_program():
    result = assess('合成企業研發補助核定名單', '本次企業研發補助核定名單如下，獲選企業請依通知辦理簽約及後續管理作業。此為純結果通知，未提供新的徵件程序。')
    assert result['classification'] == NON_GRANT
    assert result['document_kind'] == 'result_notice'
    assert result['application_url'] is None


def test_association_not_assumed_company_eligibility():
    result = assess('合成補助公協會參加展覽申請須知', '本計畫提供公協會參加展覽之補助，協助業界推動貿易，受理期間自115年11月1日起至115年11月30日止。申請資格另依附件規定。')
    assert result['classification'] == REVIEW


def test_referenced_eligibility_needs_review():
    result = assess('合成展覽業務補助申請', '本項業務受理申請，申請資格須符合補助辦法第4條第1項第1款之補助對象，相關條件及補助額度請見附件作業原則。')
    assert result['classification'] == REVIEW
    assert result['amount'] is None


def test_conflicting_round_needs_review():
    body = BODY.replace('自115年11月1日', '第3梯次自115年11月1日')
    result = assess('合成第四梯次企業補助申請', body)
    assert result['classification'] == REVIEW
    assert 'title_body_round_conflict' in result['quality_flags']


def test_project_end_not_application_deadline():
    body = '''一、企業補助申請對象：國內依法設立公司，歡迎提出申請以支持技術發展。
二、受理申請期間：自115年6月1日起至115年8月31日17時止。
三、計畫執行期間：自116年1月1日起至116年12月31日止。
四、補助結案期限：受補助企業須於117年8月31日前完成結案。'''
    result = assess('合成企業補助', body)
    assert result['classification'] == GRANT
    assert result['deadline'] == '2026-08-31'
    assert len(result['application_windows']) == 1


def test_period_reference_is_not_another_window():
    result = assess(body=BODY + '\n六、申請單位應於公告受理期間內上傳文件。')
    assert len(result['application_windows']) == 1
    assert result['deadline'] == '2026-12-07'


def test_multiple_windows_do_not_choose_deadline():
    body = '''一、補助店家導入智慧轉型，企業與服務提供者依資格共同參與申請。
二、店家受理期間：115年4月20日起至116年10月20日或經費用罄止。
三、方案上架受理期間：115年10月1日起至115年10月20日17時止。
四、申請方式：店家上傳至https://apply.example.org/store；服務提供者上傳至https://apply.example.org/vendor。'''
    result = assess('合成企業智慧轉型補助', body)
    assert result['classification'] == GRANT
    assert len(result['application_windows']) == 2
    assert result['deadline'] is None and result['application_url'] is None
    assert len(result['application_links']) == 2


def test_relative_start_does_not_invent_date():
    result = assess(body=BODY.replace('自115年11月1日起', '自公告日起'))
    assert result['application_start'] is None
    assert result['deadline'] == '2026-12-07'


def test_missing_year_not_inferred():
    result = assess(body=BODY.replace('115年12月7日', '12月7日'))
    assert result['deadline'] is None


def test_unavailable_official_body_fails_closed():
    result = assess(error='robots.txt 不允許擷取')
    assert result['classification'] == REVIEW
    assert all(result[k] is None for k in ('eligibility', 'amount', 'application_period', 'deadline', 'application_url'))


def test_wrong_url_snapshot_not_accepted():
    result = assess(official_url='https://unit.gov.tw/other')
    assert result['classification'] == REVIEW
    assert result['deadline'] is None


def test_consultation_link_is_not_application_link():
    result = assess(body=BODY + '\n六、諮詢窗口：一般資訊網址https://consult.example.org/。')
    assert result['application_url'] == 'https://apply.example.org/submit'


def test_additive_storage_history_and_staleness(store, source, tmp_path):
    record = Announcement(title='合成企業補助', agency=source['agency'], government_level='central', city=None, official_url=URL)
    store.save_batch(source['id'], [record])
    rows = store.announcements()
    doc = dict(announcement_id=rows[0]['id'], official_url=URL, http_status=200, body=BODY, links=[], error=None)
    docs = {rows[0]['id']: doc}
    results = {rows[0]['id']: classify(rows[0], doc)}
    path = store.db.execute('PRAGMA database_list').fetchone()[2]
    quality = QualityStore(path)
    try:
        before = digest_original(quality.db)
        first = quality.save(rows, docs, results)
        assert quality.save(rows, docs, results) == first
        assert quality.db.execute('SELECT count(*) FROM quality_assessments').fetchone()[0] == 1
        assert digest_original(quality.db) == before
        assert quality.db.execute('SELECT is_stale FROM latest_announcement_assessments').fetchone()[0] == 0
        store.save_batch(source['id'], [replace(record, title='合成企業補助修訂')])
        assert quality.db.execute('SELECT is_stale FROM latest_announcement_assessments').fetchone()[0] == 1
        updated_rows = store.announcements()
        quality.save(updated_rows, docs, {updated_rows[0]['id']: classify(updated_rows[0], doc)})
        assert quality.db.execute('SELECT count(*) FROM quality_assessments').fetchone()[0] == 2
        assert quality.db.execute('SELECT is_stale FROM latest_announcement_assessments').fetchone()[0] == 0
    finally:
        quality.close()


def test_export_classification_and_null(tmp_path):
    grant = dict(announcement_id='fake1', title='=合成測試', official_url=URL, **assess())
    review = dict(announcement_id='fake2', title='合成資訊不足', official_url=URL, **assess(body='不足'))
    paths = export_quality([grant, review], tmp_path)
    book = load_workbook(paths['enterprise_excel'])
    sheet = book['企業補助計畫']
    assert sheet.max_row == 2
    assert sheet.cell(2, 2).value.startswith("'=")
    book.close()
    book = load_workbook(paths['all_excel'])
    assert book['全部公告'].max_row == 3 and book['待人工確認'].max_row == 2
    headers = [c.value for c in book['全部公告'][1]]
    assert book['全部公告'].cell(3, headers.index('截止日期') + 1).value is None
    book.close()


@pytest.mark.parametrize('tamper', [None, 'raw', 'body'])
def test_snapshot_integrity(tmp_path, tamper):
    import hashlib
    from grant_watch.quality_documents import load_snapshot, parse_detail
    html = '<html><title>合成測試</title><div id="divPageDetail_Content"><div class="div-left-info">合成公告內文，不是真實公告。</div></div></html>'
    raw = html.encode()
    path = tmp_path / 'fake.html'
    path.write_bytes(raw)
    title, body, links = parse_detail('https://www.moea.gov.tw/fake', html)
    doc = dict(official_url='https://www.moea.gov.tw/fake', error=None, page_title=title,
               body=body, links=links, raw_path=str(path), raw_sha256=hashlib.sha256(raw).hexdigest())
    if tamper == 'raw':
        path.write_bytes(b'changed')
    if tamper == 'body':
        doc['body'] = '與原始HTML不同的文字'
    (tmp_path / 'documents.json').write_text(json.dumps([doc]))
    if tamper:
        with pytest.raises(ValueError):
            load_snapshot(tmp_path)
    else:
        assert load_snapshot(tmp_path)[0]['body'] == body


def test_old_snapshot_cannot_refresh_changed_original():
    from grant_watch.quality_documents import validate_snapshot_inputs
    old = dict(id='fake', title='合成原始公告', official_url=URL, content_hash='old')
    with pytest.raises(ValueError, match='舊快照'):
        validate_snapshot_inputs([dict(old, content_hash='new')], [old])


def test_same_content_new_last_seen_can_replay_snapshot():
    from grant_watch.quality_documents import validate_snapshot_inputs
    old = dict(id='fake', title='合成原始公告', official_url=URL, content_hash='same', last_seen_at='before')
    validate_snapshot_inputs([dict(old, last_seen_at='after')], [old])
