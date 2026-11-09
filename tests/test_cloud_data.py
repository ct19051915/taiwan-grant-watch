import json
import sqlite3

import pytest
import requests

from grant_watch.cloud_data import Config, SnapshotCache
from grant_watch.web_query import DataError


@pytest.fixture
def remote(tmp_path, monkeypatch):
    path = tmp_path / 'synthetic.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE announcements (id TEXT, title TEXT)')
    state = dict(sha='a' * 40, report=dict(status='success', published=True,
                 completed_at='2026-11-09T00:00:00Z'), db=path.read_bytes(), fail=False)
    calls = []

    class Response:
        status_code = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def iter_content(self, size): yield self.body

    def get(url, **kwargs):
        calls.append((url, kwargs))
        assert kwargs['allow_redirects'] is False
        assert kwargs['timeout'] == (10, 60)
        if state['fail']:
            raise requests.ConnectionError('SYNTHETIC_SECRET')
        response = Response()
        response.body = (json.dumps(dict(sha=state['sha'])).encode() if '/commits/' in url
                         else json.dumps(state['report']).encode() if 'latest-report' in url else state['db'])
        return response

    monkeypatch.setattr(requests, 'get', get)
    return state, calls


def test_same_commit_ttl_force_and_new_generation(remote):
    state, calls = remote
    now = [0]
    cache = SnapshotCache(Config('owner/private', 'SYNTHETIC_SECRET', 60), lambda: now[0])
    first = cache.load()
    assert len(calls) == 3
    assert all('ref=' + state['sha'] in c[0] for c in calls[1:])
    assert cache.load()['sha'] == first['sha'] and len(calls) == 3
    now[0] = 60
    cache.load()
    assert len(calls) == 4  # unchanged commit only needs one request
    state['sha'] = 'b' * 40
    second = cache.load(force=True)
    assert second['sha'] != first['sha']
    assert first['path'].read_bytes() == second['path'].read_bytes()
    assert 'SYNTHETIC_SECRET' not in repr(cache.config)


@pytest.mark.parametrize('failure', ['network', 'sqlite', 'report', 'schema'])
def test_failure_preserves_snapshot_and_sanitizes(remote, failure):
    state, _ = remote
    cache = SnapshotCache(Config('owner/private', 'SYNTHETIC_SECRET'))
    first = cache.load()
    before = first['path'].read_bytes()
    state['sha'] = 'b' * 40
    if failure == 'network': state['fail'] = True
    elif failure == 'sqlite': state['db'] = b'not sqlite'
    elif failure == 'schema': state['db'] = b''
    else: state['report']['published'] = False
    stale = cache.load(force=True)
    assert stale['sha'] == first['sha'] and stale['warning']
    assert stale['path'].read_bytes() == before
    assert 'SYNTHETIC_SECRET' not in repr(stale)
    state['fail'] = False
    if failure == 'network':
        assert cache.load(force=True)['warning'] is None


def test_initial_failure_and_validation(remote):
    state, _ = remote
    state['fail'] = True
    with pytest.raises(DataError, match='尚無可用') as error:
        SnapshotCache(Config('owner/private', 'SYNTHETIC_SECRET')).load()
    assert 'SYNTHETIC_SECRET' not in str(error.value)
    with pytest.raises(DataError): Config('https://evil.test/repo', 'secret')
    with pytest.raises(DataError): Config('owner/repo', '', 300)


def test_streamlit_cloud_flow(remote):
    from streamlit.testing.v1 import AppTest
    state, _ = remote
    app = AppTest.from_file('streamlit_app.py')
    app.secrets['grant_data'] = dict(repository='owner/private', token='SYNTHETIC_SECRET', cache_seconds=60)
    app.run()
    assert not app.exception
    assert any('最後成功保存' in c.value for c in app.caption)
    state['fail'] = True
    app.sidebar.button[0].click().run()
    assert not app.exception and app.error


@pytest.mark.parametrize('status', [302, 401, 403, 404, 429, 500])
def test_http_errors_do_not_read_or_render_response(monkeypatch, status):
    class Response:
        status_code = status
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def iter_content(self, size):
            raise AssertionError('error response body must not be consumed')
    monkeypatch.setattr(requests, 'get', lambda *args, **kwargs: Response())
    cache = SnapshotCache(Config('owner/private', 'SYNTHETIC_SECRET'))
    with pytest.raises(DataError):
        cache.load()


def test_download_limit(monkeypatch):
    class Response:
        status_code = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def iter_content(self, size): yield b'oversized'
    monkeypatch.setattr(requests, 'get', lambda *args, **kwargs: Response())
    cache = SnapshotCache(Config('owner/private', 'SYNTHETIC_SECRET'))
    with pytest.raises(DataError, match='大小上限'):
        cache._get('commits/grant-data', limit=2)
