# 護理排班系統

這是一個依照 [規格文件 v1.1.3](./docs/spec_v1.1.3.md) 與本地工作副本 [prompt/排班系統規格.md](./prompt/排班系統規格.md) 實作的 v1 示範應用，提供：

- 行事曆排班總覽與手動調整
- 護理師、科別、班別、職級、技能的完整 CRUD
- 自然語言規則轉 DSL、DSL 驗證、反向翻譯與版本啟用
- 最佳化排班任務、SSE 進度串流、結果套用與快照回復
- 專案狀態持久化、audit log、本機 LLM 設定儲存

## 技術選型

- 後端：FastAPI
- 資料庫：SQLite
- 前端：原生 JavaScript SPA
- 串流：Server-Sent Events
- 最佳化：內建啟發式求解器（保留 solver 參數接口）

## 目錄結構

```text
NurseRoster/
├─ .venv/
│  ├─ bin/
│  └─ pyvenv.cfg
├─ assets/
│  └─ ui/
│     ├─ calendar-view.svg
│     ├─ data-maintenance.svg
│     ├─ optimization.svg
│     └─ rules-maintenance.svg
├─ app/
│  ├─ __init__.py
│  ├─ main.py
│  ├─ config.py
│  ├─ db.py
│  ├─ seed_data.py
│  ├─ data/
│  │  └─ nurse_roster.sqlite3
│  ├─ services/
│  │  ├─ __init__.py
│  │  ├─ dsl_tools.py
│  │  ├─ jobs.py
│  │  ├─ llm_service.py
│  │  ├─ optimizer.py
│  │  ├─ repository.py
│  │  └─ rule_engine.py
│  └─ static/
│     ├─ app.css
│     ├─ app.js
│     └─ index.html
├─ logs/
│  └─ app.log
├─ docs/
│  └─ spec_v1.1.3.md
├─ LICENSE
├─ prompt/
│  └─ 排班系統規格.md
├─ tests/
│  ├─ test_dsl_tools.py
│  └─ test_optimizer.py
├─ README.md
├─ todo.md
├─ requirements.txt
├─ run_app.sh
├─ run_app.command
└─ run_app.bat
```

## 功能說明

### 1. 行事曆

- 依期間與科別顯示護理師班表
- 點擊班表格子即可修改班別與備註
- 所有手動調整會建立新的 project snapshot
- 右側可查看衝突摘要與歷史快照並執行回復

### 2. 規則維護

- 先建立規則 metadata，再用自然語言產生 DSL
- 轉譯結果會以 SSE 串流顯示
- 可直接貼上 DSL 驗證並另存版本
- 每個版本都可單獨採用成 active version

### 3. 資料維護

- 支援 `nurses`、`departments`、`shift_codes`、`job_levels`、`skill_codes`
- 前端提供新增、編輯、刪除的完整 CRUD

### 4. 最佳化

- 以 JSON 設定各科別 coverage
- 建立 job 後以 SSE 顯示 progress / log / result
- 成功後可將結果套用回行事曆並生成 snapshot

### 5. DSL 測試頁

- 支援自然語言 → DSL 串流測試
- 支援 DSL 驗證與反向翻譯

### 6. 系統設定

- 可設定 `fallback` 或 `openai`
- OpenAI API Key 會寫入本機 SQLite，不會回顯到 UI
- 若未設定 API Key 或請求失敗，系統會自動退回 fallback 邏輯

## 本地端啟動

這個專案的設計是「不用先手動進入 `.venv`」。  
你只要執行啟動檔，系統會自己建立 `.venv`、安裝套件、啟動服務。

### 給完全不熟的人：先看這段

1. 先找到整個專案資料夾 `NurseRoster`
2. 不要手動進入 `.venv`
3. 不要先輸入 `source .venv/bin/activate`
4. 直接照下面對應自己電腦系統的方法啟動

### macOS 最簡單方式

1. 打開 `NurseRoster` 資料夾
2. 找到 `run_app.command`
3. 直接雙擊它
4. 第一次啟動時，系統可能需要幾十秒安裝套件，請等它跑完
5. 成功後會自動打開瀏覽器，進入 `http://127.0.0.1:8765`

補充：

- `run_app.command` 內部已經會自動用 `bash` 執行 `run_app.sh`
- 所以通常不需要你自己先處理 `.venv` 或 `./run_app.sh` 的執行權限問題

### macOS 如果雙擊沒反應，再用終端執行

1. 打開「終端機」
2. 輸入 `cd `，注意 `cd` 後面有一個空格
3. 把 `NurseRoster` 資料夾拖曳到終端機視窗
4. 按 `Enter`
5. 再輸入以下指令：

```bash
bash run_app.sh
```

請注意：

- 這裡建議新手優先用 `bash run_app.sh`
- 不需要先進入 `.venv`
- 不需要先輸入 `source .venv/bin/activate`

如果你已經熟悉終端，也可以用：

```bash
./run_app.sh
```

### Linux 啟動方式

1. 打開終端機
2. 進入 `NurseRoster` 資料夾
3. 輸入：

```bash
bash run_app.sh
```

如果你熟悉 Linux 權限設定，也可以用：

```bash
./run_app.sh
```

### Windows 啟動方式

1. 打開 `NurseRoster` 資料夾
2. 找到 `run_app.bat`
3. 直接雙擊它
4. 第一次啟動時請稍等，系統會自動建立環境並安裝套件
5. 成功後會自動打開瀏覽器，進入 `http://127.0.0.1:8765`

### 啟動腳本會自動做什麼

你不用自己做下面這些事，啟動檔會自動完成：

1. 檢查電腦裡是否有 Python 3
2. 在專案根目錄建立 `.venv`
3. 安裝或更新 `requirements.txt` 內的套件
4. 啟動 FastAPI 本地服務
5. 自動打開瀏覽器到 `http://127.0.0.1:8765`

### 如何確認已成功啟動

看到以下任一種情況，就代表本地端已成功啟動：

- 瀏覽器自動開啟 `http://127.0.0.1:8765`
- 終端機看到 `Uvicorn running on http://127.0.0.1:8765`
- 畫面出現「護理排班系統」首頁

### 第一次啟動比較慢是正常的

第一次啟動通常會比較久，因為系統正在：

- 建立 `.venv`
- 安裝 FastAPI、uvicorn 等套件
- 初始化本機資料庫

只要終端機還在跑，就先不要關掉。

### 常見問題 1：為什麼我以為要先進入 `.venv`？

不用。

原因是 `run_app.sh` 內部本來就會自動執行這一步：

```bash
source "$VENV_DIR/bin/activate"
```

也就是說，啟動腳本自己會幫你進入虛擬環境，你不用手動做。

如果你不小心已經手動進入 `.venv`，要退出時請輸入：

```bash
deactivate
```

輸入後按 `Enter`，就會離開 `.venv`。

### 常見問題 2：為什麼 `./run_app.sh` 不能跑？

有些電腦或壓縮/解壓縮之後，檔案執行權限可能會不見。  
如果你輸入 `./run_app.sh` 失敗，請改用：

```bash
bash run_app.sh
```

這是給新手最穩定的方式。

### 如何關閉本地端

- 如果是用終端機啟動：在該終端機視窗按 `Ctrl + C`
- 如果是雙擊啟動：關閉那個終端機視窗即可

## 測試方式

安裝依賴後可執行：

```bash
python3 -m unittest discover -s tests
```

目前測試涵蓋：

- DSL 解析與驗證
- 排班最佳化硬限制判斷

## 重要資料位置

- SQLite 資料庫：`app/data/nurse_roster.sqlite3`
- Log：`logs/app.log`

## 已知限制

- v1 最佳化採啟發式求解器，主要目標是快速產生可用班表與進度回饋；若後續需要更強的可行性證明，可將 `optimizer.py` 替換為 OR-Tools CP-SAT。
- OpenAI Responses API 目前採同步請求後再回放成 SSE token；若未來需要真正逐 token provider streaming，可再擴充 `llm_service.py`。

## 變更摘要

- 建立完整後端 API、資料模型、快照、audit log 與前端 SPA
- 內建 30 位護理師 seed、預設規則與示範專案
- 補齊一鍵啟動檔與基本測試
- 保留原本倉庫中的 `docs/` 規格文件與 `assets/ui/` SVG 介面示意
