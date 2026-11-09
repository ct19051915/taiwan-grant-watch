from dataclasses import replace
import pytest
from grant_watch.models import Announcement


def item(**kwargs):
    return Announcement(title='【合成測試】企業研發補助', agency='合成測試機關',
                        government_level='central', city=None,
                        official_url='https://unit.gov.tw/news/1', external_id='fake-1', **kwargs)


def test_insert_duplicate_update(store):
    record = item()
    assert store.save_batch('synthetic', [record])['inserted'] == 1
    before = store.announcements()[0]
    assert before['deadline'] is None and before['amount'] is None
    assert before['source_validation_status'] == 'verified'
    assert store.save_batch('synthetic', [record])['unchanged'] == 1
    assert store.announcements()[0]['updated_at'] == before['updated_at']
    assert store.save_batch('synthetic', [replace(record, amount='最高 50 萬元（合成）')])['updated'] == 1
    after = store.announcements()[0]
    assert after['id'] == before['id'] and after['fetched_at'] == before['fetched_at']
    assert after['content_hash'] != before['content_hash']
    assert after['updated_at'] >= before['updated_at']
    assert len(store.announcements()) == 1


def test_source_id_survives_changed_url(store):
    store.save_batch('synthetic', [item()])
    store.save_batch('synthetic', [replace(item(), official_url='https://unit.gov.tw/new/1')])
    assert len(store.announcements()) == 1
    assert store.announcements()[0]['official_url'] == 'https://unit.gov.tw/new/1'


def test_url_dedup_without_id(store):
    store.save_batch('synthetic', [item()])
    store.save_batch('synthetic', [replace(item(), external_id=None, official_url='https://unit.gov.tw/news/1?utm_source=x')])
    assert len(store.announcements()) == 1


def test_cross_source_url(store, source):
    store.sync_sources([dict(source, id='other')])
    store.save_batch('synthetic', [item()])
    store.save_batch('other', [item()])
    assert len(store.announcements()) == 1
    assert store.db.execute('SELECT count(*) FROM source_items').fetchone()[0] == 2


def test_hash_alias_and_distinct_external_ids(store):
    record = replace(item(announced_on='115/11/09', content='完整的合成公告內文'), external_id=None)
    store.save_batch('synthetic', [record])
    store.save_batch('synthetic', [replace(record, official_url='https://unit.gov.tw/alias/1')])
    assert len(store.announcements()) == 1
    store.save_batch('synthetic', [replace(record, external_id='different', official_url='https://unit.gov.tw/other/1')])
    assert len(store.announcements()) == 2


def test_sparse_different_urls_not_merged(store):
    store.save_batch('synthetic', [replace(item(), external_id=None)])
    store.save_batch('synthetic', [replace(item(), external_id=None, official_url='https://unit.gov.tw/2')])
    assert len(store.announcements()) == 2


def test_batch_rollback(store):
    with pytest.raises(ValueError):
        store.save_batch('synthetic', [item(), replace(item(), title='')])
    assert store.announcements() == []
    assert store.sources()[0]['validation_status'] == 'pending'


def test_config_change_invalidates_validation(store, source):
    store.save_batch('synthetic', [item()])
    store.sync_sources([source])
    assert store.sources()[0]['validation_status'] == 'verified'
    store.sync_sources([dict(source, url='https://unit.gov.tw/other')])
    assert store.sources()[0]['validation_status'] == 'pending'


def test_reopen_persists_and_replay_is_idempotent(tmp_path, source):
    from grant_watch.storage import Store
    path = tmp_path / 'persist.sqlite3'
    first = Store(path)
    first.sync_sources([source])
    first.save_batch('synthetic', [item()])
    uid = first.announcements()[0]['id']
    first.close()
    second = Store(path)
    try:
        second.sync_sources([source])
        assert second.save_batch('synthetic', [item()])['unchanged'] == 1
        assert second.announcements()[0]['id'] == uid
        assert second.sources()[0]['validation_status'] == 'verified'
    finally:
        second.close()


def test_id_url_conflict_rolls_back(store):
    second = replace(item(), external_id='fake-2', official_url='https://unit.gov.tw/news/2')
    store.save_batch('synthetic', [item(), second])
    with pytest.raises(ValueError, match='不同公告'):
        store.save_batch('synthetic', [replace(item(), official_url=second.official_url)])
    assert len(store.announcements()) == 2
    assert {row['official_url'] for row in store.announcements()} == {
        'https://unit.gov.tw/news/1', 'https://unit.gov.tw/news/2'}
