# 官方來源初次驗證紀錄（歷史）

> 此為初次開發時的歷史結果。網路調整後已成功驗證 2 個來源，請見 [最新報告](official-source-validation-2026-11-09.md)。

2026-11-09 第一階段開發。實際驗證成功來源：**0**；正式公告資料：**0**。目前不能聲稱已成功追蹤兩個官方來源。

環境狀態回報 restricted 網路政策、enforced；自訂 allowed_hosts 為空，僅啟用 package_managers 預設網域組。該組不包含下列政府網站。本次依使用者要求，未修改既有環境設定。

## 實際唯讀請求

先在預設沙箱請求 `https://www.sme.gov.tw/robots.txt`，得到代理連線失敗。依環境 runtime 指引，改以受支援的 require_escalated 流程重試，保留既有代理與 TLS 驗證：

| 機關 | 檢查網址 | 時間（UTC） | 實際結果 | 狀態 |
|---|---|---|---|---|
| 中小及新創企業署 | https://www.sme.gov.tw/robots.txt | 2026-11-09 06:25:31 | HTTP CONNECT 403 Forbidden，curl exit 56 | pending / network_blocked |
| 經濟部 | https://www.moea.gov.tw/robots.txt | 2026-11-09 06:25:31 | HTTP CONNECT 403 Forbidden，curl exit 56 | pending / network_blocked |

回應為雲端代理 envoy 的 CONNECT 拒絕，尚未建立至政府網站的 HTTPS 連線。這不是政府網站本身回傳的 robots 規則、登入要求或反爬蟲判定。沒有抓取公告清單，沒有以替代網域或直連繞過限制。

## 待完成範圍

- 其餘 25 個候選（產業發展署、產業技術司、國科會與 22 縣市）未實際檢查，最後檢查時間為 NULL。
- 27 筆目前均只是候選官方入口；仍需在網路允許後確認現行網域、業務單位、官方 API／RSS 或公告列表端點、使用規範、parser 與實際公告。
- 至少兩個真實來源的完整擷取、重跑去重及公告欄位人工對照仍待完成。沒有用離線 fixture 作為真實來源證據。

若要解除目前的外部限制，請由使用者在環境設定中增加 `www.sme.gov.tw` 與 `www.moea.gov.tw` 的網域存取權；可能的重新導向或資料端點網域要在確認後另加。**本次僅記錄需求，未更動草稿、腳本或網路設定，也未發布。** 權限開通後，先重試 robots 並人工確認使用規範，找到至少兩個實際公告端點、設定解析器，再使用 CLI 擷取，不能只把 JSON 狀態改為 verified。

## 本次開發驗證

- Python 3.12.14；`python -m pytest -q`：50 passed（0.53 秒），全部為離線合成資料與暫存資料庫測試。
- `python -m pip check`：No broken requirements found。
- CLI `sources`：27 筆 pending；`fetch --source sme --source moea` 因候選尚未啟用而正確回傳 exit 1，並記錄逐來源失敗。該 CLI 結果不等同上述實際網路請求結果。
- SQLite 重開與重跑不重複新增的測試通過；CSV／Excel 合成資料往返及公式防護測試通過。
- 正式 `var/grants.sqlite3` 公告數 0、verified 來源數 0；兩種實際 CLI 匯出均只有欄位標題。
- `git diff --check` 通過；變更保留在工作目錄，未 commit、push、合併或發布。
