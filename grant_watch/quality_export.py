import csv
import json
from pathlib import Path
from openpyxl import Workbook
from .export import safe_cell
from .quality import GRANT, REVIEW

COLUMNS = [
    ('announcement_id', '公告唯一碼'), ('title', '公告名稱'), ('classification', '分類'),
    ('document_kind', '公告階段'), ('reason', '分類理由'), ('agency', '公告機關'),
    ('official_url', '官方公告網址'), ('announced_on', '公告日期'), ('eligibility', '申請對象／資格原文'),
    ('amount', '補助額度原文'), ('application_period', '受理期間原文'),
    ('application_start', '開始日期'), ('deadline', '截止日期'), ('application_url', '申請網址'),
    ('application_windows', '各對象受理期間'), ('application_links', '官方列示申請網址與證據'),
    ('quality_flags', '欄位品質提示'), ('summary', '官方原文節錄'),
    ('evidence', '官方欄位證據'), ('rule_version', '規則版本'), ('is_stale', '原文已更新需重評'),
]


def cell(value):
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    return safe_cell(value)


def write_sheet(book, title, rows):
    sheet = book.create_sheet(title)
    sheet.append([label for _, label in COLUMNS])
    for row in rows:
        sheet.append([cell(row.get(key)) for key, _ in COLUMNS])
    sheet.freeze_panes = 'A2'
    sheet.auto_filter.ref = sheet.dimensions
    for col in ('A', 'B', 'E', 'G', 'I', 'J', 'K', 'N'):
        sheet.column_dimensions[col].width = 40


def export_quality(rows, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    grant_path, all_path = directory / 'enterprise-grants.xlsx', directory / 'all-classifications.xlsx'
    for path, subset in ((grant_path, [r for r in rows if r['classification'] == GRANT and not r.get('is_stale')]), (all_path, rows)):
        book = Workbook()
        book.remove(book.active)
        write_sheet(book, '企業補助計畫' if path == grant_path else '全部公告', subset)
        if path == all_path:
            write_sheet(book, '待人工確認', [r for r in rows if r['classification'] == REVIEW])
            write_sheet(book, '欄位待補', [r for r in rows if r['classification'] == GRANT and r['quality_flags']])
        note = book.create_sheet('說明')
        for line in [
            '規則式分類；所有原始公告保留，非補助類含純結果通知，不表示與補助無關。',
            '企業補助計畫不代表目前開放申請；截止日期不代表延長，請以官方公告為準。',
            '未知欄位為空白；多對象／多期間／多網址保留明細，不任選其中一組。',
            '開始日「公告日起／即日起」保留原文，不自動代入日期。摘要為官方原文前600字。',
            '申請網址由官方內文列示，可能是受委託執行單位網域；本輪不登入或送出申請。',
            '跨站轉載仍保留為不同公告；分類結果不宣稱唯一計畫數。',
            '原始內容變更後 latest_announcement_assessments.is_stale=1，需重新評估。',
        ]:
            note.append([line])
        note.column_dimensions['A'].width = 120
        book.save(path)
    csv_path = directory / 'all-classifications.csv'
    with csv_path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow([label for _, label in COLUMNS])
        writer.writerows([[cell(r.get(key)) for key, _ in COLUMNS] for r in rows])
    return dict(enterprise_excel=str(grant_path), all_excel=str(all_path), all_csv=str(csv_path))
