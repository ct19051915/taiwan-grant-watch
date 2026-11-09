# Windows 本機查詢網頁

需要 Python 3.12 以上及 Git。以下使用 PowerShell，在本儲存庫目錄執行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-web.txt
```

`requirements-web.txt` 獨立加入 Streamlit 與 Windows 時區資料，不改變每日排程的依賴。

## 準備既有資料（不初始化、不重建）

以有權限的 GitHub 帳號在自己的電腦 clone 私人儲存庫。不要把 Token 貼入程式或指令。可以使用 Git Credential Manager 登入。將資料分支以另一個本機工作目錄取出：

```powershell
git fetch origin grant-data
git worktree add --detach ..\taiwan-grant-data origin/grant-data
$env:GRANT_DB_PATH = (Resolve-Path ..\taiwan-grant-data\grants.sqlite3).Path
$env:GRANT_REPORT_PATH = (Resolve-Path ..\taiwan-grant-data\latest-report.json).Path
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8501 --browser.gatherUsageStats false
```

在瀏覽器開啟 http://127.0.0.1:8501 。不需啟用 PowerShell 腳本執行權限。預設路徑為 `var/grants.sqlite3` 及同目錄的 `latest-report.json`，可用上述環境變數指定其他既有檔案。網頁不會連 GitHub 下載資料、不抓取官方網站、不寫 SQLite，也不會在缺檔時建立新資料庫。缺檔、格式損毀會顯示錯誤；缺表／欄位、異常 JSON 會降級顯示。

停止網頁（Ctrl+C）後可更新本機快照，再重啟：

```powershell
git fetch origin grant-data
git -C ..\taiwan-grant-data switch --detach origin/grant-data
```

網頁每次互動讀取同一交易快照，不長期快取。也可按「重新讀取本機資料」。不要在使用中的資料庫上執行初始化或分類腳本。資料工作目錄不需 commit 或 push。

## 資料解讀

- 公告保留原標題；不從標題自行編造計畫名稱或補助目的。目的欄顯示既有分類中的官方節錄。
- 採用既有 `application_states`；若另有 `quality_assessments`，採每則最新評估。內容雜湊或官方網址不符、來源未驗證、分類異常均降級為待確認。
- 以既有 `application_status` 函式及台灣當日日期判斷申請狀態，不回寫資料。多期間不任選一組；無確定起訖不標示開放。
- 產業只採既有 `category`，其中企業補助／非補助分類不當成產業。未知類別顯示待確認，不推測產業。
- 原文／證據以文字或 JSON 顯示，不能執行來源 HTML。官方連結只允許 HTTP(S)。
- 每日報告顯示本機檔案的狀態及計數；失敗時為候選寫入次數，不等於保存筆數。`grant-data` 僅保存成功快照，最新失敗須由有權限者查看 Actions artifact。
- 來源涵蓋僅列資料庫實際來源，其他中央／地方機關尚未涵蓋；沒有完整機關名冊，不能宣稱涵蓋全台。

## 測試

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt -r requirements-web.txt
.\.venv\Scripts\python.exe -m pytest
```

## 未來若需公開服務（本階段未部署）

須先另行審查：私人資料收集端與展示端分離，由受限背景工作讀取私人資料，經授權、個資／來源授權審查及欄位白名單後產生專供展示的資料集；不掛載原 SQLite、不提供私人分支與原始證據下載。展示服務採身分驗證、最小權限、唯讀服務帳號、秘密管理及存取紀錄；取得明確資料公開範圍與部署授權後才實作。請勿直接把本程式與私人資料庫放到公開 Streamlit hosting。

## 本次驗證紀錄

- Python 3.12：`python -m pytest -q`，118 passed（包含既有功能與 11 項新增案例／參數組合）。
- 實際 `grant-data` 快照 42 則公告以唯讀方式載入；Chromium / Playwright 檢查 1440×1000 與 390×844，均無 Streamlit 例外或頁面橫向溢出。
- Windows 指令已提供，尚未在原生 Windows 主機實際執行。
