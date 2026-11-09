from pathlib import Path
import json
import pytest
from grant_watch.extractors import RssExtractor, HtmlExtractor, JsonExtractor
from grant_watch.http import FetchError

FIXTURE = Path(__file__).parent / 'fixtures' / 'synthetic.rss'


def test_rss(source):
    items = RssExtractor().parse(source, FIXTURE.read_text())
    assert len(items) == 1
    assert items[0].external_id == 'fake-001'
    assert items[0].normalized()['announced_on'] == '2026-11-09'
    assert items[0].deadline is None
    assert items[0].content == '僅供測試的虛構公告，不代表政府計畫。'


def test_atom(source):
    text = '''<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>fake-a</id>
    <title>合成補助</title><link href="/news/a"/><published>2026-11-09</published></entry></feed>'''
    assert RssExtractor().parse(source, text)[0].official_url == 'https://unit.gov.tw/news/a'


def test_xml_reject_entity(source):
    with pytest.raises(FetchError):
        RssExtractor().parse(source, '<!DOCTYPE rss [<!ENTITY x "oops">]><rss/>')


def test_html_explicit_fields(source):
    source['parser'] = dict(item_selector='article', link_selector='a', announced_on_selector='time')
    text = '<article><a href="/n/1">合成補助公告</a><time>115/11/09</time></article><footer>截止 115/12/31</footer>'
    result = HtmlExtractor().parse(source, text)
    assert result[0].normalized()['announced_on'] == '2026-11-09'
    assert result[0].deadline is None
    assert result[0].official_url == 'https://unit.gov.tw/n/1'
    with pytest.raises(FetchError):
        HtmlExtractor().parse(source, '<html>changed</html>')


def test_html_requires_config(source):
    with pytest.raises(FetchError):
        HtmlExtractor().parse(source, '<a href="/">補助</a>')


def test_json(source):
    source['parser'] = dict(items_path=['data'], fields=dict(title='name', official_url='url', external_id='id', amount='money'))
    items = JsonExtractor().parse(source, json.dumps({'data': [dict(name='合成補助', url='/n/1', id=7, money=None)]}))
    assert items[0].external_id == '7' and items[0].amount is None
