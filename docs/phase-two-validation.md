# 第二階段：官方來源驗證與實作結果

基底為 GitHub `main` 的 `55dd602`（PR #1 已合併），新分支 `feat/phase-two-official-sources`。未從舊功能分支開發；原工作目錄的未提交內容完整保留。

檢查日期：2026-11-09（Asia/Taipei）。精確逐站時間、請求 URL、HTTP 狀態、SHA-256、引用原文與實際公告皆收錄在 [機器證據](phase-two-evidence.json)。

## 實測結果

27 個候選（5 個中央機關、22 縣市）均已實際發出請求。最新狀態：**5 verified、14 pending、8 failed**。

本輪累計保存 **50 筆真實來源公告**，包括高雄首輪成功取得的 8 筆。最新複查成功的 5 個來源取得 **42 筆**；高雄後來由公告清單重新導向首頁而無法解析，最新狀態因此改為 failed，已存 8 筆保留。這不是 50 個不同企業補助計畫，也不代表 22 縣市均已完成啟用。

| 機關／候選 | 最新狀態 | 最新實測取得 | 累計已存 | 端點／未完成原因 |
|---|---|---:|---:|---|
| 經濟部／moea | verified | 27 | 27 | [經濟部](https://www.moea.gov.tw/Mns/populace/news/NewsRSSdetail.aspx?Kind=2)；清單、robots、授權頁與真實公告擷取通過。 |
| 經濟部中小及新創企業署／sme | verified | 3 | 3 | [中小及新創企業署](https://www.sme.gov.tw/list-tw-2275)；清單、robots、授權頁與真實公告擷取通過。 |
| 經濟部產業發展署／ida | verified | 6 | 6 | [產業發展署](https://www.ida.gov.tw/ctlr?PRO=news.NewsList&type=eBulletin&lang=0)；清單、robots、授權頁與真實公告擷取通過。 |
| 經濟部產業技術司／doit | pending | 0 | 0 | [產業技術司](https://www.moea.gov.tw/Mns/doit/news/NewsRSSdetail.aspx?sno=31&Kind=1)；已找到並解析官方最新消息 RSS，目前僅 2 則新聞，沒有符合補助關鍵字的公告，不以新聞冒充補助。 |
| 國家科學及技術委員會／nstc | verified | 4 | 4 | [產學合作相關單位](https://www.nstc.gov.tw/folksonomy/rfpList)；清單、robots、授權頁與真實公告擷取通過。 |
| 臺北市政府／taipei | verified | 2 | 2 | [產業發展局](https://doed.gov.taipei/News.aspx?n=69F827A50BC26F06&sms=9391BC948EC0703C)；清單、robots、授權頁與真實公告擷取通過。 |
| 新北市政府／new-taipei | pending | 0 | 0 | [經濟發展局](https://www.economic.ntpc.gov.tw/)；經發局 robots.txt 回傳 HTML，未能確認 robots 規範，保守停止。 |
| 桃園市政府／taoyuan | pending | 0 | 0 | [經濟發展局](https://edb.tycg.gov.tw/News.aspx?n=3887&sms=10027)；補助清單 HTTP 200，可見 20 筆真實清單項目；授權頁所在 www.tycg.gov.tw 的 robots HTTP 428，未寫入公告庫。 |
| 臺中市政府／taichung | failed | 0 | 0 | [經濟發展局](https://www.economic.taichung.gov.tw/41064/Lpsimplelist)；ReadTimeout: connection failed |
| 臺南市政府／tainan | failed | 0 | 0 | [經濟發展局](https://economic.tainan.gov.tw/)；robots.txt 重新導向過多 |
| 高雄市政府／kaohsiung | failed | 0 | 8 | [經濟發展局](https://edbkcg.kcg.gov.tw/News.aspx?n=9A7F03ABA05E4DEF&sms=BE8A73D3A0435784)；首輪 200 且取得 8 筆；複查清單 302 → Default.aspx，selector 找不到公告列。 |
| 基隆市政府／keelung | pending | 0 | 0 | [產業發展處](https://www.klcg.gov.tw/)；robots.txt 回傳 HTML，需人工檢查 |
| 新竹市政府／hsinchu-city | failed | 0 | 0 | [產業發展處](https://www.hccg.gov.tw/)；公告頁 HTTP 403 |
| 嘉義市政府／chiayi-city | pending | 0 | 0 | [建設處](https://www.chiayi.gov.tw/)；robots.txt 回傳 HTML，需人工檢查 |
| 新竹縣政府／hsinchu-county | pending | 0 | 0 | [產業發展處](https://www.hsinchu.gov.tw/News.aspx?n=2390&sms=10056)；補助專區可連線；第一頁多為社福、農業及宣導，尚未確認企業補助端點與授權。 |
| 苗栗縣政府／miaoli | pending | 0 | 0 | [工商發展處](https://www.miaoli.gov.tw/News.aspx?n=287&sms=9464)；最新公告可連線；本頁補助關鍵字未提供企業補助申請，尚需工商處專門來源與授權審查。 |
| 彰化縣政府／changhua | pending | 0 | 0 | [經濟暨綠能發展處](https://www.chcg.gov.tw/ch2/rssnews1.aspx)；已找到並連線公布欄 RSS；尚需確認企業適用公告、解析及授權。 |
| 南投縣政府／nantou | pending | 0 | 0 | [建設處](https://www.nantou.gov.tw/)；robots.txt 回傳 HTML，需人工檢查 |
| 雲林縣政府／yunlin | pending | 0 | 0 | [建設處](https://www.yunlin.gov.tw/News.aspx?n=1400&sms=9733)；工商清單可連線；補助整合平台為導覽頁，尚需深入企業專區與授權審查。 |
| 嘉義縣政府／chiayi-county | failed | 0 | 0 | [經濟發展處](https://www.cyhg.gov.tw/)；HTTP 503: retries exhausted |
| 屏東縣政府／pingtung | failed | 0 | 0 | [城鄉發展處](https://www.pthg.gov.tw/)；HTTP 503: retries exhausted |
| 宜蘭縣政府／yilan | failed | 0 | 0 | [工商旅遊處](https://www.e-land.gov.tw/)；robots.txt 重新導向缺少 Location |
| 花蓮縣政府／hualien | failed | 0 | 0 | [觀光處／建設處（待確認分工）](https://www.hl.gov.tw/)；HTTP 500: retries exhausted |
| 臺東縣政府／taitung | pending | 0 | 0 | [財政及經濟發展處](https://www.taitung.gov.tw/News.aspx?n=15377&sms=12663)；花東基金專區可連線，但以季度執行進度、PDF 為主，未確認企業直接申請公告端點。 |
| 澎湖縣政府／penghu | pending | 0 | 0 | [建設處](https://www.penghu.gov.tw/)；robots.txt 回傳 HTML，需人工檢查 |
| 金門縣政府／kinmen | pending | 0 | 0 | [建設處](https://www.kinmen.gov.tw/cp.aspx?n=2598759C833BBB75)；補助公開專區可連線，內容為各單位連結；尚需建設／產業單位公告與授權審查。 |
| 連江縣政府／lienchiang | pending | 0 | 0 | [產業發展處](https://www.matsu.gov.tw/)；本次入口可連線；第一輪曾出現 proxy CONNECT 403。尚未確認企業公告端點與授權。 |

`verified` 表示實際清單與授權審查通過、robots 允許且至少取得一筆補助候選公告；不保證所有候選均可供企業申請。`pending` 表示規範、授權或企業來源尚未確認，或本頁沒有補助公告；`failed` 表示本次已嘗試的 HTTP、重新導向或解析作業失敗。5xx 訊息未能證明錯誤由機關源站產生，不能直接解讀為政府網站故障。

官方連線沒有關閉 TLS、繞過 robots、解驗證碼或使用非官方替代資料。robots 404 依現有 Client 視為未設定限制；200 須解析規則；HTML、428、410 等不確定回應均停止。每站至少 3 秒，最多 5 MB；批次驗證每次只嘗試一次，人工複查留下不同結果。

## 真實資料、分類與申請狀態

目前分類：{"企業補助計畫": 16, "非補助公告": 12, "待人工確認": 22}。核定、租稅法規、學研與附件資訊不足等均保留原公告及依據，不一律列為企業補助。

申請狀態（評估日 2026-11-09）：{"開放申請": 7, "即將開放": 0, "已截止": 4, "核定結果": 12, "無法確認": 27}。

狀態採臺灣日期，明示日期區間含截止日；起日未明、不一致、多個申請步驟或附件尚未解析時保留「無法確認」。僅有「公告日起」時，才使用清單明示公告日並保存規則引用；國科會「徵求期間」另取明示日期，絕不填成公告日。沒有捏造截止日或年度。此版是日期層級，未判斷當日幾點截止、經費是否提前用罄或附件內其他條件，仍應以官方原文為準。

國科會徵求專區同時包含學術與產學案件；本輪 4 筆並非全部企業直接申請。臺北兩筆為補助要點清單，詳情主要在 PDF 附件；本版沒有解析附件，不假造資格與日期。產發署部分公告 HTML 只列法源與附件，也保留待人工確認。

代表性真實公告：
- [中企署：116 年度企業跨域研發補助申請須知](https://www.sme.gov.tw/article-tw-2275-15216)。
- [產發署：研發轉型支持個案補助申請須知及受理截止日](https://www.ida.gov.tw/ctlr?PRO=news.NewsView&id=43346&type=eBulletin)。
- [國科會：116 年度科普產品製播推廣產學合作計畫](https://www.nstc.gov.tw/folksonomy/rfpDetail/58ff35a0-e94a-4b3e-b50f-9c9ed4c88a51?l=ch)。

## 跨站關聯及相容性

建立 **2 組 possible_same_plan 候選關聯**，以明示年度、引號內計畫名稱及梯次一致為依據，附雙方網址、標題、雜湊與 requires_review。跨站轉載原始公告均保留；同一來源原有去重規則維持。關聯僅供複核，沒有自動合併計畫。

第一階段公告、SQLite、分類與 Excel 功能保留。衍生資料新增 application_states、plan_relations、source_checks，沒有刪除原資料或改動原公告表欄位。分類依據、官方 URL、公告日期、截止日期、狀態評估日與關聯 ID 一併匯出；未明示的欄位為 NULL。

本次工作使用獨立驗證資料庫，不覆寫原工作目錄的 var/grants.sqlite3。原 27 筆歷史候選 data/sources.json 與第一階段 active-sources.json 保留，新設定為 data/phase-two-sources.json。

## 重跑與證據

```bash
python -m scripts.verify_phase_two
# 輸出 var/phase-two/<UTC時間>/report.json、逐站結果、原始回應、SQLite、CSV、XLSX。
# 若重用已完成結果，會核對設定雜湊並保留原檢查時間；不是重新連線驗證。
python -m scripts.verify_phase_two --resume var/phase-two/<UTC時間> --retry-source taichung
python -m pytest -q
```

每個來源獨立失敗，不中止整批；中途結果逐站保存，重新驗證會保存舊結果。resume 保留既有公告，即使目前來源失敗也不刪除先前真實資料。重播測試是同批真實公告的 SQLite 去重檢查，**不是第二次網路擷取**；本次另做的實網複查則有各自時間與請求紀錄。

原始 HTTP 回應保留於本地 var/，不提交大量 HTML。機器證據保留實際回應雜湊、路徑、完整官方公告與可用詳情引用；可依上列指令在相同環境重新檢查。來源內容會隨時間改變，重跑數量不保證相同。

## 驗證

- 原有 80 項測試未修改，全部通過；另新增 23 項測試，共 **103 passed**。
- 測試網路封鎖沿用原有 fixture，所有測試為明確合成資料，未流入正式實測資料庫。
- SQLite integrity_check = ok；真實公告重播新增 0；CSV／Excel 各讀回 50 筆，官方網址集合與 SQLite 一致。
- python -m pip check：No broken requirements found；git diff --check 通過。
