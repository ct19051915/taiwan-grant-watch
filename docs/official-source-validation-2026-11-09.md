# 官方來源重新驗證：2026-11-09

本輪已驗證 **2 個官方來源、31 筆來源公告**，成功寫入 `var/grants.sqlite3`。兩次實際網路擷取的第二次均新增 0 筆。此數量是來源公告數，不是唯一補助計畫數：同一計畫由不同官方網站轉載時，因官方網址及來源不同，仍可能各有一筆。

本輪沿用第一階段程式，對 `extractors.py` 增加可選的 HTML `title_selector` 與來源 `exclude_title_contains`，並讓來源排除詞改變時重設驗證狀態；新增可重跑的實際驗證腳本與來源設定。原有 50 項測試與合成 fixture 未修改，以執行前後 SHA-256 核對。

## 官方來源、HTTP 狀態及筆數

實際驗證執行區間：2026-11-09 14:48:26–14:48:38（Asia/Taipei）。機器報告使用 UTC：06:48:26–06:48:38。

| 來源 ID／機關 | 實際公告端點 | HTTP | 首次新增 | 第二次新增／未變 | 已存公告 | 失敗原因 |
|---|---|---|---:|---|---:|---|
| sme-business／經濟部中小及新創企業署 | https://www.sme.gov.tw/list-tw-2275 | 200 | 3 | 0／3 | 3 | 無 |
| moea-notices-rss／經濟部 | https://www.moea.gov.tw/Mns/populace/news/NewsRSSdetail.aspx?Kind=2 | 200 | 28 | 0／28 | 28 | 無 |

- 中企署業務消息第一頁 20 列，3 列符合「補助／補貼／獎勵」；以公告列 `.title` 取標題、`time` 取公告日期，不包含序號或日期於計畫名稱。
- 經濟部訊息公告 RSS 原有 40 筆符合關鍵字，再排除 12 筆平台維護、檢舉獎勵法規及智慧財產研討活動公告，保留 28 筆。排除詞明列於 `data/active-sources.json`，沒有更改通用關鍵字規則。
- 此篩選仍是候選企業補助公告，不保證全部適用所有企業，也不代表目前仍在申請期間；包含核定結果及不同申請對象，需依官方資格人工複核。
- 尚未擷取完整歷史、翻頁與附件。未由清單／RSS 明確提供的截止日、金額、資格、類別保留 NULL；沒有猜測或合成。

另檢查經濟部本部新聞 RSS `https://www.moea.gov.tw/Mns/populace/news/NewsRSSdetail.aspx?Kind=1`，HTTP 200，關鍵字結果 1 筆為台電用電成本預算補貼新聞，未選作本次企業補助來源，也未寫入 SQLite。這是內容不適合的選源結果，並非 HTTP 或解析失敗。

## 連線、robots 與使用規範的分辨

目前執行環境回報：`network_policy.mode=unrestricted`、`state=enforced`、`observations_current=true`。本輪沒有更動雲端設定、代理、TLS 信任或網路規則。

預設執行沙箱仍無法連接繼承代理；依 runtime 支援流程，以 `require_escalated` 執行同一唯讀請求後成功，這是沙箱的 socket 限制，**不是雲端代理的目的地政策拒絕**。後續請求都保留代理、TLS 驗證、既有 robots 檢查、至少 3 秒間隔與有限重試。

| 檢查 | 中企署 | 經濟部 |
|---|---|---|
| robots.txt | https://www.sme.gov.tw/robots.txt，200；User-agent: *，未禁止清單與詳情路徑 | https://www.moea.gov.tw/robots.txt，200；只對本爬蟲禁止 /MNS_OLD/，此次未使用 |
| 資料開放宣告 | https://www.sme.gov.tw/article-tw-2522-11061，200 | https://www.moea.gov.tw/Mns/populace/content/ContentFoot.aspx?menu_id=13863，200 |
| 使用條件 | 政府資料開放授權條款第1版；利用時須註明出處 | 政府資料開放授權條款第1版；利用時須註明出處 |
| 公告頁／RSS | 200，可解析 | 200，可解析 |

本輪沒有遇到代理政策拒絕、遠端 4xx／5xx、robots 禁止或解析失敗。原先 CONNECT 403 屬於上輪歷史結果，不能沿用成這次的失敗原因。未嘗試繞過登入、驗證碼、反爬蟲或 robots 限制。

驗證腳本會記錄每個實際 HTTP 回應的 URL、狀態、時間、回應 SHA-256 與本地檔案。若將來失敗，分辨 `proxy_denied`、`tls_error`、`robots_disallowed`、`robots_unavailable`、`http_or_connection_error`、`parse_or_configuration_error`；不將空結果誤判為成功。

## 代表性真實公告

兩站代表公告的詳情網址均另行 GET 驗證為 HTTP 200，且內容符合對應計畫：

- 中企署：[公告116年度「深科技驅動中小企業跨域創新計畫」企業跨域研發補助申請須知](https://www.sme.gov.tw/article-tw-2275-15216)，公告日 2026-10-14。
- 經濟部：[公告受理第三梯次「提升商業服務業營運效能強化韌性計畫」個案補助申請須知－多店升級（115年11月）](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=124430)，公告日 2026-11-02。

## 去重與內容更新

正式資料庫首次擷取新增 3 + 28 筆；第二次重新連線擷取，各為 `inserted=0, updated=0, unchanged=3/28`。重跑前後正式總數均為 31。

內容更新驗證使用上述中企署真實公告：清單中只有標題及日期，詳情頁有真實計畫內文。將正式資料庫以 SQLite backup 複製到 `update-replay.sqlite3`，在副本中補入**實際取得的官方內文**：

- 更新 `inserted=0, updated=1`；UUID 與首次擷取時間不變，內容雜湊及 updated_at 改變，總筆數不變。
- 同一完整內文再次重播：`inserted=0, updated=0, unchanged=1`。
- 正式資料庫未寫入驗證性變更；沒有替真實公告編造內容。

這是「真實清單到真實詳情的內容補全」重播驗證，**沒有觀察到官網在本次期間自然修改同一篇公告**，不能宣稱已驗證某次實際官網歷史修訂。原有內容更新單元測試亦重新通過。

## 匯出與可重跑指令

在專案根目錄執行，保留現有 `.venv`：

```bash
.venv/bin/python -m scripts.verify_official_sources
# 只執行擷取，可使用現有 CLI：
.venv/bin/python -m grant_watch --sources data/active-sources.json fetch --source sme-business --source moea-notices-rss
.venv/bin/python -m grant_watch --sources data/active-sources.json sources
.venv/bin/python -m grant_watch --sources data/active-sources.json export var/announcements.csv
.venv/bin/python -m grant_watch --sources data/active-sources.json export var/announcements.xlsx
.venv/bin/python -m pytest -q
```

此雲端執行沙箱若無法接代理，仍須走支援的 require_escalated 流程；不要改成直連或停用 TLS 驗證。

正式 CSV／Excel 各 31 筆，已重新讀回並比對 SQLite 的完整官方網址集合與筆數。`var/announcements.csv` 與 `var/announcements.xlsx` 可供審查；31 筆皆來自官方清單或 RSS，測試的合成 fixture 不在正式資料庫。

本次完整機器證據：`var/verification/20261109T064826944792Z/report.json`；同目錄含回應原始檔與 SHA-256、正式資料庫驗證前備份、隔離更新副本及當次匯出。`var/` 沿用既有 gitignore，不會隨程式碼提交。所有產物保留在目前工作目錄，未 commit、push、合併或發布。

`data/sources.json` 保留原有 27 筆候選與歷史觀察，避免把初始候選清單誤當作動態狀態。**本輪啟用的兩個具體端點在 `data/active-sources.json`**，具有不同來源 ID，不會因預設 CLI 載入候選清單而重設成功來源。設定檔的 verified 是本次檢查快照；目前執行狀態仍以 SQLite sources／runs 為準。

其他候選（產業發展署、產業技術司、國科會與 22 縣市）本輪未重新檢查，沒有新增成功宣稱。

## 最終自動化檢查

- `python -m pytest -q`：**54 passed（0.52 秒）**，原有 50 項未修改，另新增 4 項標題／排除詞設定的回歸測試。
- 執行前後 SHA-256 核對原有全部測試檔及合成 fixture：全部相同。
- `python -m pip check`：No broken requirements found；`git diff --check` 通過。
- SQLite `PRAGMA integrity_check`：ok；兩個啟用來源均 verified／success。
- 最終正式 CSV 與 Excel 各讀回 31 筆，網址集合與 SQLite 完全相符，未含合成測試公告。
