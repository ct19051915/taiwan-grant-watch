import json
import sqlite3
from datetime import date

import pytest
from grant_watch.storage import Store
from grant_watch.web_query import (DataError, connect_readonly, filter_announcements,
                                   read_report, read_snapshot, taipei_time)


@pytest.fixture
def database(tmp_path):
    path = tmp_path / 'grants.sqlite3'
    store = Store(path)
    store.close()
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE application_states (announcement_id TEXT, source_content_hash TEXT, assessment_json TEXT)')
        db.execute('CREATE TABLE daily_documents (official_url TEXT, document_json TEXT)')
        for uid, title, level, city, industry in [('1', '研發補助', 'central', None, '科技'), ('2', '服務補助', 'local', '臺北市', '服務')]:
            db.execute('''INSERT INTO announcements (id,title,agency,government_level,city,official_url,category,content_hash,fetched_at,last_seen_at,updated_at,source_validation_status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)''', (uid,title,'測試機關',level,city,'https://example.gov.tw/'+uid,industry,'hash','2026-01-01','2026-01-01','2026-01-01','verified'))
            assessment = dict(classification='企業補助計畫', application_start='2026-01-01', deadline='2026-12-31')
            db.execute('INSERT INTO application_states VALUES (?,?,?)', (uid,'hash',json.dumps(assessment)))
    return path


def test_search_filters_and_date_boundary(database):
    rows = read_snapshot(database, date(2026,12,31))['announcements']
    assert len(filter_announcements(rows, open_only=True)) == 2
    assert [r['id'] for r in filter_announcements(rows, keyword='  研發 ', government='中央政府', city='待確認', industry='科技', status='開放申請', open_only=True)] == ['1']
    assert len(filter_announcements(rows, government='地方政府', city='臺北市', industry='服務')) == 1
    assert not filter_announcements(rows, keyword="' OR 1=1 --")
    assert not filter_announcements(rows, city='高雄市')
    assert not filter_announcements(read_snapshot(database, date(2027,1,1))['announcements'], open_only=True)


def test_readonly_and_no_file_changes(database, tmp_path):
    before = database.read_bytes()
    read_snapshot(database)
    assert database.read_bytes() == before
    with connect_readonly(database) as db:
        with pytest.raises(sqlite3.OperationalError):
            db.execute('DELETE FROM announcements')
    missing = tmp_path / 'missing.sqlite3'
    with pytest.raises(DataError):
        read_snapshot(missing)
    assert not missing.exists()


def test_empty_missing_columns_and_corruption(tmp_path):
    path = tmp_path / 'empty.sqlite3'
    sqlite3.connect(path).close()
    assert read_snapshot(path)['announcements'] == []
    with sqlite3.connect(path) as db:
        db.execute('CREATE TABLE announcements (wrong TEXT)')
    assert read_snapshot(path)['warnings']
    path.write_text('not a database')
    with pytest.raises(DataError):
        read_snapshot(path)


@pytest.mark.parametrize('change', ['stale', 'unverified', 'json', 'shape'])
def test_uncertain_data_never_open(database, change):
    with sqlite3.connect(database) as db:
        if change == 'stale':
            db.execute("UPDATE announcements SET content_hash='new'")
        elif change == 'unverified':
            db.execute("UPDATE announcements SET source_validation_status='pending'")
        else:
            value = '{broken' if change == 'json' else json.dumps(dict(classification='企業補助計畫', quality_flags=42))
            db.execute('UPDATE application_states SET assessment_json=?', (value,))
    rows = read_snapshot(database)['announcements']
    assert not filter_announcements(rows, open_only=True)
    assert all(r['classification'] == '待人工確認' for r in rows)


def test_report_and_time(tmp_path):
    path = tmp_path / 'report.json'
    assert read_report(path)[1]
    path.write_text('[]')
    assert read_report(path)[1]
    path.write_text('{"status":"success","inserted":0}')
    assert read_report(path)[0]['inserted'] == 0
    assert taipei_time('2026-11-09T00:00:00Z') == '2026-11-09 08:00:00 台灣時間'
    assert taipei_time('bad') == '待確認'


def test_streamlit_missing_database(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv('GRANT_DB_PATH', str(tmp_path / 'missing'))
    app = AppTest.from_file('streamlit_app.py').run()
    assert not app.exception
    assert app.error


def test_streamlit_filters_and_updates(database, monkeypatch, tmp_path):
    from streamlit.testing.v1 import AppTest
    monkeypatch.setenv('GRANT_DB_PATH', str(database))
    monkeypatch.setenv('GRANT_REPORT_PATH', str(tmp_path / 'missing.json'))
    app = AppTest.from_file('streamlit_app.py').run()
    assert not app.exception
    assert len(app.expander) == 2
    app.sidebar.text_input[0].set_value('研發').run()
    assert len(app.expander) == 1
    assert '研發' in app.expander[0].label
    app.sidebar.text_input[0].set_value('找不到').run()
    assert len(app.expander) == 0
    assert not app.exception
