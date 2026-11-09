import json
import logging
from .extractors import EXTRACTORS
from .http import Client, FetchError, official_url

LOG = logging.getLogger(__name__)


def load_sources(path):
    with open(path, encoding='utf-8') as handle:
        sources = json.load(handle)
    ids = set()
    for source in sources:
        if source['id'] in ids:
            raise ValueError('來源 ID 重複')
        ids.add(source['id'])
        official_url(source['url'])
        if source['method'] not in EXTRACTORS:
            raise ValueError('未知擷取方式')
        if source['government_level'] not in {'central', 'local'}:
            raise ValueError('未知政府層級')
    return sources


def collect(store, sources, client=None):
    client = client or Client()
    store.sync_sources(sources)
    results = {}
    for source in sources:
        try:
            if not source.get('terms_reviewed'):
                raise FetchError('待人工確認網站使用規範與實際公告端點；尚未啟用')
            response = client.get(source['url'])
            # 正確處理 UTF-8 / Big5 網頁；明確 charset 優先，否則偵測。
            if response.encoding is None or response.encoding.lower() == 'iso-8859-1':
                response.encoding = response.apparent_encoding
            items = EXTRACTORS[source['method']]().parse(source, response.text)
            if not items:
                raise FetchError('本次未取得符合補助關鍵字的公告，不能標記驗證成功')
            results[source['id']] = store.save_batch(source['id'], items)
            LOG.info('source=%s success items=%d', source['id'], len(items))
        except Exception as exc:
            # 每個來源獨立失敗，批次寫入則原子提交；避免在日誌輸出回應或密鑰。
            message = str(exc) if isinstance(exc, (FetchError, ValueError)) else type(exc).__name__
            store.record_failure(source['id'], message)
            results[source['id']] = {'error': message}
            LOG.error('source=%s failed: %s', source['id'], message)
    return results
