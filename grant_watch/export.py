import csv
from pathlib import Path
from openpyxl import Workbook

COLUMNS = ['id', 'title', 'agency', 'government_level', 'city', 'announced_on',
           'deadline', 'amount', 'eligibility', 'category', 'official_url',
           'fetched_at', 'updated_at', 'source_validation_status', 'last_seen_at', 'content_hash', 'content',
           'application_status', 'status_as_of', 'classification_reason', 'classification_evidence',
           'related_announcements', 'topics']


def safe_cell(value):
    # 試算表公式注入防護；資料庫保留原始值。
    if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


def export_rows(rows, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix.lower() == '.csv':
        with path.open('w', encoding='utf-8-sig', newline='') as handle:
            writer = csv.writer(handle)
            writer.writerow(COLUMNS)
            writer.writerows([[safe_cell(row.get(key)) for key in COLUMNS] for row in rows])
    elif path.suffix.lower() == '.xlsx':
        book = Workbook()
        sheet = book.active
        sheet.title = '公告'
        sheet.append(COLUMNS)
        for row in rows:
            sheet.append([safe_cell(row.get(key)) for key in COLUMNS])
        sheet.freeze_panes = 'A2'
        sheet.auto_filter.ref = sheet.dimensions
        book.save(path)
    else:
        raise ValueError('僅支援 .csv 與 .xlsx')
