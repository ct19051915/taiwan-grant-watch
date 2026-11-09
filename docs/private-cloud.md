# 第五階段：Streamlit Community Cloud 私人部署

## 可行性與權限邊界（2026-11-09 查核）

可在 Windows、iPad、手機以瀏覽器登入私人 app，無須本機持續開機。每日追蹤仍由既有 GitHub Actions 執行；本階段不修改排程、main 或 grant-data 的寫入流程。PR 合併與部署均由人工作業。

Community Cloud 支援私人 repo，私人 repo 的 app 預設私人，且同時僅允許一個私人 app。不得為騰出額度而將此 app 或 repo 改為公開。若已有私人 app，先停止此部署，評估刪除不再需要的舊 app 或採下述替代方案。

**應用程式資料存取**使用 fine-grained PAT：僅此 repo，Contents: Read-only（Metadata 為 GitHub 必要唯讀），不授予 Actions、Administration 或任何寫入權限。GitHub 的 Contents 權限無法限縮至單一分支或兩個檔案，因此此 token 能讀整個指定 repo，不是檔案級 ACL。程式只呼叫 grant-data 的 commit 與兩個檔案端點。

**平台原始碼授權有額外限制**：Community Cloud 目前要求 repo 管理員以 GitHub OAuth `repo` scope 授權，才能建立唯讀 deploy key；OAuth scope 本身超出唯讀。應用程式 PAT 不能替代平台 OAuth。若安全要求是「連平台授權也必須嚴格唯讀」，Community Cloud 無法完全符合，請勿授權或部署；改用有 OIDC／VPN 身分閘道的私有主機／容器服務，由管理員安裝僅此 repo 的唯讀 deploy key，資料仍用 Contents 唯讀 PAT（或唯讀 GitHub App installation token）。此替代方案需要另外建置驗證與主機，不由此 PR 自動部署。若接受平台此權限模型，才繼續以下步驟。

## 人工部署步驟

1. 人工審查並合併第五階段 PR；確認 repo 仍為 Private，grant-data 包含 `grants.sqlite3`、`latest-report.json`，每日 Actions 最近一次成功。不要把兩檔複製至 main，不要提供公開下載 URL。
2. GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens。Resource owner 選 repo 擁有者，Repository access 選 Only select repositories → taiwan-grant-watch，Contents 設 Read-only。設定有限效期並記錄輪替提醒；組織如需核准／SSO，先完成核准。不要使用 classic `repo` PAT，也不要把 token 貼到聊天、PR、日誌或截圖。
3. 使用 repo 管理員登入 https://share.streamlit.io ，連接 GitHub 並閱讀平台 OAuth 權限；私人 repo 未出現時檢查 GitHub OAuth／組織政策，勿改 repo 可見度。檢查新增 deploy key 為唯讀。此處連接 GitHub 的授權與步驟 2 的資料 token 是兩件事。
4. Create app → 從既有私人 repo 部署，參數如下。Advanced settings 中**明確選擇 Python 3.12**，貼入 Secrets（下面範例），不要依賴平台預設 Python。
5. 確認私人部署與額度後才按 Deploy。若介面要求公開才能繼續，立即停止，採替代方案。此 PR 不代為操作部署。
6. Settings → Sharing → Who can view this app → **Only specific people can view this app**。僅邀請需要的 viewer 電子郵件，不授予 GitHub 寫入權限。開發者的 GitHub 權限亦可影響可見性，需定期檢查。使用者以 Google 或單次郵件連結登入。
7. 先用未受邀的無痕瀏覽器確認**看不到公告**；再用受邀帳號在 Windows、iPad、手機驗證登入、搜尋、篩選、詳情與來源證據。此私人身分驗證由平台負責，程式不提供另一組密碼。
8. 對照 app 顯示的最後成功保存時間／commit 與私人 grant-data；等下一次既有每日工作成功，確認無需重部署即可取得新 commit。資料 token 撤銷時應顯示錯誤並保留舊快照；完成驗收後恢復有效 token 並 Reboot app。

| 部署欄位 | 值 |
| --- | --- |
| Repository | ct19051915/taiwan-grant-watch（Private） |
| Branch | main（人工合併後） |
| Main file path | streamlit_app.py |
| Python | 3.12 |
| Dependency file | 根目錄 requirements.txt |
| App visibility | Only specific people can view this app |
| Data branch | grant-data（程式固定，非部署分支） |

Secrets（TOML，實際 token 僅輸入平台 Secrets）：

```toml
[grant_data]
repository = "ct19051915/taiwan-grant-watch"
token = "在平台填入限定此repo的唯讀fine-grained PAT"
cache_seconds = 300
```

範例另見 `.streamlit/secrets.toml.example`。本機如需驗證，可在忽略的 `.streamlit/secrets.toml` 設定；真正檔案不可提交。Secrets 更改或 token 輪替後 Reboot，確保舊資源快取與舊憑證從程序釋放；撤銷舊 token。不要啟用 HTTP debug／輸出 Secrets。無 Secrets 時保留原本本機唯讀模式；main 不含 DB，因此雲端漏設時會顯示無法讀取資料，不建立空資料庫。

## 快取、更新與失敗語意

伺服器共享一個有鎖的資源快取；預設每 300 秒檢查（範圍 60～3600 秒）。活躍網頁用 fragment 定期重新執行以檢查更新；休眠、背景分頁暫停或斷線時不保證準時，恢復瀏覽或按「重新讀取資料」會再檢查。手動按鈕可略過 TTL。失敗也有 TTL，避免每次篩選反覆打 API。

先解析 grant-data 的 immutable commit SHA，再從該 SHA 讀兩個檔案，避免每日推送時混用版本。SHA 未改僅查 metadata；有新版本時要求報告 `status=success`、`published=true`、有 `completed_at`，資料庫 quick_check 正常且具必要公告欄位，並驗證唯讀 adapter 可解析後才替換目前版本。畫面分開顯示「最後成功保存」（報告時間）與公告內容最後更新時間；無公告異動仍可看到每日成功時間。成功快照不能證明後續每日工作沒有失敗，仍需查看 Actions。

下載只連 `https://api.github.com`，不跟隨重新導向，不採用 API 回傳的 download_url；設連線／讀取 timeout，DB 上限 100 MiB、報告及 metadata 上限 2 MiB。超過上限或私有資料的 GitHub Contents API 限制時保留舊版本並報錯，需另評估私有物件儲存方案。

候選資料寫入程序私人臨時目錄，檔案權限 0600，正式查詢使用 SQLite mode=ro/query_only，不修改來源。舊成功檔案在程序存續期間保留；沒有公開下載元件，static serving 明確關閉。錯誤訊息不含例外本文、回應本文、Authorization、token 或路徑。首次失敗停止顯示；後續失敗明確告知資料可能過期，持續使用前次成功版本，不刪除或覆寫它。服務重啟、休眠回收後本機快取不保證存在，須重新取得 GitHub 成功快照；grant-data 才是持久來源。資料交由 Streamlit 平台代管運算，平台管理員／有開發權限者不在「未授權閱覽者」隔離範圍內。

## 相容性與維護

Python 3.12 與既有 CI 一致，requirements.txt 現在同時包含 Streamlit、tzdata 和追蹤依賴；requirements-web.txt 保留為相容入口。無額外系統套件、SQLite 使用 Python 標準函式庫。部署後要檢查安裝日誌；平台未來 Python 支援變動時需重新評估，不可直接依賴自動升級。

本機驗證：`python -m pip install -r requirements-dev.txt`、`python -m pytest -q`、`python -m pip check`。單元測試只用合成資料，禁止真實網路；驗證一致版本、TTL、手動更新、失敗保留、初次失敗、憑證遮蔽與 Streamlit 雲端介面。CI 沿用原 Tests workflow；每日 workflow 僅修正既有 schedule 的 YAML 縮排，維持 `0 0 * * *`、main 條件與所有追蹤步驟。部署權限與真實 Secrets 尚需前述人工驗收，測試通過不代表已部署。

## 官方依據

- [私人 app、額度與 viewer](https://docs.streamlit.io/deploy/streamlit-community-cloud/share-your-app)
- [OAuth、唯讀 deploy key 與平台限制](https://docs.streamlit.io/deploy/streamlit-community-cloud/status)
- [Secrets 操作](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)
- [部署與 Python 選擇](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)
- [GitHub fine-grained PAT](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens)
- [GitHub Contents API 大小限制](https://docs.github.com/en/rest/repos/contents#get-repository-content)
