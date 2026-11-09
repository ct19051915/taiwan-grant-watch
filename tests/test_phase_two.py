"""合成測試案例僅用於離線測試，不計入真實公告驗證。"""
from dataclasses import replace
import json
import sqlite3
import pytest
from grant_watch.models import Announcement
from grant_watch.phase_two import application_status, plan_identity, refresh_derived, enriched_rows
from grant_watch.quality import GRANT
from grant_watch.storage import Store
from grant_watch.extractors import HtmlExtractor
from grant_watch.http import Client, FetchError


def assessment(**kwargs):
    return dict(classification=GRANT, reason='合成測試依據', application_start='2026-11-01',
                deadline='2026-11-09', application_windows=[], **kwargs)


@pytest.mark.parametrize(('today','expected'),[
    ('2026-10-31','即將開放'),('2026-11-01','開放申請'),
    ('2026-11-09','開放申請'),('2026-11-10','已截止')])
def test_status_boundaries(today,expected):
    assert application_status(assessment(),today)['status']==expected


@pytest.mark.parametrize('changes',[
    {'application_start':None}, {'deadline':None},
    {'application_start':'2026-11-10'}, {'classification':'待人工確認'},
    {'application_windows':[{},{}]}, {'quality_flags':['title_body_round_conflict']},
])
def test_ambiguous_status_stays_unknown(changes):
    item=assessment();item.update(changes)
    assert application_status(item,'2026-11-09')['status']=='無法確認'


def test_result_notice_precedes_application_dates():
    assert application_status(assessment(document_kind='result_notice'),'2026-11-09')['status']=='核定結果'


def test_expired_without_start():
    item=assessment();item['application_start']=None
    assert application_status(item,'2026-11-10')['status']=='已截止'


def test_relation_preserves_year_and_round():
    first='公告115年度「合成企業補助計畫」第一梯次申請'
    assert plan_identity(first)==plan_identity('轉知'+first)
    assert plan_identity(first)!=plan_identity(first.replace('115','116'))
    assert plan_identity(first)!=plan_identity(first.replace('第一','第二'))
    assert plan_identity('合成企業補助') is None


def test_derivation_preserves_originals_and_is_idempotent(tmp_path,source):
    db=Store(tmp_path/'grants.sqlite3'); db.sync_sources([source,dict(source,id='other')])
    a=Announcement(title='115年度「合成企業補助計畫」',agency='合成',government_level='central',city=None,
                   official_url='https://unit.gov.tw/1')
    b=replace(a,official_url='https://other.gov.tw/2',agency='合成二')
    db.save_batch(source['id'],[a]); db.save_batch('other',[b])
    before=db.announcements(); assessments={r['id']:assessment() for r in before}
    assert refresh_derived(db,assessments,'2026-11-09')==1
    assert refresh_derived(db,assessments,'2026-11-09')==1
    assert db.announcements()==before and len(before)==2
    assert all(r['related_announcements'] and r['application_status']=='開放申請' for r in enriched_rows(db))
    db.save_batch(source['id'],[replace(a,content='合成新內文')])
    changed=next(r for r in enriched_rows(db) if r['official_url']==a.official_url)
    assert changed['application_status']=='無法確認'
    db.close()


def test_open_legacy_database_adds_no_original_columns(tmp_path,source):
    path=tmp_path/'legacy.sqlite3';db=Store(path);db.sync_sources([source]);db.close()
    db=Store(path);before=list(db.db.execute('PRAGMA table_info(announcements)'))
    refresh_derived(db,{},'2026-11-09')
    assert list(db.db.execute('PRAGMA table_info(announcements)'))==before
    assert db.db.execute('PRAGMA integrity_check').fetchone()[0]=='ok';db.close()


def test_configured_title_attribute_and_sbir_inclusion(source):
    source=dict(source,include_title_contains=['SBIR'],parser=dict(item_selector='li',link_selector='a',title_attribute='title'))
    records=HtmlExtractor().parse(source,'<li><a href="/a" title="合成SBIR核定名單">1 日期 合成SBIR核定名單</a></li>')
    assert records[0].title=='合成SBIR核定名單'


def test_include_rule_change_invalidates_source(store,source):
    a=Announcement(title='合成補助',agency='合成',government_level='central',city=None,official_url='https://unit.gov.tw/a')
    store.save_batch(source['id'],[a]);store.sync_sources([dict(source,include_title_contains=['SBIR'])])
    assert store.sources()[0]['validation_status']=='pending'


def test_phase_two_registry_covers_exact_candidates():
    candidates=json.load(open('data/sources.json'));phase=json.load(open('data/phase-two-sources.json'))
    assert {s['id'] for s in candidates}=={s['candidate_id'] for s in phase}
    assert len(phase)==27 and len([s for s in phase if s['government_level']=='local'])==22
    assert all(s['validation_status'] in {'verified','pending','failed'} for s in phase)
    assert all(s.get('terms_url') for s in phase if s.get('terms_reviewed'))


def test_all_configured_html_selectors_compile():
    import soupsieve
    for source in json.load(open('data/phase-two-sources.json')):
        if source['method']!='html':continue
        for key,value in source.get('parser',{}).items():
            if key.endswith('_selector'):soupsieve.compile(value)


def test_source_parser_failure_is_isolated(tmp_path,source,monkeypatch):
    from types import SimpleNamespace
    from scripts.verify_phase_two import verify_source
    class Broken:
        def parse(self,*args):raise RuntimeError('合成格式改變')
    class FakeClient:
        events=[]
        def get(self,url):return SimpleNamespace(text='授權方式，請註明出處',status_code=200,encoding='utf-8')
    monkeypatch.setitem(__import__('scripts.verify_phase_two',fromlist=['EXTRACTORS']).EXTRACTORS,'rss',Broken)
    source=dict(source,terms_url='https://unit.gov.tw/terms')
    record,items=verify_source(source,tmp_path,FakeClient())
    assert record['status']=='failed' and not items
    assert '合成格式改變' in record['error']
    assert (tmp_path/'synthetic-result.json').exists()


def test_redirect_without_location_reports_reason():
    import requests
    from unittest.mock import Mock
    response=requests.Response();response.status_code=302;response._content=b'';response._content_consumed=True
    client=Client(session=Mock(get=Mock(return_value=response)),sleep=lambda _:None)
    with pytest.raises(FetchError,match='robots.txt 重新導向缺少 Location'):
        client.get('https://unit.gov.tw/feed')


def test_explicit_publication_start_keeps_evidence():
    from grant_watch.phase_two import assess_announcement
    row=dict(title='【合成】企業補助計畫',official_url='https://unit.gov.tw/1',announced_on='2026-11-01',content=None)
    body='一、申請對象\n本計畫補助國內企業或公司研發。\n二、受理期間：自公告日起至115年12月7日止。\n三、補助金額\n每家企業補助上限50萬元。'
    doc=dict(official_url=row['official_url'],http_status=200,error=None,body=body,links=[])
    result=assess_announcement(row,doc)
    assert result['application_start']=='2026-11-01'
    assert result['evidence']['fields']['application_start']['official_url']==row['official_url']
    assert application_status(result,'2026-11-09')['status']=='開放申請'
    row['announced_on']=None
    assert assess_announcement(row,doc)['application_start'] is None


def test_structured_call_dates_are_not_publication_dates():
    from grant_watch.phase_two import assess_announcement
    row=dict(title='【合成】企業研發補助計畫',official_url='https://unit.gov.tw/1',announced_on=None,content=None)
    body='徵求期間\n115年11月4日至\n115年12月28日\n申請資格\n本計畫補助企業公司及學研機構共同合作申請研發經費，每案最高50萬元。'
    result=assess_announcement(row,dict(official_url=row['official_url'],http_status=200,error=None,body=body,links=[]))
    assert result['application_start']=='2026-11-04' and result['deadline']=='2026-12-28'
    assert row['announced_on'] is None
    assert result['evidence']['fields']['deadline']['quote'].startswith('徵求期間')
