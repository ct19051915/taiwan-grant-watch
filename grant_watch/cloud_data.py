"""Private GitHub snapshots; never writes to the repository or exposes credentials."""
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import threading
import time

import requests

from .web_query import DataError, read_snapshot


@dataclass(frozen=True)
class Config:
    repository: str
    token: str = field(repr=False)
    ttl: int = 300

    def __post_init__(self):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', self.repository):
            raise DataError('雲端 repository 設定錯誤。')
        if not self.token or not 60 <= self.ttl <= 3600:
            raise DataError('請設定唯讀 token 與 60～3600 秒快取。')


class SnapshotCache:
    def __init__(self, config, clock=time.monotonic):
        self.config = config
        self.clock = clock
        self.lock = threading.Lock()
        self.current = None
        self.checked = None
        self.warning = None
        self.directory = tempfile.TemporaryDirectory(prefix='grant-private-')

    def _get(self, path, *, binary=False, limit=100 * 1024 * 1024):
        # No redirects: Authorization must only reach api.github.com.
        url = f'https://api.github.com/repos/{self.config.repository}/{path}'
        with requests.get(url, headers={
            'Authorization': 'Bearer ' + self.config.token,
            'Accept': 'application/vnd.github.raw+json' if binary else 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
        }, timeout=(10, 60), allow_redirects=False, stream=True) as response:
            if response.status_code != 200:
                raise DataError('無法讀取私人資料來源；請檢查唯讀權限、token 到期與 grant-data 分支。')
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > limit:
                    raise DataError('雲端資料超過大小上限，保留既有快照。')
                chunks.append(chunk)
            return b''.join(chunks)

    def _refresh(self):
        metadata = json.loads(self._get('commits/grant-data', limit=2 * 1024 * 1024))
        sha = metadata['sha']
        if not re.fullmatch(r'[0-9a-f]{40}', sha):
            raise ValueError('invalid commit')
        if self.current and self.current['sha'] == sha:
            return
        report = json.loads(self._get(f'contents/latest-report.json?ref={sha}', binary=True, limit=2 * 1024 * 1024))
        if not isinstance(report, dict) or report.get('status') != 'success' or report.get('published') is not True or not report.get('completed_at'):
            raise ValueError('unsuccessful report')
        payload = self._get(f'contents/grants.sqlite3?ref={sha}', binary=True)
        # A new generation is published only after BOTH files validate. Old files survive failures.
        candidate = Path(self.directory.name) / f'{sha}.sqlite3'
        try:
            candidate.write_bytes(payload)
            candidate.chmod(0o600)
            with sqlite3.connect(candidate.as_uri() + '?mode=ro', uri=True) as db:
                if db.execute('PRAGMA quick_check').fetchone() != ('ok',):
                    raise ValueError('invalid sqlite')
                columns = {r[1] for r in db.execute('PRAGMA table_info(announcements)')}
                if not {'id', 'title'} <= columns:
                    raise ValueError('missing announcements')
            read_snapshot(candidate)
        except Exception:
            candidate.unlink(missing_ok=True)
            raise
        self.current = dict(path=candidate, report=report, sha=sha)

    def load(self, force=False):
        with self.lock:
            if force or self.checked is None or self.clock() - self.checked >= self.config.ttl:
                try:
                    self._refresh()
                    self.warning = None
                except Exception:
                    # Never display exception text, HTTP bodies, URLs or Authorization headers.
                    self.warning = '無法更新雲端資料（權限、網路或快照驗證失敗）；保留並顯示上次成功快照，資料可能過期。'
                self.checked = self.clock()
            if self.current is None:
                raise DataError('尚無可用雲端快照；請檢查 Secrets、唯讀權限與 grant-data 的成功資料。')
            return dict(self.current, warning=self.warning)
