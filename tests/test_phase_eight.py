"""第八階段合成回歸測試；實網結果另見 docs，不冒充官方資料。"""
from dataclasses import replace
import json
from pathlib import Path
import pytest
from grant_watch.coverage import coverage_rows, coverage_summary
from grant_watch.extractors import HtmlExtractor, RssExtractor
from grant_watch.http import FetchError
from grant_watch.service import collect, load_sources
from grant_watch.storage import Store
from grant_watch.topics import classify_topics
from scripts.verify_phase_two import EvidenceClient
from test_storage import item


def test_catalog_preserves_existing_and_has_22_local():
    catalog = load_sources('data/phase-eight-sources.json')
    old = load_sources('data/phase-two-sources.json')
    assert {s['id'] for s in old if s['validation_status'] == 'verified'} <= {s['id'] for s in catalog if s['enabled']}
    local = [s for s in catalog if s['government_level'] == 'local']
    assert len(local) == len({s['city'] for s in local}) == 22
    assert 5 < sum(s['enabled'] for s in catalog) <= 8
    assert all(s.get('unsupported_reason') for s in catalog if not s['enabled'])


def test_accordion_permalink_and_unknown_fields(source):
    source['parser'] = dict(item_selector='.item', link_selector='a', title_selector='button',
                            link_pattern=r'#qaH(?P<id>\d+)', link_template='https://unit.gov.tw/news/{id}')
    html = '<div class="item"><button>合成企業補助</button><a href="#qaH123">複製</a></div>'
    a = HtmlExtractor().parse(source, html)[0]
    assert a.official_url == 'https://unit.gov.tw/news/123'
    assert a.title == '合成企業補助'
    assert a.deadline is a.amount is a.eligibility is a.announced_on is None
    with pytest.raises(FetchError, match='識別碼'):
        HtmlExtractor().parse(source, html.replace('#qaH123', '#changed123'))


def test_datetime_attribute(source):
    source['parser'] = dict(item_selector='li', link_selector='a', announced_on_selector='time', announced_on_attribute='datetime')
    a = HtmlExtractor().parse(source, '<li><a href="/x">合成補助</a><time datetime="2026-11-10">今日</time></li>')[0]
    assert a.normalized()['announced_on'] == '2026-11-10'


def test_rss_namespaced_content_and_date(source):
    xml = '''<rss xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:content="http://purl.org/rss/1.0/modules/content/">
    <channel><item><title>合成補助</title><link>https://unit.gov.tw/x</link><dc:date>2026-11-10</dc:date>
    <description>短摘要</description><content:encoded>&lt;p&gt;合成完整原文&lt;/p&gt;</content:encoded></item></channel></rss>'''
    a = RssExtractor().parse(source, xml)[0]
    assert a.content == '合成完整原文' and a.normalized()['announced_on'] == '2026-11-10'


def test_history_replay_update_and_absence(store, source):
    a = item()
    store.save_batch(source['id'], [a])
    store.save_batch(source['id'], [a])
    store.save_batch(source['id'], [replace(a, amount='合成變更')])
    store.save_batch(source['id'], [])
    versions = [json.loads(r[0]) for r in store.db.execute('SELECT snapshot_json FROM announcement_versions ORDER BY id')]
    assert len(versions) == 2 and versions[0]['amount'] == a.amount
    assert versions[1]['amount'] == '合成變更'
    assert len(store.announcements()) == 1
    assert len({r['id'] for r in versions}) == 1


def test_history_existing_database_migration(tmp_path, source):
    path = tmp_path/'old.sqlite3'
    db = Store(path); db.sync_sources([source]); db.save_batch(source['id'], [item()])
    db.db.execute('DROP TABLE announcement_versions'); db.close()
    db = Store(path)
    db.save_batch(source['id'], [replace(item(), amount='合成修改')])
    assert db.db.execute('SELECT count(*) FROM announcement_versions').fetchone()[0] == 2
    db.close()


def test_history_atomic_rollback(store, source):
    before = len(store.announcements())
    with pytest.raises(ValueError):
        store.save_batch(source['id'], [item(), replace(item(), title='')])
    assert len(store.announcements()) == before
    assert store.db.execute('SELECT count(*) FROM announcement_versions').fetchone()[0] == 0


def test_topics_multilabel_and_no_ai_substring():
    tags = classify_topics('合成AI智慧製造數位轉型節能研發補助', {})
    assert set(tags) == {'AI','智慧製造','數位轉型','節能減碳','研發創新'}
    assert classify_topics('Taiwan mail campaign', {}) == {}
    assert classify_topics('合成補助', dict(error='無法取得',body='AI',http_status=200)) == {}


def test_coverage_denominator_and_unique_agency_counts():
    catalog = load_sources('data/phase-eight-sources.json')
    live = [dict(id='sme-business',validation_status='verified',last_success_at='2026-11-10',announcement_count=3, config=next(s for s in catalog if s['id']=='sme-business'))]
    rows = coverage_rows(catalog, live)
    summary = coverage_summary(rows)
    assert summary['local']['total'] == 22 and summary['local']['verified'] == 0
    assert summary['central']['verified'] == 1
    assert next(r for r in rows if r['id']=='sme-business')['announcement_count'] == 3
    assert next(r for r in rows if r['id']=='ida')['verified'] is False


def test_request_budget_stops_before_network(tmp_path):
    client = EvidenceClient(tmp_path, max_requests=1)
    client.events.append({})
    with pytest.raises(FetchError, match='預算'):
        client._request('https://unit.gov.tw/x')
    client = EvidenceClient(tmp_path, budget_seconds=1)
    client.deadline = 0
    with pytest.raises(FetchError, match='預算'):
        client._request('https://unit.gov.tw/x')


def test_explicit_empty_batch_records_success(store, source):
    source.update(method='rss',allow_empty=True,terms_reviewed=True)
    class Response:
        encoding='utf-8'
        text='<rss><channel><item><title>合成一般消息</title></item></channel></rss>'
    class Client:
        def get(self, url): return Response()
    result = collect(store,[source],Client())
    assert result[source['id']] == dict(inserted=0,updated=0,unchanged=0)
    assert store.sources()[0]['last_outcome']=='success'


def test_official_detail_fields_and_execution_date_not_deadline(tmp_path, source):
    from scripts.verify_phase_two import verify_source
    source.update(terms_reviewed=True,terms_url='https://unit.gov.tw/terms',method='html',
                  parser=dict(item_selector='li',link_selector='a'),detail_selector='.body',
                  detail_fields=dict(announced_on_selector='.published'))
    pages = {
        source['url']: '<li><a href="/detail">合成企業AI補助</a></li>',
        source['terms_url']: '資料授權，請註明出處',
        'https://unit.gov.tw/detail': '''<div class="published">2026-11-10</div><div class="body">
<p>一、計畫目的：合成企業研發補助計畫，補助國內公司研發經費並受理企業申請。</p>
<p>二、申請資格：國內依法登記公司。</p><p>三、補助比例：每案上限100萬元。</p>
<p>四、受理期間：自115年11月10日至115年11月30日。</p>
<p>五、執行期間：至116年12月31日。</p></div>'''}
    # fixture source uses a gov.tw host; relative detail belongs to that same host.
    from urllib.parse import urljoin
    detail_url=urljoin(source['url'],'/detail')
    pages[detail_url]=pages['https://unit.gov.tw/detail']
    class Response:
        status_code=200
        encoding='utf-8'
        def __init__(self,text): self.text=text
    class Client:
        events=[]
        def get(self,url):
            self.events.append(dict(checked_at='2026-11-10T00:00:00Z',sha256='synthetic',raw_path='synthetic'))
            return Response(pages[url])
    record, items=verify_source(source,tmp_path,Client())
    assert record['status']=='verified'
    a=items[0]
    assert a.announced_on=='2026-11-10' and a.deadline=='2026-11-30'
    assert '100萬元' in a.amount and '國內依法登記公司' in a.eligibility
    assert '執行期間' in a.content
    assert record['announcements'][0]['deadline']=='2026-11-30'


def test_batch_limit_preserves_existing_database(tmp_path, source):
    from grant_watch.daily import run
    from test_daily import verifier
    path=tmp_path/'db.sqlite3'
    assert run(path,[source],tmp_path/'first',True,verifier())['status']=='success'
    before=path.read_bytes()
    result=run(path,[dict(source,id=f's{i}') for i in range(9)],tmp_path/'second',verifier=verifier())
    assert result['status']=='failed' and not result['published']
    assert path.read_bytes()==before and '8' in result['error']


def test_coverage_does_not_certify_changed_parser():
    catalog=load_sources('data/phase-eight-sources.json')
    s=next(s for s in catalog if s['id']=='adi-events')
    live=dict(id=s['id'],validation_status='verified',last_success_at='2026-11-10',config=dict(s,parser={}))
    assert not next(r for r in coverage_rows(catalog,[live]) if r['id']==s['id'])['verified']


def test_streamlit_coverage_and_topic_filter(tmp_path,monkeypatch):
    from streamlit.testing.v1 import AppTest
    from grant_watch.phase_two import assess_announcement,refresh_derived
    path=tmp_path/'ui.sqlite3'
    catalog=load_sources('data/phase-eight-sources.json')
    s=next(s for s in catalog if s['id']=='sme-business')
    store=Store(path);store.sync_sources([s]);store.save_batch(s['id'],[replace(item(),title='合成AI研發補助')])
    refresh_derived(store,{r['id']:assess_announcement(r,dict(error='合成無內文')) for r in store.announcements()})
    store.close()
    monkeypatch.setenv('GRANT_DB_PATH',str(path))
    app=AppTest.from_file('streamlit_app.py').run()
    assert not app.exception
    assert len(app.expander)==1
    assert any(m.value=='1/12' for m in app.metric)
    table=app.dataframe[0].value
    assert len(table)==34 and int(table.loc[table['機關']==s['agency'],'公告數'].iloc[0])==1
    app.sidebar.multiselect[0].set_value(['智慧製造']).run()
    assert not app.exception and len(app.expander)==0
    app.sidebar.multiselect[0].set_value(['AI']).run()
    assert not app.exception and len(app.expander)==1


def test_view_counters_do_not_create_false_updates(source):
    from scripts.verify_phase_two import parse_document
    from types import SimpleNamespace
    source.update(detail_selector='.body',detail_exclude_selectors=['.views'],
                  detail_ignored_line_patterns=[r'\(下載次數:\s*[\d,]+\)'])
    def parse(count):
        html=f'<div class="body"><p>合成正式補助內文100萬元。</p><li><a href="/a.pdf">附件</a> (下載次數: {count})</li><div class="views">點閱次數：{count}</div></div>'
        return parse_document(dict(official_url='https://unit.gov.tw/x'),source,
                              SimpleNamespace(text=html,status_code=200),
                              dict(checked_at='synthetic',sha256='synthetic',raw_path='synthetic'))
    before,after=parse(1),parse(99)
    assert before['body']==after['body'] and '100萬元' in before['body']
    assert '點閱次數' not in before['body'] and '下載次數' not in before['body']
    assert before['links']==after['links']


def test_old_quality_review_does_not_hide_updated_daily_assessment(tmp_path, source):
    from grant_watch.phase_two import assess_announcement, refresh_derived
    from grant_watch.web_query import read_snapshot
    path=tmp_path/'old-quality.sqlite3'
    store=Store(path);store.sync_sources([source]);store.save_batch(source['id'],[replace(item(),title='合成AI補助')])
    row=store.announcements()[0]
    refresh_derived(store,{row['id']:assess_announcement(row,dict(error='合成內文未取得'))})
    store.db.execute('CREATE TABLE quality_assessments (announcement_id TEXT, assessed_at TEXT, source_content_hash TEXT, assessment_json TEXT)')
    store.db.execute('INSERT INTO quality_assessments VALUES (?,?,?,?)',
                     (row['id'],'2026-11-10','older-content',json.dumps(dict(topics=['智慧製造']))))
    store.db.commit();store.close()
    result=read_snapshot(path)['announcements'][0]
    assert result['topics']==['AI'] and result['classification']=='待人工確認'
    assert result['application_status']=='無法確認'
