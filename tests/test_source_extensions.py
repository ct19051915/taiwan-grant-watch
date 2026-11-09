"""新增真實來源設定需要的回歸案例；資料仍為合成，原 50 項測試不修改。"""
import pytest
from grant_watch.extractors import HtmlExtractor, announcement
from grant_watch.http import FetchError


def test_separate_title_selector(source):
    source['parser'] = dict(item_selector='li', link_selector='a', title_selector='.title', announced_on_selector='time')
    text = '<li><a href="/notice/1"><b>1</b><span class="title">合成企業補助</span><time>2026-11-09</time></a></li>'
    record = HtmlExtractor().parse(source, text)[0]
    assert record.title == '合成企業補助'
    assert record.normalized()['announced_on'] == '2026-11-09'


def test_configured_title_missing_fails(source):
    source['parser'] = dict(item_selector='li', link_selector='a', title_selector='.title')
    with pytest.raises(FetchError, match='標題節點'):
        HtmlExtractor().parse(source, '<li><a href="/notice/1">合成企業補助</a></li>')


def test_explicit_non_grant_title_exclusion(source):
    source['exclude_title_contains'] = ['合成系統維護']
    assert announcement(source, '合成補助平台：合成系統維護', 'https://unit.gov.tw/maintenance') is None
    assert announcement(source, '合成企業補助計畫', 'https://unit.gov.tw/grant') is not None


def test_exclusion_change_resets_source_validation(store, source):
    record = announcement(source, '合成企業補助計畫', 'https://unit.gov.tw/grant')
    store.save_batch(source['id'], [record])
    assert store.sources()[0]['validation_status'] == 'verified'
    store.sync_sources([dict(source, exclude_title_contains=['合成排除詞'])])
    assert store.sources()[0]['validation_status'] == 'pending'
