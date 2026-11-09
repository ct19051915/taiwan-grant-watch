"""Daily runs use synthetic data; no official network requests."""
from dataclasses import replace
import json
import sqlite3
import pytest
from openpyxl import load_workbook
from grant_watch.daily import run, database_lock
from test_storage import item


def verifier(record=None, detail_error=None):
    def verify(source, output, client):
        a = record or item()
        return dict(status='verified', error=None, documents={a.official_url: dict(
            official_url=a.official_url, http_status=200, error=detail_error,
            body='合成企業研發補助計畫，補助國內公司研發經費。', links=[])}), [a]
    return verify


def test_daily_replay_and_update(tmp_path, source):
    db, output = tmp_path/'db.sqlite3', tmp_path/'report'
    assert run(db,[source],output,True,verifier())['inserted'] == 1
    with sqlite3.connect(db) as conn:
        uid = conn.execute('SELECT id FROM announcements').fetchone()[0]
    result = run(db,[source],output,verifier=verifier())
    assert result['status'] == 'success' and result['inserted'] == 0 and result['unchanged'] == 1
    assert run(db,[source],output,verifier=verifier(replace(item(),amount='合成100萬')))['updated'] == 1
    with sqlite3.connect(db) as conn:
        assert conn.execute('SELECT id FROM announcements').fetchall() == [(uid,)]
        assert conn.execute('SELECT count(*) FROM application_states').fetchone()[0] == 1
    book = load_workbook(output/'announcements.xlsx',read_only=True)
    rows = list(book.active.values); book.close()
    assert len(rows) == 2
    assert {'title','category','application_status','announced_on','deadline','official_url'} <= set(rows[0])
    assert json.loads((output/'report.json').read_text())['status'] == 'success'


@pytest.mark.parametrize('failure',['source','detail','export'])
def test_failure_preserves_original_bytes(tmp_path,source,monkeypatch,failure):
    db, output = tmp_path/'db.sqlite3', tmp_path/'report'
    assert run(db,[source],output,True,verifier())['status'] == 'success'
    before = db.read_bytes()
    verify = verifier(replace(item(),amount='合成變更'))
    sources = [source]
    if failure == 'source':
        sources.append(dict(source,id='broken'))
        good = verify
        def verify(s,o,c):
            if s['id']=='broken':
                return dict(status='failed',error='synthetic HTTP failure',documents={}), []
            return good(s,o,c)
    elif failure == 'detail':
        verify = verifier(detail_error='synthetic detail failure')
    else:
        def broken(*args):
            raise OSError('synthetic disk full')
        monkeypatch.setattr('grant_watch.daily.export_rows',broken)
    result = run(db,sources,output,verifier=verify)
    assert result['status'] == 'failed' and not result['published']
    assert db.read_bytes() == before
    assert (output/'report.json').exists()


def test_missing_corrupt_and_locked_database(tmp_path,source):
    db, output = tmp_path/'db.sqlite3', tmp_path/'report'
    assert run(db,[source],output,verifier=verifier())['status']=='failed'
    assert not db.exists()
    db.write_bytes(b'corrupt synthetic database')
    assert run(db,[source],output,True,verifier())['status']=='failed'
    assert db.read_bytes()==b'corrupt synthetic database'
    db.unlink()
    with database_lock(db):
        assert run(db,[source],output,True,verifier())['status']=='failed'
    assert not db.exists()
