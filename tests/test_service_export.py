import csv
from pathlib import Path
from types import SimpleNamespace
from openpyxl import load_workbook
from grant_watch.export import export_rows, COLUMNS
from grant_watch.http import FetchError
from grant_watch.service import collect, load_sources


class FakeClient:
    def __init__(self, text=None, error=None):
        self.text, self.error = text, error

    def get(self, url):
        if self.error:
            raise self.error
        return SimpleNamespace(text=self.text, encoding='utf-8')


def test_pipeline_repeat_and_failure(store, source):
    text = (Path(__file__).parent / 'fixtures/synthetic.rss').read_text()
    assert collect(store, [source], FakeClient(text))['synthetic']['inserted'] == 1
    assert collect(store, [source], FakeClient(text))['synthetic']['unchanged'] == 1
    assert len(store.announcements()) == 1
    collect(store, [source], FakeClient(error=FetchError('synthetic failure')))
    assert store.sources()[0]['last_outcome'] == 'failed'
    assert store.sources()[0]['last_success_at'] is not None
    assert store.db.execute('SELECT count(*) FROM runs').fetchone()[0] == 3


def test_failed_source_does_not_stop_next(store, source):
    bad = dict(source, id='bad', terms_reviewed=False)
    text = (Path(__file__).parent / 'fixtures/synthetic.rss').read_text()
    result = collect(store, [bad, source], FakeClient(text))
    assert 'error' in result['bad']
    assert result['synthetic']['inserted'] == 1
    states = {row['id']: row for row in store.sources()}
    assert states['bad']['validation_status'] == 'pending'
    assert states['bad']['last_checked_at'] is not None


def test_empty_never_verified(store, source):
    collect(store, [source], FakeClient('<rss><channel/></rss>'))
    assert store.sources()[0]['validation_status'] == 'pending'
    assert store.announcements() == []


def test_exports(tmp_path):
    rows = [dict(id='synthetic', title='=HYPERLINK("bad")', agency='合成機關', amount=None)]
    csv_path, xlsx_path = tmp_path / 'out.csv', tmp_path / 'out.xlsx'
    export_rows(rows, csv_path)
    export_rows(rows, xlsx_path)
    with csv_path.open(encoding='utf-8-sig', newline='') as f:
        output = list(csv.DictReader(f))
    assert output[0]['title'].startswith("'=")
    assert output[0]['amount'] == ''
    book = load_workbook(xlsx_path)
    sheet = book.active
    assert sheet.cell(2, COLUMNS.index('title') + 1).data_type == 's'
    assert sheet.cell(2, COLUMNS.index('amount') + 1).value is None
    book.close()


def test_registry_coverage():
    sources = load_sources('data/sources.json')
    local = [s for s in sources if s['government_level'] == 'local']
    assert len(local) == len({s['city'] for s in local}) == 22
    assert {'moea', 'sme', 'ida', 'doit', 'nstc'} <= {s['id'] for s in sources}
    assert all(s['validation_status'] == 'pending' and not s['terms_reviewed'] for s in sources)
    assert all('last_checked_at' in s for s in sources)
