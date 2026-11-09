"""純解析器：測試可注入合成文件，不需網路。"""
import re
from urllib.parse import urljoin
from xml.etree import ElementTree
from bs4 import BeautifulSoup
from .http import FetchError, official_url
from .models import Announcement

KEYWORDS = re.compile(r'補助|補貼|獎勵')


def announcement(source, title, url, **fields):
    if not title or not url or not (KEYWORDS.search(title) or any(
            term in title for term in source.get('include_title_contains', []))):
        return None
    if any(term in title for term in source.get('exclude_title_contains', [])):
        return None
    return Announcement(title=title, official_url=official_url(url), agency=source['agency'],
                        government_level=source['government_level'], city=source['city'], **fields)


class RssExtractor:
    def parse(self, source, text):
        # 不接受 DTD/entity；RSS/Atom 不需要這些功能。
        if re.search(r'<!\s*(DOCTYPE|ENTITY)', text, re.I):
            raise FetchError('XML 不允許 DTD 或 entity')
        root = ElementTree.fromstring(text)
        items = root.findall('./channel/item')
        atom = root.tag == '{http://www.w3.org/2005/Atom}feed'
        if atom:
            items = root.findall('{http://www.w3.org/2005/Atom}entry')
        elif root.tag != 'rss':
            raise FetchError('不是 RSS 或 Atom feed')
        result = []
        for item in items:
            if atom:
                ns = {'a': 'http://www.w3.org/2005/Atom'}
                title = item.findtext('a:title', '', ns)
                links = item.findall('a:link', ns)
                link = next((x.get('href') for x in links if x.get('rel', 'alternate') == 'alternate'), None)
                external_id = item.findtext('a:id', None, ns)
                published = item.findtext('a:published', None, ns)
                content = item.findtext('a:summary', None, ns)
            else:
                title, link = item.findtext('title', ''), item.findtext('link')
                external_id = item.findtext('guid')
                published, content = item.findtext('pubDate'), item.findtext('description')
            record = announcement(source, title.strip(), urljoin(source['url'], link) if link else None,
                                  external_id=external_id, announced_on=published,
                                  content=BeautifulSoup(content, 'html.parser').get_text(' ', strip=True) if content else None)
            if record:
                result.append(record)
        return result


class HtmlExtractor:
    def parse(self, source, text):
        config = source.get('parser', {})
        if not config.get('item_selector') or not config.get('link_selector'):
            raise FetchError('HTML 來源尚未設定並驗證公告列與連結 selector')
        soup = BeautifulSoup(text, 'html.parser')
        rows = soup.select(config['item_selector'])
        if not rows:
            raise FetchError('找不到公告列；頁面格式可能已變更')
        result = []
        for row in rows:
            link = row.select_one(config['link_selector'])
            if link is None or not link.get('href'):
                raise FetchError('公告列缺少連結')
            fields = {}
            # 只依明確設定擷取欄位；不從整頁猜測截止日、金額或資格。
            for field in ('announced_on', 'deadline', 'amount', 'eligibility', 'category', 'content'):
                selector = config.get(field + '_selector')
                node = row.select_one(selector) if selector else None
                fields[field] = node.get_text(' ', strip=True) if node else None
            title_node = row.select_one(config['title_selector']) if config.get('title_selector') else link
            if title_node is None:
                raise FetchError('公告列缺少設定的標題節點')
            title = (title_node.get(config['title_attribute']) if config.get('title_attribute')
                     else title_node.get_text(' ', strip=True))
            record = announcement(source, title, urljoin(source['url'], link['href']), **fields)
            if record:
                result.append(record)
        return result


class JsonExtractor:
    def parse(self, source, text):
        import json
        data = json.loads(text)
        config = source.get('parser', {})
        for key in config.get('items_path', []):
            data = data[key]
        if not isinstance(data, list):
            raise FetchError('JSON 公告集合必須為陣列')
        mapping = config.get('fields', {})
        if not {'title', 'official_url'} <= mapping.keys():
            raise FetchError('JSON 來源未設定 title 與 official_url 欄位')
        result = []
        allowed = {'external_id', 'announced_on', 'deadline', 'amount', 'eligibility', 'category', 'content'}
        for row in data:
            title, link = row.get(mapping['title']), row.get(mapping['official_url'])
            fields = {key: row.get(value) for key, value in mapping.items() if key in allowed}
            if fields.get('external_id') is not None:
                fields['external_id'] = str(fields['external_id'])
            record = announcement(source, title, urljoin(source['url'], link) if link else None, **fields)
            if record:
                result.append(record)
        return result


EXTRACTORS = {'rss': RssExtractor, 'html': HtmlExtractor, 'json': JsonExtractor}
