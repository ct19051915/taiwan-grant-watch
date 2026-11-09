import csv
import json
from grant_watch.__main__ import main


def test_cli_offline_registry_failure_and_export(tmp_path, monkeypatch, capsys):
    db = tmp_path / 'cli.sqlite3'
    output = tmp_path / 'export.csv'
    base = ['grant_watch', '--db', str(db)]
    monkeypatch.setattr('sys.argv', base + ['sources'])
    assert main() == 0
    state = json.loads(capsys.readouterr().out)
    assert len(state) == 27
    assert all(row['validation_status'] == 'pending' for row in state)
    monkeypatch.setattr('sys.argv', base + ['fetch', '--source', 'sme'])
    assert main() == 1
    assert 'error' in json.loads(capsys.readouterr().out)['sme']
    monkeypatch.setattr('sys.argv', base + ['export', str(output)])
    assert main() == 0
    with output.open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.reader(handle))
    assert len(rows) == 1 and rows[0][0] == 'id'
