import pytest
from grant_watch.storage import Store


@pytest.fixture(autouse=True)
def no_real_network(monkeypatch):
    def blocked(*args, **kwargs):
        raise AssertionError('單元測試禁止連線；所有資料均為合成資料')
    monkeypatch.setattr('requests.sessions.Session.request', blocked)


@pytest.fixture
def source():
    return dict(id='synthetic', agency='合成測試機關', government_level='central',
                city=None, method='rss', url='https://unit.gov.tw/feed', terms_reviewed=True,
                validation_status='pending', last_checked_at=None)


@pytest.fixture
def store(tmp_path, source):
    db = Store(tmp_path / 'test.sqlite3')
    db.sync_sources([source])
    yield db
    db.close()
