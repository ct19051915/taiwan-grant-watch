# 第七階段：Public 儲存庫每日更新

## 診斷（2026-11-10，台灣時間）

Repository 為 Public；daily.yml API 狀態為 active。原本 `Require private repository` 步驟要求 `.private == true`，因此目前公開設定會阻擋正式蒐集。這是程式中的限制，並非 Public repo 不支援 Actions。查閱時僅有早期 push 事件的失敗紀錄（沒有 job），未找到最近的 schedule 執行；不能將這些歷史失敗直接歸因為 Private 檢查，也不能聲稱已觀察到每日排程成功。

本次移除此限制，保留 `0 0 * * *`（UTC 00:00＝台灣 08:00）。排程使用預設 main 的 workflow，PR 分支修改須人工合併才會生效。GitHub 排程可能延遲或略過，不能保證準點。Public repo 若 60 天無 repository 活動，排程可能被 GitHub 自動停用；可在 Actions 檢查並 Enable workflow。無需改為 Private。

## 權限與寫入

- workflow 預設 `contents: read`，蒐集工作不保留 checkout 憑證；連官方網站的工作沒有寫入 Token。
- 獨立 publish job 才有 `contents: write`，其他權限未授予。只會在 main、非 dry-run、蒐集與驗證成功時執行。
- 使用內建短效 GITHUB_TOKEN，不需新增 PAT、Secrets、Actions 寫入或 PR 寫入權限。GitHub Contents 權限無法限制單一分支，main 寫入限制由 workflow 守門與儲存庫規則補強。
- 執行環境的連線憑證對 Actions 管理設定端點回 403，無法查閱 repository 的預設／組織上層限制。不要因此擴大 Token 權限；若發布遭拒，維護者應查 Settings → Actions → General、組織政策及 grant-data ruleset。預設權限可保留唯讀，由 job 明確要求 Contents 寫入。
- 每次從 grant-data 還原既有 SQLite，在暫存副本蒐集／分類；歷史公告不刪除，依來源 ID／官方 URL 去重。來源、詳情、匯出或完整性檢查失敗，正式資料不變。
- 新增公告資料 `announcements.json`，驗證 JSON 與 SQLite 公告 ID／筆數、兩檔 SHA-256，以及原有公告 ID 皆保留後才產生發布 artifact。
- publish 再比對遠端資料 commit 是否仍與蒐集起點一致；改變或消失即拒絕覆寫。三檔 `grants.sqlite3`、`latest-report.json`、`announcements.json` 同 commit、一般 push，禁止 force push。初始化僅適用確實沒有資料分支時。
- concurrency 防止重疊寫入，不取消執行中的工作；GitHub 最多保留一個 pending run，多次觸發可能取代等待項目。
- Public repo 的資料與歷史版本均公開。main／PR 僅提交程式、文件與合成測試，不提交 SQLite、實際設定檔、Token 或 Secrets。

## 手動 workflow_dispatch 測試

PR 審查期間，在有 Actions 執行權限的帳號執行：

```bash
gh workflow run daily.yml --repo ct19051915/taiwan-grant-watch \
  --ref fix/phase-seven-public-daily -f dry_run=true -f initialize=false
gh run list --repo ct19051915/taiwan-grant-watch --workflow daily.yml --limit 5
```

或 Actions → Daily grant tracking → Run workflow → Branch 選 `fix/phase-seven-public-daily`，勾 dry_run，不勾 initialize。若 GitHub UI 尚未顯示 PR 分支新增的 input，使用 CLI；workflow_dispatch 已存在 main，因此可指定分支版本。測試應 collect 成功、publish skipped。摘要確認 failed_sources 為空、42 筆或更多；下載 `grant-snapshot-*` 可取得 SQLite 及兩份 JSON，`grant-report-*` 另含 Excel。確認 grant-data commit 沒有改變。dry-run 報告的 published 指本機候選資料完成，**不代表已推送遠端**；遠端寫入只以 publish job 成功及資料 commit 為準。

人工合併後，先用 main 的 dry_run 測試，再選 main、不勾 dry_run、不勾 initialize 執行正式補跑：

```bash
gh workflow run daily.yml --repo ct19051915/taiwan-grant-watch \
  --ref main -f dry_run=false -f initialize=false
```

確認 collect/publish 皆成功，grant-data 出現新 commit 且三檔齊全，latest-report 的 status=success、published=true、failed_sources=[]。再觀察下一次台灣 08:00 排程紀錄。失敗查看紅色步驟／摘要／artifact，不以先前成功快照推論後續工作成功。

## Streamlit 更新驗收

現有 app 依 grant-data commit SHA 下載同版本 DB／報告，預設 300 秒檢查，活躍頁面定期重新執行，按「重新讀取資料」可跳過快取。PR 額外檢查報告中的 database_sha256；舊版報告無該欄位仍相容。錯誤繼續保留舊成功版本。

合併且正式補跑成功後，在已部署 app 按「重新讀取資料」，比對「資料版本」前 12 碼與 grant-data 新 commit、「最後成功保存」與 completed_at；無公告內容變更也應出現新保存時間。不需為資料分支更新重新部署 app。程式變更則需 Streamlit 正常取得 main 新版本。

Public 匿名模式可在 Streamlit 平台 Secrets 設定 `[grant_data]`、repository、`token = ""`、cache_seconds=300；不要把實際憑證加入 repo。保留現有可用設定即可。匿名 API 可能受共享 IP 額度限制，失敗時先查安全日誌，不改用寫入 Token。

## 已執行驗證

- 全部離線測試 146 通過；包含重跑去重、失敗保留、歷史 ID、JSON／DB 雜湊、Streamlit 版本切換，以及直接執行 workflow 發布 shell 的本機 bare Git 測試（正常發布、過期候選拒絕、資料分支消失拒絕）。
- actionlint 1.7.7 通過；pip check、git diff --check 通過。
- 使用正式 42 則資料副本重新連線 5 個官方來源：全部 verified，新增 0、更新 0、未變 42、失敗 0，耗時 162.444 秒。SQLite 完整性、外鍵、歷史 ID 及 JSON 一致性通過。涵蓋中央 4 來源與地方臺北市 1 來源，不代表全臺來源已涵蓋。
- 正式 Public grant-data 匿名讀取驗證，以及使用真實前後 42 筆副本的 Streamlit AppTest 切換驗證；不代表已對部署中的 app 進行正式資料更新驗收。
- GitHub 實際 [workflow_dispatch dry-run #42749105946](https://github.com/ct19051915/taiwan-grant-watch/actions/runs/42749105946) 成功（台灣 2026-11-10 11:23～11:26）；日誌確認 Contents: read、五站全部 verified、新增 0／更新 0／未變 42／失敗 0、歷史 ID 及快照驗證通過，兩份 artifact 上傳成功，publish skipped。正式 grant-data 仍為 `f375833f0338c6d6b5e82101af26842354732559`，main 亦未改動。
- 本次未合併 main，未寫入正式 grant-data；正式寫入及下次 schedule 驗收須於人工合併後依上述方式完成。

官方說明：[排程與 Public 60 天停用規則](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)、[GITHUB_TOKEN 最小權限](https://docs.github.com/en/actions/security-for-github-actions/security-guides/automatic-token-authentication)、[手動執行](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)。
