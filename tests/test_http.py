import requests
import pytest
from grant_watch.http import Client, FetchError


def response(status=200, text='', headers=None):
    result = requests.Response()
    result.status_code = status
    result.headers.update(headers or {})
    result._content = text.encode()
    result._content_consumed = True
    result.encoding = 'utf-8'
    return result


class Session:
    def __init__(self, responses):
        self.responses, self.calls = iter(responses), []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        result = next(self.responses)
        if isinstance(result, Exception):
            raise result
        return result


def client(responses):
    session = Session(responses)
    waits = []
    return Client(session=session, sleep=waits.append, clock=lambda: 100), session, waits


def test_robots_deny():
    c, session, _ = client([response(text='User-agent: *\nDisallow: /private')])
    with pytest.raises(FetchError, match='不允許'):
        c.get('https://unit.gov.tw/private/feed')
    assert len(session.calls) == 1


def test_robots_fail_closed():
    c, session, _ = client([response(403)])
    with pytest.raises(FetchError):
        c.get('https://unit.gov.tw/feed')
    assert len(session.calls) == 1


def test_retry_rate_limit_and_cache():
    c, session, waits = client([response(text='User-agent: *\nCrawl-delay: 8\nAllow: /'),
                               response(503), response(text='<rss/>'), response(text='<rss/>')])
    assert c.get('https://unit.gov.tw/feed').status_code == 200
    c.get('https://unit.gov.tw/feed')
    assert len(session.calls) == 4
    assert 8 in waits and 1 in waits
    assert all(call[1]['allow_redirects'] is False for call in session.calls)
    assert all('verify' not in call[1] for call in session.calls)


def test_redirect_checks_new_host_robots():
    c, session, _ = client([response(404), response(302, headers={'Location': 'https://other.gov.tw/feed'}),
                            response(text='User-agent: *\nDisallow: /')])
    with pytest.raises(FetchError):
        c.get('https://unit.gov.tw/feed')
    assert session.calls[-1][0] == 'https://other.gov.tw/robots.txt'


def test_redirect_non_official_rejected():
    c, session, _ = client([response(404), response(302, headers={'Location': 'https://example.com/login'})])
    with pytest.raises(FetchError):
        c.get('https://unit.gov.tw/feed')
    assert len(session.calls) == 2


def test_retries_exhausted():
    c, _, _ = client([requests.Timeout(), requests.Timeout(), requests.Timeout()])
    with pytest.raises(FetchError, match='connection failed'):
        c.get('https://unit.gov.tw/feed')


def test_retry_after_long_wait_stops():
    c, _, waits = client([response(429, headers={'Retry-After': '3600'})])
    with pytest.raises(FetchError, match='長時間'):
        c.get('https://unit.gov.tw/feed')
    assert waits == []


def test_tls_not_retried():
    c, session, _ = client([requests.exceptions.SSLError('synthetic')])
    with pytest.raises(FetchError, match='TLS'):
        c.get('https://unit.gov.tw/feed')
    assert len(session.calls) == 1


def test_proxy_policy_denial_not_retried():
    c, session, _ = client([requests.exceptions.ProxyError('CONNECT tunnel failed: 403 Forbidden')])
    with pytest.raises(FetchError, match='destination denied'):
        c.get('https://unit.gov.tw/feed')
    assert len(session.calls) == 1


def test_captcha_stops():
    c, _, _ = client([response(404), response(text='<html><div class="g-recaptcha"></div></html>')])
    with pytest.raises(FetchError, match='反爬蟲'):
        c.get('https://unit.gov.tw/feed')
