# 第八階段第一批：中央企業補助來源擴充

驗證日期：2026-11-10（台灣時間）。本 PR 僅準備程式與設定，須人工審查合併後才影響 main 的每日工作。

## 既有來源盤點

`data/sources.json` 原始名冊的中央 5 候選為經濟部、中小及新創企業署、產業發展署、產業技術司、國科會；其中候選狀態不是每日啟用狀態。

既有每日程式使用 `data/phase-two-sources.json` 中 5 個 verified 來源：經濟部 RSS、中小及新創企業署、產業發展署、國科會、臺北市。`data/active-sources.json` 是更早的 2 來源快照。這些歷史檔案保留，新的唯一每日名冊改為 `data/phase-eight-sources.json`，以 `enabled` 明確控制每日執行。

## 本批來源與實際測試

名冊共 12 個中央候選機關與 22 縣市。第一批每日只啟用 7 個來源：既有 5 個，加上數位產業署及產業技術司 RSS。未找到已驗證的官方企業補助 API；優先沿用已公布 RSS，無適用 RSS 的站點採公開 HTML，不呼叫未驗證的私有端點。JSON 介接能力保留。

下表 HTTP 是「清單／入口」請求結果，不代表公告解析、授權或詳情均通過。待審表示尚未完成可用端點／解析驗證。逐次請求的官方網址、UTC 時間與回應雜湊見 [機器可讀證據](phase-eight-evidence.json)。

|機關|官方清單／入口|方式|HTTP|本次符合標題公告數|每日啟用|實測結果／尚未支援原因|
|---|---|---|---|---:|---|---|
|經濟部|[moea-notices-rss](https://www.moea.gov.tw/Mns/populace/news/NewsRSSdetail.aspx?Kind=2)|rss|200|27|是|清單、授權與全部符合條件公告詳情通過|
|經濟部中小及新創企業署|[sme-business](https://www.sme.gov.tw/list-tw-2275)|html|200|3|是|清單、授權與全部符合條件公告詳情通過|
|經濟部產業發展署|[ida](https://www.ida.gov.tw/ctlr?PRO=news.NewsList&type=eBulletin&lang=0)|html|200|6|是|清單、授權與全部符合條件公告詳情通過|
|經濟部產業技術司|[doit](https://www.moea.gov.tw/Mns/doit/news/NewsRSSdetail.aspx?sno=31&Kind=1)|rss|200|0|是|RSS 可解析、授權通過；目前 feed 2 則新聞皆無補助標題關鍵字，正常空批次（allow_empty），不推定無補助|
|國家科學及技術委員會|[nstc](https://www.nstc.gov.tw/folksonomy/rfpList)|html|200|4|是|清單、授權與全部符合條件公告詳情通過|
|臺北市政府|[taipei](https://doed.gov.taipei/News.aspx?n=69F827A50BC26F06&sms=9391BC948EC0703C)|html|200|2|是|清單、授權與全部符合條件公告詳情通過|
|新北市政府|[new-taipei](https://www.economic.ntpc.gov.tw/)|html|未取得|0|否|robots.txt 回傳 HTML，需人工檢查|
|桃園市政府|[taoyuan](https://edb.tycg.gov.tw/News.aspx?n=3887&sms=10027)|html|200|0|否|robots.txt HTTP 428，保守停止|
|臺中市政府|[taichung](https://www.economic.taichung.gov.tw/41064/Lpsimplelist)|html|200|7|否|詳情擷取失敗：找不到已設定官方詳情節點；需重新審查 selector|
|臺南市政府|[tainan](https://economic.tainan.gov.tw/)|html|未取得|0|否|robots.txt 重新導向過多|
|高雄市政府|[kaohsiung](https://edbkcg.kcg.gov.tw/News.aspx?n=9A7F03ABA05E4DEF&sms=BE8A73D3A0435784)|html|200|8|否|後續地方批次：清單／詳情本次通過，但第一批僅保留既有臺北市來源，尚未排入每日更新|
|基隆市政府|[keelung](https://www.klcg.gov.tw/)|html|未取得|0|否|robots.txt 回傳 HTML，需人工檢查|
|新竹市政府|[hsinchu-city](https://www.hccg.gov.tw/)|html|未取得|0|否|公告頁 HTTP 403|
|嘉義市政府|[chiayi-city](https://www.chiayi.gov.tw/)|html|未取得|0|否|robots.txt 回傳 HTML，需人工檢查|
|新竹縣政府|[hsinchu-county](https://www.hsinchu.gov.tw/News.aspx?n=2390&sms=10056)|html|200|0|否|尚未完成可存取的授權條款審查或企業公告端點設定（入口 HTTP 200，未視為公告蒐集成功）|
|苗栗縣政府|[miaoli](https://www.miaoli.gov.tw/News.aspx?n=287&sms=9464)|html|200|0|否|尚未完成可存取的授權條款審查或企業公告端點設定（入口 HTTP 200，未視為公告蒐集成功）|
|彰化縣政府|[changhua](https://www.chcg.gov.tw/ch2/rssnews1.aspx)|html|200|0|否|尚未完成可存取的授權條款審查或企業公告端點設定（入口 HTTP 200，未視為公告蒐集成功）|
|南投縣政府|[nantou](https://www.nantou.gov.tw/)|html|未取得|0|否|robots.txt 回傳 HTML，需人工檢查|
|雲林縣政府|[yunlin](https://www.yunlin.gov.tw/News.aspx?n=1400&sms=9733)|html|200|0|否|尚未完成可存取的授權條款審查或企業公告端點設定（入口 HTTP 200，未視為公告蒐集成功）|
|嘉義縣政府|[chiayi-county](https://www.cyhg.gov.tw/)|html|未取得|0|否|HTTP 503: retries exhausted|
|屏東縣政府|[pingtung](https://www.pthg.gov.tw/)|html|未取得|0|否|HTTP 503: retries exhausted|
|宜蘭縣政府|[yilan](https://www.e-land.gov.tw/)|html|未取得|0|否|robots.txt 重新導向缺少 Location|
|花蓮縣政府|[hualien](https://www.hl.gov.tw/)|html|未取得|0|否|HTTP 500: retries exhausted|
|臺東縣政府|[taitung](https://www.taitung.gov.tw/News.aspx?n=15377&sms=12663)|html|200|0|否|尚未完成可存取的授權條款審查或企業公告端點設定（入口 HTTP 200，未視為公告蒐集成功）|
|澎湖縣政府|[penghu](https://www.penghu.gov.tw/)|html|未取得|0|否|robots.txt 回傳 HTML，需人工檢查|
|金門縣政府|[kinmen](https://www.kinmen.gov.tw/cp.aspx?n=2598759C833BBB75)|html|200|0|否|尚未完成可存取的授權條款審查或企業公告端點設定（入口 HTTP 200，未視為公告蒐集成功）|
|連江縣政府|[lienchiang](https://www.matsu.gov.tw/)|html|未取得|0|否|proxy CONNECT 403: destination denied|
|數位發展部數位產業署|[adi-events](https://moda.gov.tw/ADI/news/events/772)|html|200|1|是|清單、授權與全部符合條件公告詳情通過|
|經濟部能源署|[energy](https://www.moeaea.gov.tw/ECW/populace/news/NewsRSSdetail.aspx?Kind=3)|rss|200|14|否|清單 14 則中 13 則詳情通過，1 則舊公告連結已失效（news_id=16612）；暫不啟用，避免阻斷每日批次|
|環境部|[moenv](https://www.moenv.gov.tw/information-service/convenience-services/subsidy/moenv/3129.html)|html|200|0|否|已找到並讀取補助公告清單；本批未完成授權及企業公告解析／詳情驗證，留待後續批次（入口 HTTP 200，未視為公告蒐集成功）|
|勞動部|[mol](https://www.mol.gov.tw/)|html|200|0|否|尚未完成可存取的授權條款審查或企業公告端點設定（入口 HTTP 200，未視為公告蒐集成功）|
|農業部|[moa](https://www.moa.gov.tw/)|html|200|0|否|尚未完成可存取的授權條款審查或企業公告端點設定（入口 HTTP 200，未視為公告蒐集成功）|
|國家發展委員會|[ndc](https://www.ndc.gov.tw/)|html|200|0|否|尚未完成可存取的授權條款審查或企業公告端點設定（入口 HTTP 200，未視為公告蒐集成功）|
|經濟部商業發展署|[moea-commerce](https://www.aoc.gov.tw/)|html|200|0|否|尚未完成可存取的授權條款審查或企業公告端點設定（入口 HTTP 200，未視為公告蒐集成功）|

## 擷取與資料保留

- 能源署已改用正式 `www.moeaea.gov.tw` 布告欄 RSS 並實測：14 則清單、13 則詳情成功，1 則舊公告（news_id=16612）轉向官方不存在頁面。異常完整保留，不以刪除這筆或抓整頁導覽代替修復，能源署先 disabled。原 energy.gov.tw 受阻並非整個能源署不可存取。
- 依已驗證 selector / RSS 欄位擷取名稱、公告日期及官方連結；主管機關為來源設定的官方機關，不猜測轉載公告的實際補助主辦單位。
- 詳情原文使用既有可稽核規則擷取截止日、金額與資格；明示的不同申請期間衝突時保留空值。申請截止日不採用計畫執行結束日。詳情缺失、PDF／外站附件才有的欄位不推測。
- 數位產業署是伺服器輸出的風琴式 HTML：依 `.accordion-item` 的標題與 `#qaH數字` 永久連結組成官方詳情 URL；已與官方首頁直連逐一比對。建立日期由 `.articleInfo .infoDate span` 取得，非更新日期。授權宣告 CC0 1.0 已檢查。
- RSS 增加 Dublin Core 日期及 content:encoded 支援；HTML 可讀取 datetime 等明確屬性。所有來源沿用官方網域限制、TLS、robots、3 秒限速、5 MB 上限；不登入、不解驗證。
- 產業發展署詳情中的點閱／下載統計只從解析內文排除，避免每次抓取製造假更新；原始回應與 SHA-256 證據仍保留。
- 原公告與來源關聯保留；同 URL／來源 ID 去重；不同年度、梯次或跨站轉載不任意合併。詳情原文及擷取欄位進入內容雜湊，內文變更也能觸發更新。
- `announcement_versions` 與公告更新同交易保存修改前後版本；重跑不產生假版本，列表消失不刪歷史。舊 DB 可自動新增此表，但無法重建升級前未保存的歷史。
- 來源錯誤寫入每日 report 與 GitHub Actions artifact；任何來源／詳情失敗均不取代上次成功 DB。失敗候選 DB 的 runs 不發佈，故失敗歷史應查 Actions artifacts（保留 30 日），成功 DB 不能反映後續失敗。
- AI、智慧製造、數位轉型、節能減碳、研發創新採獨立多標籤、保留命中字詞；不取代「企業補助／非補助／待人工確認」判定。主題未命中時不指定類別。

## 分批與排程

- UTC `0 0 * * *`＝台灣每日 08:00，既有 workflow 不變；GitHub Actions 實際啟動可能延遲。
- 每日只載入 enabled 來源，最多 8 個；本批 7 個。整次網路預算 180 次請求、約 20 分鐘軟上限，超限停止新請求並回報失敗，保留成功快照；單一進行中請求仍受既有連線／讀取 timeout 約束。工作原有 45 分鐘硬上限保留。
- 地方批次先保留臺北市；其他 21 縣市列入名冊但 disabled。高雄本次可讀仍留待後批，臺中 7 則中 2 則詳情 selector 不符；不得因清單 HTTP 200 就啟用。
- 後續建議順序：修復／重驗臺中、高雄 → 其餘都會區 → 其他縣市；每批重新驗證 robots、授權、清單、全部符合公告詳情及每日耗時，再於 PR 調整 enabled，不將整份名冊直接交給每日工作。

## 第七階段排程相容性

已同步遠端 main 的第七階段修正（fd7f3b5）：公開 repository 已可使用每日排程，並保留 collect 唯讀、publish 才有寫入權限的分離架構、dry_run、JSON／DB 雜湊與歷史 ID 驗證。先前本機舊基準的私人 repository 限制不適用於目前 main；本 PR 不加入該限制、不改可見性，也不直接寫入正式 grant-data。PR 使用 dry_run 執行 GitHub 驗證，只有人工合併後才採用本批新來源於正式每日排程。

## 涵蓋率定義

Streamlit 顯示名冊中「已啟用、設定符合目前版本、資料庫曾成功抓取」的來源數／名冊數；中央分母僅本次盤點 12 機關，地方分母 22 縣市，不能宣稱涵蓋所有中央機關。顯示來源關聯的 DISTINCT 公告數（未經查詢篩選影響）。跨來源重複公告會各計一次，故來源數不可相加當作不同公告總數。正常空批次仍可顯示來源成功；零筆不代表無補助。

## 可重現指令

```bash
python -m pytest -q
python -m scripts.verify_phase_two --sources data/phase-eight-sources.json --output work/phase-eight-validation
python -m grant_watch.daily --db work/phase-eight/grants.sqlite3 --output work/phase-eight/first --initialize
python -m grant_watch.daily --db work/phase-eight/grants.sqlite3 --output work/phase-eight/replay
```

完整名冊驗證是人工執行，不加入每日 Actions；它可能抓取未啟用候選供審查，不會更改正式 grant-data。

## 驗證結果

- 完整自動化測試：`163 passed`，含原有 146 項、新增 17 項；既有歷史 ID 測試的 fixture 補上版本表外鍵關聯，保留原先「完整 baseline 下拒絕歷史 ID 消失」的驗證目的。涵蓋風琴清單、datetime 屬性、RSS 命名空間、明示日期／金額／資格、執行日不誤當截止日、舊 DB 遷移、版本原子交易、重跑去重、空批次、多標籤、涵蓋率分母、設定改變不得沿用成功狀態、預算、舊品質審查不遮蔽新評估及 Streamlit UI。
- 7 來源實網首跑：新增 43／更新 0／未變 0，171.059 秒，失敗 0。另一次獨立實網重跑：新增 0／更新 4／未變 39，174.384 秒，公告總數仍 43。比對歷史證實 4 筆差異全為產業發展署點閱次數；已加入針對該站的統計排除規則，原始回應未改寫。
- 將上述兩次獨立取得的官方原始回應交給最終解析器重新處理（離線重播、無新增網路請求）：首次新增 43，第二次新增 0／更新 0／未變 43；DB 維持 43 筆、43 個版本，證明點閱次數變動不再造成假更新。
- 最終版本再次實網首跑：新增 43／更新 0／未變 0，172.834 秒，失敗 0；SQLite integrity_check=ok、43 個版本；Excel 讀回 43 筆並包含主題欄位，真實快照 Streamlit AppTest 通過，涵蓋率中央 6/12、地方 1/22。
- 數位產業署範例實測：公告日 2026-10-22、截止日 2026-11-06；金額保留官方「50 %、新臺幣 2,000 萬為上限」原文，資格保留官方完整段落；執行期程 117 年 3 月 31 日未誤用為申請截止日。
- Python compileall 與 `git diff --check` 通過。正式 grant-data、main 與 repository 可見性未變更。

最終實網資料欄位完整度（非 NULL／43）：title 43/43；agency 43/43；announced_on 39/43；deadline 16/43；amount 5/43；eligibility 15/43；official_url 43/43。未知欄位維持 NULL。

最終 43 則分類：待人工確認 14；企業補助計畫 17；非補助公告 12。43 是公告數，並非 43 個已確認企業補助方案。

## GitHub 實際驗證

- [Tests CI](https://github.com/ct19051915/taiwan-grant-watch/actions/runs/42776596707)：163 passed。
- [每日流程 dry-run](https://github.com/ct19051915/taiwan-grant-watch/actions/runs/42776462704)：collect 成功，publish skipped；還原既有資料後共 43 則，新增 1／更新 38／未變 4，失敗來源 0，蒐集 172.435 秒，整個 collect 工作 3 分 15 秒，低於 45 分鐘上限。JSON／DB 雜湊及歷史 ID 檢查通過。
- 本次升級將詳情內文納入雜湊並補齊欄位，既有資料首次升級出現更新為預期；不刪歷史公告、不改既有公告 ID。修正點閱統計後的同回應重播無假更新。
- 執行前後 main 與 grant-data 遠端 SHA 完全相同；兩份 artifact 上傳成功。此處筆數及耗時來自 GitHub 公開日誌，執行環境下載 artifact 遭 HTTP 403，因此未宣稱已讀回該 artifact；本機 Excel／SQLite 讀回測試另已通過。
- GitHub dry-run 使用已同步第七階段的應用程式版本；之後僅補測試 fixture 與驗證文件，應用程式及來源設定未變。
