"""保留系統代理與 TLS 驗證；逐站 robots、限速、有限重試及回應大小。"""
import logging
import time
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser
import requests

LOG = logging.getLogger(__name__)
USER_AGENT = 'TaiwanGrantWatch/0.1'


class FetchError(RuntimeError):
    pass


def official_url(url):
    p = urlsplit(url)
    if p.scheme not in {'http', 'https'} or not p.hostname or not p.hostname.endswith(('.gov.tw', '.gov.taipei')):
        raise FetchError('僅允許官方 *.gov.tw 或 *.gov.taipei HTTP(S) 網址')
    if p.username or p.password or p.port not in (None, 80, 443):
        raise FetchError('不允許登入資訊或非標準連接埠')
    return url


class Client:
    def __init__(self, session=None, sleep=time.sleep, clock=time.monotonic, interval=3.0, attempts=3):
        self.session = session or requests.Session()
        self.sleep, self.clock = sleep, clock
        self.interval, self.attempts = max(interval, 3.0), attempts
        self.last_request, self.robots = {}, {}

    def _request(self, url, interval=None):
        official_url(url)
        host = urlsplit(url).netloc
        delay = max(self.interval, interval or 0)
        for attempt in range(self.attempts):
            remaining = self.last_request.get(host, -float('inf')) + delay - self.clock()
            if remaining > 0:
                self.sleep(remaining)
            self.last_request[host] = self.clock()
            try:
                response = self.session.get(url, timeout=(10, 30), allow_redirects=False,
                                            stream=True, headers={'User-Agent': USER_AGENT})
                if response.status_code == 429 or 500 <= response.status_code < 600:
                    retry_after = response.headers.get('Retry-After')
                    response.close()
                    wait = 2 ** attempt
                    if retry_after:
                        try:
                            wait = max(wait, float(retry_after))
                        except ValueError:
                            try:
                                wait = max(wait, (parsedate_to_datetime(retry_after) - datetime.now(timezone.utc)).total_seconds())
                            except (TypeError, ValueError):
                                raise FetchError('無法解讀 Retry-After，停止擷取')
                    if wait > 60:
                        raise FetchError('伺服器要求長時間等待，請稍後再執行')
                    if attempt + 1 == self.attempts:
                        raise FetchError(f'HTTP {response.status_code}: retries exhausted')
                    self.sleep(wait)
                    continue
                chunks, size = [], 0
                try:
                    for chunk in response.iter_content(65536):
                        size += len(chunk)
                        if size > 5_000_000:
                            raise FetchError('回應超過 5 MB 上限')
                        chunks.append(chunk)
                    response._content = b''.join(chunks)
                    response._content_consumed = True
                finally:
                    response.close()
                return response
            except requests.exceptions.SSLError as exc:
                raise FetchError('TLS 驗證失敗；未停用驗證') from exc
            except (requests.ConnectionError, requests.Timeout) as exc:
                # 不重試明確的代理政策拒絕。
                if '403' in str(exc):
                    raise FetchError('proxy CONNECT 403: destination denied') from exc
                if attempt + 1 == self.attempts:
                    raise FetchError(f'{type(exc).__name__}: connection failed') from exc
                self.sleep(2 ** attempt)
        raise FetchError('無可用回應')

    def _policy(self, url):
        p = urlsplit(official_url(url))
        origin = f'{p.scheme}://{p.netloc}'
        if origin not in self.robots:
            robots_url = origin + '/robots.txt'
            for _ in range(6):
                response = self._request(robots_url)
                if response.status_code in {301, 302, 303, 307, 308}:
                    if not response.headers.get('Location'):
                        raise FetchError('robots.txt 重新導向缺少 Location')
                    robots_url = official_url(urljoin(robots_url, response.headers['Location']))
                    continue
                break
            else:
                raise FetchError('robots.txt 重新導向過多')
            parser = RobotFileParser()
            if response.status_code == 404:
                parser.parse([])
            elif response.status_code == 200:
                if '<html' in response.text[:500].lower():
                    raise FetchError('robots.txt 回傳 HTML，需人工檢查')
                parser.parse(response.text.splitlines())
            else:
                raise FetchError(f'robots.txt HTTP {response.status_code}，保守停止')
            self.robots[origin] = parser
        parser = self.robots[origin]
        if not parser.can_fetch(USER_AGENT, url):
            raise FetchError('robots.txt 不允許擷取')
        delay = parser.crawl_delay(USER_AGENT) or 0
        rate = parser.request_rate(USER_AGENT)
        if rate:
            delay = max(delay, rate.seconds / rate.requests)
        return delay

    def get(self, url):
        for _ in range(6):
            delay = self._policy(url)
            response = self._request(url, delay)
            if response.status_code in {301, 302, 303, 307, 308}:
                if not response.headers.get('Location'):
                    raise FetchError('公告頁重新導向缺少 Location')
                url = official_url(urljoin(url, response.headers['Location']))
                continue
            if response.status_code != 200:
                raise FetchError(f'公告頁 HTTP {response.status_code}')
            # 不解 CAPTCHA、不繞過登入或反爬蟲。
            if any(marker in response.text[:10000].lower() for marker in ('g-recaptcha', 'cf-chl-', '<title>just a moment')):
                raise FetchError('偵測驗證或反爬蟲頁面，停止擷取')
            return response
        raise FetchError('公告頁重新導向過多')
