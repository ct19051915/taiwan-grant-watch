# 企業補助公告辨識與資料品質驗證

本輪逐筆讀取現有 SQLite 的 31 筆真實來源公告，全部 31 個官方詳情頁 HTTP 200，遵守既有 robots、TLS 與限速；沒有合成公告寫入正式資料庫。

| 類別 | 筆數 | 定義／範例 |
|---|---:|---|
| 企業補助計畫 | 14 | 可辨識的申請方案／資格規範，例如企業跨域研發、關鍵醫材、商業服務業節能。不是「目前一定受理中」。 |
| 非補助公告 | 13 | 本輪全為純核定／入選／審查結果通知，例如多店升級入選名單。此分類表示不作為申請計畫，並非否認與補助的關聯。 |
| 待人工確認 | 4 | 申請主體待釐清、資格僅引用法規，或標題與內文梯次矛盾。 |

31 筆是來源公告數，同計畫跨站轉載仍各自保留，不宣稱唯一計畫數。原始 announcements、sources、source_items、runs 四表與擷取前 SQLite 備份逐筆雜湊完全相同。

## 判斷規則與證據

規則版本 `enterprise-grants-v1.1`。先檢查官方 URL、HTTP、內文長度與原始 HTML，再辨識採購、結果通知、行政資訊、申請主體與資助機制。確認企業補助時必須有官方內文的企業／營業對象與申請或資格資訊；不以 AI、研發或補助等標題關鍵字單獨決定。

每筆另存摘要（官方原文前 600 字）、分類理由、公告階段、欄位證據原文、來源網址、抓取時間、HTTP 狀態及原始檔 SHA-256。快照重播會驗證原始 HTML 雜湊，並重新解析比對內文，不能只替換 JSON 文字冒充官網。

一般新聞及採購公告在這批 31 筆中為 0，不為湊齊類別捏造真實案例；相關誤判情境已有明示合成資料的離線測試。

## 需要人工確認的 4 筆

1. [公告受理第四梯次「提升商業服務業營運效能強化韌性計畫」整合型補助申請須知（115年10月）](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=124125)：標題梯次與官方內文受理梯次不一致，需向主辦單位確認。
2. [公告自即日起受理「115年度國際展會觀光消費卡」之業務補助申請。](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=124158)：資格僅引用補助辦法條款，需核對法規／附件後確認企業申請資格。
3. [公告「經濟部116年補助公協會參加國際展覽計畫申請須知」。](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=124320)：申請主體為公協會；企業是否可直接申請需另確認，不推定企業資格。
4. [公告自即日起受理116年度「推動國際會議及展覽在臺辦理」之業務補助申請。](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=124330)：資格僅引用補助辦法條款，需核對法規／附件後確認企業申請資格。

其中「第四梯次」標題的官方內文確實寫「第3梯次（智慧營運整合）」，系統保留雙方文字，不自行更正。其餘資格如僅寫補助辦法第4條等法條，未擅自展開為「所有企業均可申請」。

## 14 筆計畫的欄位品質

- 11 筆有對象／資格原文，其中 5 筆僅能確認資助對象範圍，標為 `eligibility_scope_only`，不等於取得完整申請資格；其餘 3 筆資格 NULL。
- 4 筆有明示額度（兩個計畫各被兩站刊載）：跨域研發每案上限 900 萬元及補助比例限制；創育機構個別上限 700 萬元、聯合上限 1,500 萬元及明示條件。原文完整保留，不換算或挑最高額當成人人可領。
- 12 筆有受理期間原文，其中 10 筆能確認單一截止日期；2 筆單店方案有店家與服務提供者不同期間，單一截止日 NULL、各組期間分開保存。另 2 筆醫材／衛星計畫本頁未明示受理截止，保持 NULL。
- 8 筆有單一官方列示申請網址；2 筆單店方案有兩個不同角色網址，不任選一個，其餘未明示者 NULL。未登入、未提交申請，亦未假稱外部申請平台本身已通過連線驗證。
- 「公告日起／即日起」保留文字，開始日不自動套公告日期；申請期、計畫執行期與結案期分開判斷，申請時刻與經費用罄條件保留於受理期間原文。

以下 10 筆計畫的欄位仍待補，不與「分類待人工確認」4 筆混為同一狀態：

| 公告 | 欄位提示 |
|---|---|
| [公告「經濟部115年度補助企業布建海外通路計畫申請須知」。](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=122847) | eligibility_scope_only, amount_not_stated, application_url_not_stated |
| [公告受理「提升商業服務業營運效能強化韌性計畫」個案補助-單店導入方案上架申請。](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=122864) | eligibility_scope_only, multiple_application_windows, multiple_application_urls, amount_not_stated, application_url_not_stated |
| [公告115年度「商業服務業系統節能專案補助」委託辦理單位、受理申請期間、補助結案期限及其展延條件及相關申請事宜。](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=122897) | eligibility_not_stated, amount_not_stated |
| [公告「產業升級創新平台輔導計畫」主題式研發計畫-關鍵醫材國產量能自主整合補助計畫](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=123139) | deadline_not_stated, amount_not_stated, application_url_not_stated |
| [公告受理第三梯次「提升商業服務業營運效能強化韌性計畫」整合型補助申請須知（115年7月）](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=123192) | eligibility_scope_only, amount_not_stated |
| [公告受理第二梯次「提升商業服務業營運效能強化韌性計畫」個案補助申請須知-多店升級（115年8月）](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=123502) | eligibility_not_stated, amount_not_stated |
| [公告「產業升級創新平台輔導計畫」主題式研發計畫-自適應衛星通訊酬載與多軌衛星地面終端開發補助計畫。](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=123664) | deadline_not_stated, amount_not_stated, application_url_not_stated |
| [公告受理「提升商業服務業營運效能強化韌性計畫」個案補助-單店導入方案上架申請](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=124126) | eligibility_scope_only, multiple_application_windows, multiple_application_urls, amount_not_stated, application_url_not_stated |
| [公告「經濟部辦理116年度第1次補助公司或商號參加海外國際展覽申請須知」。](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=124332) | eligibility_scope_only, amount_not_stated, application_url_not_stated |
| [公告受理第三梯次「提升商業服務業營運效能強化韌性計畫」個案補助申請須知-多店升級（115年11月）](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=124430) | eligibility_not_stated, amount_not_stated |

`amount_not_stated`／`eligibility_not_stated` 等表示本頁缺乏可確認的欄位；不代表該計畫不提供補助。部分資料可能在附件或完整申請須知，這輪未自動解析附件。

## 31 筆逐筆結果

| 公告／官方網址 | 分類 | 判斷理由 | 單一截止日期 |
|---|---|---|---|
| [公告「提升商業服務業營運效能強化韌性計畫」個案補助-多店升級（第一梯）入選名單](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=122626) | 非補助公告 | 純核定／入選／審查結果通知；與補助相關，但不是申請計畫或徵件規範 | NULL |
| [公告115年度「活絡商圈補助計畫」審查結果](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=122840) | 非補助公告 | 純核定／入選／審查結果通知；與補助相關，但不是申請計畫或徵件規範 | NULL |
| [公告「提升商業服務業營運效能強化韌性計畫」整合型補助（第一梯）入選名單](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=122841) | 非補助公告 | 純核定／入選／審查結果通知；與補助相關，但不是申請計畫或徵件規範 | NULL |
| [公告「經濟部115年度補助企業布建海外通路計畫申請須知」。](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=122847) | 企業補助計畫 | 官方內文明示企業或營業對象、資助措施及申請／資格資訊 | 2026-10-30 |
| [公告受理「提升商業服務業營運效能強化韌性計畫」個案補助-單店導入方案上架申請。](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=122864) | 企業補助計畫 | 官方內文明示企業或營業對象、資助措施及申請／資格資訊 | NULL |
| [公告「115年度次世代產業新創企業發展計畫」新創驅動高齡驗證獎勵核定通過名單](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=122871) | 非補助公告 | 純核定／入選／審查結果通知；與補助相關，但不是申請計畫或徵件規範 | NULL |
| [公告「115年度次世代產業新創企業發展計畫」深科技新創共創獎勵核定通過名單](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=122872) | 非補助公告 | 純核定／入選／審查結果通知；與補助相關，但不是申請計畫或徵件規範 | NULL |
| [公告「115年度次世代產業新創企業發展計畫」國際拔尖潛力新創獎勵核定通過名單](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=122873) | 非補助公告 | 純核定／入選／審查結果通知；與補助相關，但不是申請計畫或徵件規範 | NULL |
| [公告115年度「商業服務業系統節能專案補助」委託辦理單位、受理申請期間、補助結案期限及其展延條件及相關申請事宜。](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=122897) | 企業補助計畫 | 官方內文明示企業或營業對象、資助措施及申請／資格資訊 | 2026-08-31 |
| [公告「產業升級創新平台輔導計畫」主題式研發計畫-關鍵醫材國產量能自主整合補助計畫](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=123139) | 企業補助計畫 | 官方內文明示企業或營業對象、資助措施及申請／資格資訊 | NULL |
| [公告受理第三梯次「提升商業服務業營運效能強化韌性計畫」整合型補助申請須知（115年7月）](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=123192) | 企業補助計畫 | 官方內文明示企業或營業對象、資助措施及申請／資格資訊 | 2026-07-31 |
| [公告「提升商業服務業營運效能強化韌性計畫」整合型補助（第二梯_AI能源管理）入選名單](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=123335) | 非補助公告 | 純核定／入選／審查結果通知；與補助相關，但不是申請計畫或徵件規範 | NULL |
| [公告受理第二梯次「提升商業服務業營運效能強化韌性計畫」個案補助申請須知-多店升級（115年8月）](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=123502) | 企業補助計畫 | 官方內文明示企業或營業對象、資助措施及申請／資格資訊 | 2026-08-31 |
| [公告「產業升級創新平台輔導計畫」主題式研發計畫-自適應衛星通訊酬載與多軌衛星地面終端開發補助計畫。](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=123664) | 企業補助計畫 | 官方內文明示企業或營業對象、資助措施及申請／資格資訊 | NULL |
| [公告「經濟部115年度補助企業布建海外通路計畫」之受補助廠商名單(如附件)。](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=123734) | 非補助公告 | 純核定／入選／審查結果通知；與補助相關，但不是申請計畫或徵件規範 | NULL |
| [公告「提升商業服務業營運效能強化韌性計畫」整合型補助（第三梯次_智慧營運整合）入選名單](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=123859) | 非補助公告 | 純核定／入選／審查結果通知；與補助相關，但不是申請計畫或徵件規範 | NULL |
| [公告「『大南方新矽谷推動方案』115年度智慧雨林產業創生補助計畫-智慧製造領域【主題案】、【示範案】及【擴散案】」核定補助名單](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=124016) | 非補助公告 | 純核定／入選／審查結果通知；與補助相關，但不是申請計畫或徵件規範 | NULL |
| [公告受理第四梯次「提升商業服務業營運效能強化韌性計畫」整合型補助申請須知（115年10月）](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=124125) | 待人工確認 | 標題梯次與官方內文受理梯次不一致，需向主辦單位確認 | 2026-10-30 |
| [公告受理「提升商業服務業營運效能強化韌性計畫」個案補助-單店導入方案上架申請](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=124126) | 企業補助計畫 | 官方內文明示企業或營業對象、資助措施及申請／資格資訊 | NULL |
| [公告自即日起受理「115年度國際展會觀光消費卡」之業務補助申請。](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=124158) | 待人工確認 | 資格僅引用補助辦法條款，需核對法規／附件後確認企業申請資格 | NULL |
| [公告「提升商業服務業營運效能強化韌性計畫」個案補助-多店升級（第二梯次）入選名單](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=124159) | 非補助公告 | 純核定／入選／審查結果通知；與補助相關，但不是申請計畫或徵件規範 | NULL |
| [公告「經濟部115年度補助企業布建海外通路計畫」受補助廠商名單（如附件）。](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=124175) | 非補助公告 | 純核定／入選／審查結果通知；與補助相關，但不是申請計畫或徵件規範 | NULL |
| [公告116年度經濟部中小及新創企業署「深科技驅動中小企業跨域創新計畫」企業跨域研發補助申請須知](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=124251) | 企業補助計畫 | 官方內文明示企業或營業對象、資助措施及申請／資格資訊 | 2026-12-07 |
| [公告「經濟部116年補助公協會參加國際展覽計畫申請須知」。](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=124320) | 待人工確認 | 申請主體為公協會；企業是否可直接申請需另確認，不推定企業資格 | 2026-11-23 |
| [公告自即日起受理116年度「推動國際會議及展覽在臺辦理」之業務補助申請。](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=124330) | 待人工確認 | 資格僅引用補助辦法條款，需核對法規／附件後確認企業申請資格 | 2026-11-23 |
| [公告「經濟部辦理116年度第1次補助公司或商號參加海外國際展覽申請須知」。](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=124332) | 企業補助計畫 | 官方內文明示企業或營業對象、資助措施及申請／資格資訊 | 2026-11-23 |
| [116年度「創育機構補助計畫」自即日起受理至115年12月21日止](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=124421) | 企業補助計畫 | 官方內文明示企業或營業對象、資助措施及申請／資格資訊 | 2026-12-21 |
| [公告受理第三梯次「提升商業服務業營運效能強化韌性計畫」個案補助申請須知-多店升級（115年11月）](https://www.moea.gov.tw/MNS/populace/news/News.aspx?kind=2&menu_id=41&news_id=124430) | 企業補助計畫 | 官方內文明示企業或營業對象、資助措施及申請／資格資訊 | 2026-11-30 |
| [公告「『大南方新矽谷推動方案』115年度智慧雨林產業創生補助計畫-智慧製造領域【主題案】、【示範案】及【擴散案】」核定補助名單](https://www.sme.gov.tw/article-tw-2275-15153) | 非補助公告 | 純核定／入選／審查結果通知；與補助相關，但不是申請計畫或徵件規範 | NULL |
| [公告116年度經濟部中小及新創企業署「深科技驅動中小企業跨域創新計畫」企業跨域研發補助申請須知](https://www.sme.gov.tw/article-tw-2275-15216) | 企業補助計畫 | 官方內文明示企業或營業對象、資助措施及申請／資格資訊 | 2026-12-07 |
| [116年度「創育機構補助計畫」自即日起受理至115年12月21日止](https://www.sme.gov.tw/article-tw-2275-15285) | 企業補助計畫 | 官方內文明示企業或營業對象、資助措施及申請／資格資訊 | 2026-12-21 |

## 儲存、匯出及重跑

僅新增 `quality_runs`、`quality_documents`、`quality_assessments`，不改寫原始四表。`latest_announcement_assessments` view 每公告僅一筆最新評估；不同輸入或規則版本保留歷史，同一快照重跑不重複新增評估。

快照重播會先比對當前公告標題、網址與內容雜湊，拒絕以舊快照更新已改變的公告。當原始內容雜湊或公告 URL 變更，view 的 `is_stale=1`，表示舊分類需重評；不干涉既有擷取及 upsert。另存原始 HTML 備份，不將詳情補全回寫 announcements，避免影響現有去重與更新行為。

```bash
# 沿用現有環境；逐筆重新抓官方詳情
.venv/bin/python -m scripts.classify_announcements
# 以本輪真實官方快照離線重播
.venv/bin/python -m scripts.classify_announcements --snapshot var/quality/20261109T080655Z
.venv/bin/python -m pytest -q
```

預設網路沙箱若無法連接代理，依既有 runtime 指引使用受支援的 require_escalated 流程；不改代理、不停用 TLS、不繞過網站限制。本輪未更動環境設定。

- `var/quality/enterprise-grants.xlsx`：14 筆計畫及說明。
- `var/quality/all-classifications.xlsx`：31 筆完整分類、4 筆待人工確認、10 筆計畫欄位待補及說明。
- `var/quality/all-classifications.csv`：31 筆完整分類。
- `var/quality/report.json`／`assessments.json`：統計、逐筆欄位與來源證據。
- 本輪快照：`var/quality/20261109T080655Z`，逐頁原始 HTML、抓取時間、完整內文及擷取前資料庫備份。

已讀回兩份 Excel 核對筆數與官方網址；未知欄位為空白，Excel／CSV 延續公式注入防護。以上產物在既有忽略目錄 var/，不隨程式碼提交。

## 測試與保留狀態

全部 80 項測試通過：既有 54 項測試及 fixture 未修改，SHA-256 核對一致；新增 26 項分類、日期語境、多角色、無資料、採購、新聞、原始快照完整性、歷史、過期狀態與匯出測試。

SQLite integrity_check 為 ok、foreign_key_check 無錯誤；原始 31 筆全部保留，最新分類 31 筆、is_stale=0。未合併、未發布，沒有開發網頁、排程或通知。
