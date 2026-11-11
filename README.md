> 第八階段第一批：每日來源名冊為 `data/phase-eight-sources.json`。實測與未啟用原因見 [第八階段報告](docs/phase-eight-validation.md)；早期階段數量為歷史快照。

# 台灣政府企業補助公告自動追蹤系統

Python 3.12／SQLite 的第一階段實作。提供候選來源管理、RSS／Atom、HTML、JSON 擷取器、標準化、去重更新、失敗紀錄、CSV／Excel 匯出及 pytest 測試。

**最新驗證（2026-11-09）：2 個官方來源成功，共 31 筆來源公告。** 中小及新創企業署業務消息 3 筆、經濟部訊息公告 RSS 28 筆，均 HTTP 200；各來源第二次實際擷取新增 0 筆。CSV／Excel 已讀回核對真實官方網址。詳見 [最新驗證報告](docs/official-source-validation-2026-11-09.md)；先前代理 403 紀錄保留於 [歷史驗證紀錄](docs/source-validation.md)。

尚未開發 Gradio、AI 摘要、Email 或 GitHub Actions 排程；之後可每天呼叫 CLI，這次沒有設定排程。既有雲端 install_script、start_skill 與網路設定保留不變。`.gitignore` 排除虛擬環境、資料庫、匯出檔、憑證及暫存產物。

## 使用已驗證的官方來源

沿用現有程式與原 50 項測試；可用來源另列於 `data/active-sources.json`，原候選清單保持不變。正式資料庫在 `var/grants.sqlite3`，匯出在 `var/announcements.csv` 與 `var/announcements.xlsx`。

```bash
.venv/bin/python -m grant_watch --sources data/active-sources.json fetch --source sme-business --source moea-notices-rss
.venv/bin/python -m grant_watch --sources data/active-sources.json sources
.venv/bin/python -m grant_watch --sources data/active-sources.json export var/announcements.csv
.venv/bin/python -m grant_watch --sources data/active-sources.json export var/announcements.xlsx
# 完整重跑：兩次網路擷取、隔離內容更新與匯出比對
.venv/bin/python -m scripts.verify_official_sources
```

官方資料授權要求註明出處；已保留來源機關與官方網址。31 筆為來源公告數，同計畫在不同網站轉載時仍可能有不同紀錄；未聲稱是 31 個不同計畫。內容更新已以真實清單與官方詳情在隔離資料庫重播驗證，不代表本次觀察到官網自然修訂。其餘候選仍待驗證。

## 企業補助辨識與資料品質

已逐筆核對現有 31 筆真實公告的官方詳情：**企業補助計畫 14、非補助公告 13、待人工確認 4**。非補助類本輪皆為純核定／結果通知，仍保留原始紀錄；企業補助分類也不代表目前正在受理。規則依官方內文判斷，不只看標題關鍵字。

詳見 [逐筆分類、人工確認與欄位品質報告](docs/announcement-quality-report.md)。原始四表不變，另以 quality_runs／quality_documents／quality_assessments 保存版本與證據，view `latest_announcement_assessments` 提供最新結果及 is_stale。

```bash
# 重新逐筆抓官方詳情並評估現有 SQLite 公告
.venv/bin/python -m scripts.classify_announcements
# 重播已保存的真實快照（先驗證原始 HTML、原公告內容版本）
.venv/bin/python -m scripts.classify_announcements --snapshot var/quality/20261109T080655Z
```

輸出 `var/quality/enterprise-grants.xlsx`（14 筆計畫）與 `var/quality/all-classifications.xlsx`（31 筆完整分類、4 筆人工確認及 10 筆計畫欄位待補）。另有完整 CSV 與 JSON 證據。分類另表保存，不回寫原始公告、刪除公告或改變既有去重更新機制。

未知欄位 NULL；多對象期間／網址保存明細，不任選其一。部分補助僅明示適用範圍，未提供完整資格，會另外提示。申請網址只表示官方內文明示的連結，並未登入或送出申請。原始內容更新後需重新擷取與評估，不能用過期快照冒充新驗證。

## 安裝與執行

在專案根目錄執行（現有 `.venv` 可直接使用）：

```bash
python3 --version  # 需 Python 3.12
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pytest -q
python -m grant_watch sources
```

依賴的直接版本已固定；`requirements-dev.txt` 包含執行與測試依賴，尚非完整間接依賴鎖檔。可選擇 `python -m pip install -e .` 安裝套件；CLI 的資料檔相對路徑仍以目前工作目錄為準。預設資料庫為被既有 `.gitignore` 忽略的 `var/grants.sqlite3`，測試資料庫一律位於 pytest 臨時目錄。

```bash
# 現有候選尚未啟用：此命令會記錄失敗、回傳 exit 1，不會假裝成功。
python -m grant_watch fetch --source sme --source moea

# 可選擇多個來源，逐站執行；任何來源失敗時整個命令 exit 1。
python -m grant_watch --db var/grants.sqlite3 --log-file var/fetch.log fetch --source sme
python -m grant_watch export var/announcements.csv
python -m grant_watch export var/announcements.xlsx
```

全域參數 `--db`、`--sources`、`--log-file` 須放在子命令前。SQLite 會自動建立資料目錄；自訂日誌的父目錄須先建立。預設日誌送至 stderr。空資料庫可匯出欄位標題，不代表取得公告。CSV 使用 UTF-8 BOM，NULL 匯出空白；Excel 保留空白儲存格，兩種格式均處理公式注入。

## 來源管理及啟用流程

`data/sources.json` 保留初次開發的 27 筆候選快照（本輪啟用端點及成功快照在 `data/active-sources.json`）：經濟部、中小及新創企業署、產業發展署、產業技術司、國科會與全台 22 縣市。地方政府先記錄官方入口及優先尋找的業務單位；**首頁不是已確認的公告端點，單位名稱與分工也待核對**。所有來源為 `pending`，`last_checked_at: null` 表示從未檢查，不能當成已追蹤。

啟用新來源前：

1. 取得環境對該官方網域的合法存取權，確認 robots.txt、網站使用規範及開放資料授權；不得繞過登入、驗證碼或反爬蟲。環境設定由使用者管理，本次未更動。
2. 人工從官方入口尋找企業補助公告清單，優先選擇 API 或 RSS。將 `url` 改為實際端點，設定 `method`（`rss`、`html` 或 `json`）。目前只允許 `*.gov.tw`、`*.gov.taipei`；其他官方網域需另行審查後擴充程式。
3. HTML 設定公告列與欄位 selector；JSON 設定路徑與欄位對照。確認條款後設 `terms_reviewed: true`。這是人工確認旗標，不會自動驗證網站條款。不要手動把候選 JSON 的驗證狀態改為 verified。
4. 執行 `fetch --source ID`，檢查實際公告與擷取結果。只有成功取得至少一筆符合關鍵字、可標準化且整批寫入成功的公告，資料庫才標為 `verified`。輸入清單不會自動升級；後續執行狀態以 SQLite `sources`／`runs` 為準。可用 `sources` 指令查看。

HTML 可選 `title_selector` 指定標題節點，避免連結內序號與日期混入；來源可用 `exclude_title_contains` 明列排除詞。HTML parser 設定示例（**僅為格式示例，不是任何真實網站的 selector**）：

```json
{
  "item_selector": "article.notice",
  "link_selector": "a.title",
  "title_selector": ".plan-name",
  "announced_on_selector": "time.published",
  "deadline_selector": ".deadline",
  "amount_selector": ".amount",
  "eligibility_selector": ".eligibility"
}
```

JSON parser 設定示例（同為合成格式）：

```json
{
  "items_path": ["data", "items"],
  "fields": {
    "title": "name",
    "official_url": "url",
    "external_id": "id",
    "announced_on": "published_date",
    "deadline": "application_deadline"
  }
}
```

RSS／Atom 不需 parser 設定。所有擷取器先以標題的「補助、補貼、獎勵」作候選篩選；**尚非企業適用性判定**，可能包含非企業補助，也可能漏掉沒有這些字的計畫，需人工複核。資料只來自當次清單／feed，不自動翻頁、追附件或深入詳情；大量回溯與 PDF 解析屬後續範圍。公告機關使用所設定的發布來源機關，不推測實際承辦單位。欄位需由明確 selector／對照提供；沒有資料則 NULL，不從導覽、頁尾或全文猜測截止日及金額。

## 資料與去重規則

- `announcements`：UUID 公告唯一碼、名稱、機關、`government_level`（central/local）、縣市、公告日期、申請截止日、金額、資格、類別、官方網址、內文、內容雜湊、首次擷取時間、最後看見時間、內容最後更新時間、驗證狀態。金額與資格以原文儲存，不換算或推論。中央來源縣市 NULL。
- `sources`：來源 ID、完整設定、歷史驗證狀態、最後檢查時間、最後成功時間、最近結果與錯誤。修改端點、parser、方法、機關或使用規範旗標會重設驗證狀態。
- `source_items`：上游來源 ID／項目 ID（缺項目 ID 時改用網址）與公告 UUID 對照，支援跨來源同網址去重。
- `runs`：逐次執行結果、筆數與錯誤。曾成功的來源後來失敗會保留歷史 verified 與 last_success_at，但 last_outcome 為 failed；**verified 不代表目前健康**。公告的驗證狀態為寫入當時快照。

先比對來源項目 ID，再比對去除 fragment／utm／fbclid／gclid 並排序 query 的官方網址。只有無上游 ID、同來源、存在內文與公告日期時才用完整標準化內容雜湊合併不同網址，避免僅同名就誤合併。不同上游 ID 且不同網址的公告不因同名合併。ID 與 URL 指向不同既存公告時，整批失敗並記錄錯誤，交由人工處理。

內容雜湊不含擷取時間與網址。內容未變時只更新 `last_seen_at`，內容或同一來源項目的網址改變時更新既有 UUID 及 `updated_at`；`fetched_at` 保留首次擷取時間。每來源一個原子交易，某來源失敗不阻止其他來源。相同批次重跑不新增重複公告。

日期接受完整西元、三位數民國或明示「民國」年月日、ISO timestamp、RSS RFC 日期；不完整、無法辨識與不合法日期為 NULL。所有執行時間用 UTC ISO 8601，公告日期依來源文字的日期部分保存。

## 請求規則與限制

使用繼承的 HTTP(S) proxy 與 TLS 信任設定，不停用憑證驗證。每主機每次請求至少間隔 3 秒，並尊重 robots 的 Crawl-delay／Request-rate；先取 robots，404 視為未提供規則，其他非 200 狀態與 HTML 偽裝 robots 均保守停止。重新導向逐跳檢查，新主機重新驗證 robots。遇到反爬蟲標記即停止，不嘗試破解。

單次連線／讀取 timeout 為 10／30 秒，回應上限 5 MB，最多 3 次嘗試；暫時性網路錯誤、429、5xx 有退避，尊重 Retry-After，要求等待超過 60 秒則停止留待下次執行。代理明確 403 與 TLS 錯誤不重試。限速與 robots cache 僅在單一執行程序內有效，請勿同時執行多個擷取程序；SQLite 目前亦以單一寫入程序為使用方式。

## 專案結構與測試

```text
grant_watch/
  __main__.py      CLI
  models.py        欄位、日期與 URL 標準化
  http.py          robots、限速、重試、大小與重新導向限制
  extractors.py    RSS/Atom、HTML、JSON 解析器登錄
  storage.py       SQLite schema、來源狀態、交易及去重更新
  service.py       逐來源執行與失敗隔離
  export.py        CSV / Excel
 data/sources.json 候選官方入口（非成功來源）
 docs/             真實驗證證據與限制
 tests/fixtures/   明示合成資料，非真實公告
```

`python -m pytest -q` 的測試完全離線，禁止任何真實 requests 網路操作，涵蓋新增、重複、內容／網址更新、跨來源同 URL、保守內容雜湊合併、批次回滾、日期、解析器、來源失敗、重試、robots／TLS／重新導向／反爬蟲及兩種匯出。**離線測試通過不代表官方來源已驗證。**

## 第一階段版本與 PR 驗證

目前版本為 `0.1.0`，使用 Python 3.12。完整離線測試為 80 項；在專案根目錄執行 `python -m pytest -q`，並以 `python -m pip check` 檢查依賴。

乾淨 checkout 不包含本機 SQLite、官方網頁快照或 Excel。請先依安裝指令安裝依賴，再使用 `data/active-sources.json` 擷取官方資料，或執行 `python -m scripts.verify_official_sources` 建立本機資料及驗證證據；官方來源與數量會隨時間改變。歷史報告中的 31 筆與 14／13／4 分類是 2026-11-09 的實測快照，不是每次重跑必定相同的結果。可重現的離線測試使用明示合成 fixture，不需外網。

提交內容只包含程式、候選／啟用來源設定、測試與文字報告。`.venv/`、`var/`、SQLite 資料庫與側檔、產生的 Excel、`.env` 及其變體、私鑰與暫存檔不應提交；機密值不得寫入來源設定或範例檔。此版本不含網頁介面、排程、通知或部署設定。

## 第二階段：中央與 22 縣市來源驗證

從已合併第一階段的 `main` 建立；完整逐機關結果與限制見
[第二階段驗證報告](docs/phase-two-validation.md)，實際官方公告、請求時間與回應雜湊見
[機器證據](docs/phase-two-evidence.json)。新來源設定為 `data/phase-two-sources.json`，保留原候選及第一階段啟用清單。

```bash
python -m scripts.verify_phase_two
python -m pytest -q
```

驗證會逐站檢查 robots、官方清單與已審查的授權宣告，將 `verified`、`pending`、`failed`、HTTP 證據、原始回應及真實公告存到獨立的 `var/phase-two/<時間>/`。來源失敗不刪除先前取得的公告。此輪有 5 個來源最新驗證成功；其餘來源仍有存取、規範或端點確認工作，不能視為全臺均已啟用。

新增 `application_states` 保存五種申請狀態（開放申請、即將開放、已截止、核定結果、無法確認）與日期依據；`plan_relations` 保存跨站同計畫的候選關聯，原始公告不合併。CSV／Excel 同時匯出分類依據、狀態評估日、截止日與關聯 ID。原文缺乏明確日期或需要附件時維持未知；評估結果是標示日期當日的快照，日後需重跑更新。

## 每日台灣時間 08:00 自動追蹤（第七階段）

目前維持 **Public**，排程已在 daily.yml 設為 `0 0 * * *`（UTC 00:00／台灣 08:00）。第七階段已支援公開 repository；本批來源擴充須人工合併 PR 才會生效，GitHub 排程可能延遲。每日採第八階段名冊中 enabled 的 7 個來源，每批最多 8 個；其餘來源分批處理，不代表全臺全面涵蓋。

### 手動測試與正式執行

完整測試步驟、權限與驗證紀錄見 [第七階段說明](docs/phase-seven-daily.md)。Actions → Daily grant tracking → Run workflow，選 main 並勾 `dry_run` 可測試但不寫入資料。要正式補跑，選 main、不勾 `dry_run`、不勾 `initialize`。只有資料分支完全不存在且確定沒有歷史資料時，才可使用 `initialize`。

PR 分支可手動勾 `dry_run` 測試；正式發布工作只允許 main。全部流程使用 GitHub 內建短效 GITHUB_TOKEN，不需要新增 PAT／Secrets；蒐集工作 Contents 唯讀，只有發布工作 Contents 寫入。Repository 預設權限可維持唯讀，若組織政策限制 workflow 提升權限，需由管理員處理。

報表免費保存 30 天，包含新增／更新／未變次數、失敗來源與原因、開始／結束時間及耗時。新增／更新是候選資料的寫入次數（跨來源同公告可計入更新）；失敗時不代表已保存。Excel 是當次候選結果，失敗的報表請勿當作正式資料。Artifacts 到期不影響資料分支。私有儲存庫 Actions 受帳號免費分鐘數與儲存額度限制，請在 GitHub Billing 查看用量；每日最多八站、單一工作優先控制成本，不使用付費外部服務。

### 資料庫如何保存與保護

正式檔案為 **`grant-data` 分支根目錄的 `grants.sqlite3`**；同分支 `latest-report.json` 記錄最近成功資料，`announcements.json` 提供公告資料 JSON；三檔在同一 commit 發布。資料庫、Excel、密鑰不提交 main。每次先下載既有資料庫並以 SQLite backup 建立暫存副本，再擷取清單及詳情、分類、重算申請狀態與跨站候選關聯、匯出 Excel、檢查完整性。歷史公告不刪除，已存詳情供未出現在當日清單的公告重新評估狀態。

任一來源或詳情失敗、寫入／分類／匯出錯誤時，原資料庫保持原樣；錯誤列於 Actions 日誌與報表。這是整批成功才保存的保守策略，某站長期失敗會阻止每日正式更新，需維護者修復來源。首次執行只抓目前清單，不會自動載入第二階段本機的 50 筆歷史資料；如需沿用既有 SQLite，應由維護者先檢查、備份，再放入資料分支。

Actions `concurrency` 防止手動與每日工作同時寫入，不取消進行中的工作（GitHub 最多保留一個等待中的執行，多次觸發可能取代等待項目）；本機額外有檔案鎖。遠端使用一般 push，禁止 force push，若其他人同時改動資料分支，push 會失敗而保留遠端版本。**只有 Persist successful snapshot 步驟成功才代表遠端已保存**；後續報表上傳失敗可能造成工作紅色但資料已保存，請檢查該步驟及分支最新 commit。鎖只適用本機同一路徑；不要在其他電腦手動覆寫正式分支。

資料分支不存在時必須明確首次初始化；下載失敗、檔案遺失或損壞不會當作空資料庫重建。依目前 Public 設定，資料分支與歷史版本同樣公開；只保存政府公告與衍生資料，禁止提交 Token、Secrets 或其他敏感資料。

### 備份與還原

每次成功保存都是資料分支的一個 Git commit，無需依賴會到期的 Artifact。可在 GitHub 切換到 `grant-data`、點 **History**，選擇日期後下載該版本的 `grants.sqlite3`；也建議定期下載離線備份。不要刪除資料分支或強制推送歷史。Git 保存整份二進位檔，資料量大時需定期評估儲存空間，並非無限備份。

要還原：先停用 workflow，等待所有執行結束；下載目前版本作備份。請維護者從要還原的 commit 取出 SQLite，執行完整性檢查後，以**新 commit** 提交到 `grant-data`（不改 main、不 force push）。須將同一成功 commit 的 SQLite、JSON 與報告一起還原，保持雜湊一致。以下是 SQLite 完整性檢查範例，不能單獨推送而沿用不同版本的報告：

```bash
# GOOD_COMMIT 換成 History 中確認的完整 commit SHA
 git show GOOD_COMMIT:grants.sqlite3 > restored.sqlite3
 python -c "import sqlite3; db=sqlite3.connect('file:restored.sqlite3?mode=ro',uri=True); assert db.execute('PRAGMA integrity_check').fetchone()[0]=='ok'; assert not db.execute('PRAGMA foreign_key_check').fetchall(); db.close()"
 mv restored.sqlite3 grants.sqlite3
# 再取出同一 GOOD_COMMIT 的 latest-report.json 及 announcements.json（如該版本有）
# 完成一致版本驗證後，將全部檔案以新 commit 保存；不要 force push
```

上述檢查只需 Python 標準函式庫；也可用 SQLite 工具執行 `PRAGMA integrity_check`（應為 ok）及 `PRAGMA foreign_key_check`（應無資料列）。還原後重新啟用 workflow、手動執行一次（不要勾 initialize），確認成功再恢復每日排程。還原只回復該時點，之後的新增資料可能需要重新擷取。

本機可執行 `python -m grant_watch.daily --initialize` 首次建立；之後執行 `python -m grant_watch.daily`。預設資料在忽略提交的 `var/`，本機執行不會自動推送 GitHub。測試命令仍為 `python -m pytest -q`，新增離線測試涵蓋每日重跑、更新、Excel 欄位、來源／詳情／匯出失敗保護、缺失／損壞資料庫與重疊執行。

## 第四階段：本機公告查詢網頁

新增 Streamlit 繁體中文搜尋、篩選、詳細證據及每日狀態頁；唯讀讀取既有 SQLite，不初始化資料庫、不改動每日排程。Windows 安裝、資料快照準備與啟動指令見 [本機網頁說明](docs/windows-web.md)。網頁依賴獨立放在 `requirements-web.txt`，未公開部署。

## 第五階段：私人雲端部署準備

Streamlit 可使用 Secrets 中限定此 repo 的 Contents 唯讀憑證，從 `grant-data` 的同一 commit 安全讀取成功快照；支援快取、自動檢查、手動重讀與失敗保留。繁體中文查詢、篩選與證據功能沿用既有網頁。

請依 [私人雲端部署文件](docs/private-cloud.md) 人工審查、合併及設定私人 app。文件列出平台 OAuth 過度授權限制、一個私人 app 的額度、替代方案、Secrets、部署參數與驗收步驟；此階段不自動部署或合併。

雲端讀取亦支援根層 `GITHUB_TOKEN` Secrets，或在 `[grant_data]` 設定 `token = ""` 明確使用公開 repo 匿名讀取。伺服器日誌提供不含憑證的 HTTP 狀態碼與失敗階段，詳見上述部署文件的「資料讀取修正與診斷」。
