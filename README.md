# AI論文閱讀輔助系統

![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green)
![React](https://img.shields.io/badge/React%20%2B%20Vite-Frontend-61DAFB)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Database-336791)
![Ubuntu](https://img.shields.io/badge/Ubuntu%20VM-Deployment-E95420)

**AI論文閱讀輔助系統**是一個部署於學校 VM 的 Web-based AI academic reading assistant，主要目標是協助使用者上傳英文論文 PDF 後，自動完成論文解析、段落摘要、重點整理、中文翻譯、PDF 對照閱讀、文字與 PDF 標註、內容編輯、重新生成摘要與匯出閱讀資料。

系統採用 **React + FastAPI + PostgreSQL + background workers** 的架構，並整合學校 SSO 登入與學生個人 API Key 機制，使不同使用者能在各自帳號下管理自己的論文資料，並使用個人的 AI 服務額度進行摘要、翻譯與重新生成。

---

## 系統完成狀態

本專案目前已完成一套可部署於學校 VM 的 AI 論文閱讀輔助系統。系統已支援 PDF 論文上傳、背景解析、AI 摘要生成、中文翻譯、PDF 與文字對照閱讀、段落編輯、重點標註、全文摘要重新生成、匯出下載、刪除論文與多使用者資料隔離等功能。

部署版本已完成 FastAPI 後端、React 前端、PostgreSQL 資料庫、背景 worker、Apache reverse proxy 與 systemd 服務管理。使用者登入部分已整合學校 SSO，登入後系統會依使用者身份建立資料歸屬，確保不同使用者只能讀取與操作自己的論文資料。

最終版設計包含依登入使用者的 `user_account` 查詢學校 LLM Gateway 中的個人 API key，並在摘要、翻譯、重新生成與段落編輯等 LLM 任務中使用該使用者的 API key 呼叫模型。若提交版本尚未完成此部分，則可在本地測試模式下使用 `.env` 中的共用測試 API key 執行 LLM 功能。

---

## Overview

本系統的核心設計目標是將「論文閱讀」拆解為可由系統輔助完成的多個階段：

1. 使用者透過學校 SSO 登入系統。
2. 上傳英文論文 PDF。
3. 後端建立論文資料與背景任務。
4. worker 解析 PDF，擷取段落與結構。
5. 透過 AI 服務產生全文摘要、章節摘要、段落摘要與重點。
6. 自動建立中文翻譯任務，產生中文閱讀內容。
7. 使用者在 ReaderPage 中進行英文 / 中文 / PDF 對照閱讀。
8. 使用者可進行 highlight、段落編輯、重新生成摘要、下載匯出與刪除。
9. 系統依登入者身份隔離資料，並依使用者帳號取得個人 API Key 進行 AI 呼叫。

本系統不是單純的 PDF 顯示器，而是包含身份驗證、資料管理、背景任務、AI 內容生成、使用者資料隔離與錯誤恢復機制的完整閱讀輔助平台。

---

## Features

- **學校 SSO 登入整合**：使用者進入 `/workspace7/` 後，系統會檢查 PHP session，未登入者導向學校登入流程，登入後由 React 向 FastAPI 交換 JWT token。
- **使用者資料隔離**：在 `AUTH_MODE=school` 模式下，所有論文、段落、highlight、任務與匯出操作都依 current user 進行權限檢查。
- **學生個人 API Key 支援**：系統可依登入者 `user_account` 至 gateway 資料庫查詢對應 API Key，並使用該使用者的 AI 服務額度。
- **PDF 上傳與背景處理**：使用者上傳 PDF 後，API 立即建立 paper record 與 queued task，耗時任務交由 background worker 執行。
- **PDF 文字解析與段落建立**：使用 PyMuPDF / pymupdf4llm 進行 PDF 文字擷取，並建立段落、章節與閱讀元素。
- **AI 全文摘要與段落摘要**：產生 abstract summary、paper overview、main sections、段落摘要與 key points。
- **自動中文翻譯**：初始解析完成後自動建立 `translate_zh` 任務，將論文閱讀內容翻譯為中文。
- **ReaderPage 對照閱讀介面**：支援英文 / 中文切換、PDF On / Off、PDF zoom、左側 AI 摘要與右側 PDF 原文對照閱讀。
- **Highlight 標註功能**：支援文字 highlight 與 PDF highlight，並提供 Yellow / Green / Pink 等顏色。
- **段落編輯與內容更新**：使用者可編輯段落文字、bullet list 或新增段落，系統會重新生成相關摘要、重點與翻譯。
- **Regenerate Overview**：使用者可重新生成全文摘要與章節摘要，系統會建立 background task。
- **Export / Download**：支援匯出 PDF、全文摘要、分段落摘要、中英文內容與 highlights。
- **任務錯誤處理與恢復**：記錄 parse、overview、translation、regenerate 等任務狀態與錯誤訊息，前端顯示處理中、完成或失敗狀態。
- **systemd 多 worker 部署**：API 與多個 worker 皆可透過 systemd 常駐執行。

---

## System Architecture

系統採用前後端分離與背景任務處理架構。

```text
使用者瀏覽器
    │
    │ HTTPS
    ▼
Apache / Reverse Proxy
    ├── React Frontend
    │       └── /workspace7/
    │
    └── FastAPI Backend
            └── /workspace7/api/
                    │
                    ├── PostgreSQL
                    │       ├── users
                    │       ├── papers
                    │       ├── paragraphs
                    │       ├── tasks
                    │       ├── highlights
                    │       └── overview
                    │
                    ├── Background Workers
                    │       ├── paper-reader-worker@1
                    │       └── paper-reader-worker@2
                    │
                    ├── File Storage
                    │       ├── uploads/
                    │       └── logs/
                    │
                    └── External LLM API
                            └── 依 user_account 取得個人 API Key
```

### Main Components

| Component | Technology | Description |
|----------|------------|-------------|
| Frontend | React + Vite + TypeScript | 提供上傳、閱讀、切換語言、PDF 顯示、highlight、編輯、匯出與刪除介面 |
| Backend API | FastAPI | 提供 papers、paragraphs、overview、translation、highlight、export、auth 等 API |
| Database | PostgreSQL | 儲存使用者、論文、段落、摘要、任務狀態與標註資料 |
| Background Worker | Python worker + tasks table | 處理 PDF 解析、摘要生成、中文翻譯與重新生成等耗時任務 |
| Web Server | Apache | 提供 React 靜態檔案與 `/workspace7/api/` reverse proxy |
| Authentication | School SSO + PHP session + JWT | 整合學校登入，並由 FastAPI 發行 JWT 作為 API 存取憑證 |
| LLM Gateway | OpenAI-compatible API Gateway | 依使用者帳號查詢 API Key 後呼叫 AI 模型 |
| Service Manager | systemd | 管理 FastAPI 與多個 worker 常駐服務 |

---

## Authentication and User Flow

```text
使用者進入 /workspace7/
    │
    ▼
React 呼叫 session_user.php
    │
    ├── 未登入：導向學校 SSO login.php
    │
    └── 已登入：取得 user_account / user_name / tenant_id / user_oid
            │
            ▼
React POST /workspace7/api/auth/school-login
            │
            ▼
FastAPI 建立或取得本系統 user
            │
            ▼
回傳 JWT access_token
            │
            ▼
前端後續 API request 自動帶 Authorization: Bearer token
```

### Data Isolation

在 `AUTH_MODE=school` 模式下：

- 未帶 `Authorization` header 的 API request 會被拒絕。
- 使用者只能看到自己 `user_id` 所屬的 papers。
- 使用者無法讀取、修改、刪除其他使用者的論文。
- 不屬於目前使用者的 paper id 會回傳 404 或 403。
- highlight、rename、export、delete、edit、regenerate 等操作都需要通過 ownership check。

---

## AI API Key Flow

最終版系統支援依使用者帳號取得個人 API Key：

```text
current_user / task.user_id
        │
        ▼
paper_reader.users.user_account
        │
        ▼
gateway_v4.api_keys.user_account
        │
        ▼
取得 api_key
        │
        ▼
OpenAI-compatible client
        │
        ▼
LLM summary / translation / regeneration / edit
```

### Supported LLM Tasks

| Task | Trigger | Execution |
|------|---------|-----------|
| parse_overview | PDF 上傳後自動建立 | worker |
| translate_zh | parse_overview 完成後自動建立 | worker |
| regenerate_overview | 使用者按 Regenerate | worker |
| edit paragraph | 使用者編輯段落 | API request |
| insert paragraph | 使用者新增段落 | API request |
| update bullet list | 使用者修改 bullet list | API request |
| section summary update | 相關段落內容更新後 | API / service |

---

## Processing Workflow

```text
使用者上傳 PDF
    │
    ▼
FastAPI 檢查檔案格式、大小與登入身份
    │
    ▼
儲存 PDF 至 uploads/
    │
    ▼
建立 paper record
    │
    ▼
建立 parse_overview task
    │
    ▼
API 回傳 queued，前端顯示 Processing
    │
    ▼
worker 取得 queued task
    │
    ▼
PDF 解析與段落建立
    │
    ▼
LLM 生成全文摘要、章節摘要與段落重點
    │
    ▼
parse_overview completed
    │
    ▼
自動建立 translate_zh task
    │
    ▼
worker 執行中文翻譯
    │
    ▼
translation completed
    │
    ▼
使用者進入 ReaderPage 閱讀與操作
```

---

## Installation

本系統可分成兩種執行方式：

1. **線上展示 / 正式部署模式**：部署於學校 Ubuntu VM，透過 Apache reverse proxy 提供 `/workspace7/` 前端與 `/workspace7/api/` 後端 API，並整合學校 SSO，並整合學校 SSO，可直接用瀏覽器開啟https://air.cgu.edu.tw/workspace7/後執行系統，不需額外下載和安裝。
2. **本地端測試 / 開發模式**：下載原始碼後在本機啟動 PostgreSQL、FastAPI、worker 與 React，使用 `AUTH_MODE=dev` 測試主要功能，不需要學校 SSO。

> 注意：本專案不應提交真實 `.env`、API Key、DB 密碼、JWT secret、上傳檔案、log、venv、node_modules 或 dist 至 GitHub。請使用 `.env.example` 建立自己的本機設定。

---

### 環境需求

| 項目 | 建議版本 / 說明 |
|------|----------------|
| Python | 3.10+ |
| Node.js | 18+ |
| npm | 9+ |
| PostgreSQL | 14+ |
| Git | 用於下載與版本管理 |
| 作業系統 | Windows / Linux / macOS 皆可，本系統正式部署於 Ubuntu VM |
| LLM API | 本地測試可使用 `.env` 中的測試 API key；正式部署可依登入使用者取得個人 API key |

---

### A. 下載專案

```bash
git clone https://github.com/your-account/AI-Paper-Reader.git
cd AI-Paper-Reader
```

如果是從壓縮檔取得原始碼，請先解壓縮後進入專案根目錄。

---

### B. 建立 PostgreSQL 資料庫

本系統使用 PostgreSQL 儲存使用者、論文、段落、摘要、翻譯、任務狀態與標註資料。

請先建立資料庫：

```sql
CREATE DATABASE paper_reader;
```

若使用 Docker，也可以啟動 PostgreSQL container，並在後端 `.env` 中設定對應的 `DATABASE_URL`。

範例：

```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/paper_reader
```

---

### C. 安裝後端套件

進入後端資料夾：

```bash
cd backend
```

建立 Python 虛擬環境：

```bash
python -m venv venv
```

啟用虛擬環境：

Linux / macOS：

```bash
source venv/bin/activate
```

Windows PowerShell：

```powershell
venv\Scripts\activate
```

安裝套件：

```bash
pip install -r requirements.txt
```

---

### D. 設定後端環境變數

複製範例設定檔：

Linux / macOS：

```bash
cp .env.example .env
```

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

本地端測試建議使用：

```env
AUTH_MODE=dev

DATABASE_URL=postgresql://postgres:password@localhost:5432/paper_reader

LLM_API_KEY=<dev-fallback-key>
LLM_BASE_URL=https://air.cgu.edu.tw/cgullmapi/v1
LLM_MODEL=gpt-5.4-mini

SESSION_SECRET_KEY=<your-session-secret>
JWT_SECRET_KEY=<your-jwt-secret>
JWT_EXPIRE_MINUTES=720

LOG_LEVEL=INFO
AUTO_TRANSLATE_AFTER_PARSE=true
ENABLE_DEBUG_EXPORTS=false
ENABLE_ORPHAN_FILE_SCAN=true
AUTO_DELETE_ORPHAN_FILES=false

WORKER_POLL_INTERVAL_SECONDS=2
PDF_UPLOAD_CHUNK_BYTES=1048576
INCOMING_FILE_TTL_HOURS=24
```

設定說明：

- `AUTH_MODE=dev`：本地端測試模式，不需要學校 SSO，系統會使用開發用使用者。
- `AUTH_MODE=school`：正式部署模式，需搭配學校 SSO、PHP session bridge、JWT 驗證與使用者資料隔離。
- `LLM_API_KEY`：本地測試時使用的 LLM API key。
- `LLM_BASE_URL`：LLM Gateway 或 OpenAI-compatible API endpoint。
- `JWT_SECRET_KEY` / `SESSION_SECRET_KEY`：部署時必須改為安全隨機字串，不能使用範例值。
- `PDF_UPLOAD_CHUNK_BYTES`：前後端或後端處理 PDF 上傳時使用的 chunk 大小設定。
- `AUTO_TRANSLATE_AFTER_PARSE=true`：PDF 解析與摘要完成後，自動建立中文翻譯任務。

若正式部署需要依使用者取得個人 API key，需額外設定 Gateway DB 相關參數：

```env
GATEWAY_DB_HOST=<gateway-db-host>
GATEWAY_DB_PORT=3306
GATEWAY_DB_NAME=<gateway-db-name>
GATEWAY_DB_USER=<gateway-db-user>
GATEWAY_DB_PASSWORD=<gateway-db-password>
GATEWAY_API_KEYS_TABLE=api_keys
```

---

### E. 初始化或更新資料庫結構

若專案包含 migration 檔案，可執行：

```bash
psql -U postgres -h localhost -d paper_reader -f migrations/2026_05_school_auth_phase1.sql
```

若沒有 migration 工具，至少需確認 `users` table 具備 school auth 需要的欄位：

```sql
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS user_account VARCHAR;

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS last_login_at TIMESTAMPTZ;

CREATE UNIQUE INDEX IF NOT EXISTS uq_users_user_account
    ON users (user_account);

CREATE INDEX IF NOT EXISTS ix_users_user_account
    ON users (user_account);
```

確認欄位：

```bash
psql -U postgres -h localhost -d paper_reader -c "\d users"
```

---

### F. 啟動後端 API

在 `backend` 資料夾中，且虛擬環境已啟用時執行：

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

啟動後可開啟 FastAPI 文件頁面：

```text
http://127.0.0.1:8000/docs
```

若可正常看到 Swagger UI，代表後端 API 已啟動。

---

### G. 啟動背景 worker

另開一個終端機，進入後端資料夾並啟用虛擬環境：

Linux / macOS：

```bash
cd backend
source venv/bin/activate
python -m app.worker_main
```

Windows PowerShell：

```powershell
cd backend
venv\Scripts\activate
python -m app.worker_main
```

worker 會從資料庫中的 tasks table 取得待處理任務，負責執行 PDF 解析、段落建立、摘要生成、中文翻譯與重新生成摘要等耗時工作。

如果專案版本使用 workers module，也可依實際檔案改用：

```bash
python -m app.workers.paper_worker
```

---

### H. 安裝前端套件

另開一個終端機，進入前端資料夾：

```bash
cd frontend
npm install
```

---

### I. 設定前端環境變數

複製前端設定檔：

Linux / macOS：

```bash
cp .env.example .env
```

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

本地端測試設定：

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

正式部署於學校 VM 並透過 `/workspace7/api` reverse proxy 時，可使用：

```env
VITE_API_BASE_URL=/workspace7/api
```

---

### J. 啟動前端

```bash
npm run dev
```

開啟瀏覽器：

```text
http://localhost:5173/
```

若前端成功載入，且可以看到論文上傳首頁，代表本地端前端啟動成功。

---

### K. Production Build

若要產生可部署到 Apache 的前端靜態檔案：

```bash
cd frontend
npm run build
```

輸出會位於：

```text
frontend/dist/
```

部署到 Apache document root 的範例：

```bash
sudo rsync -av dist/ /var/www/html/
```

正式部署時需確認：

- React `index.html` 為 `/workspace7/` 首頁。
- `/workspace7/api/` 正確 reverse proxy 到 FastAPI。
- PHP SSO bridge 檔案，例如 `auth_callback.php`、`session_user.php`、`logout.php`，放在 Apache 實際對應的資料夾。
- 不要把 `.env`、API key、JWT secret、DB 密碼放進前端或 GitHub。

---

### L. VM 正式部署摘要

正式部署於學校 Ubuntu VM 時，系統使用：

```text
React Frontend: /workspace7/
FastAPI API:    /workspace7/api/
API internal:   http://127.0.0.1:8000/
PostgreSQL:     localhost:5432
Workers:        paper-reader-worker@1, paper-reader-worker@2
```

Apache reverse proxy 概念設定：

```apache
ProxyPass        /workspace7/api/ http://127.0.0.1:8000/
ProxyPassReverse /workspace7/api/ http://127.0.0.1:8000/
```

systemd 服務檢查：

```bash
sudo systemctl status paper-reader-api --no-pager
sudo systemctl status paper-reader-worker@1 --no-pager
sudo systemctl status paper-reader-worker@2 --no-pager
```

重新啟動：

```bash
sudo systemctl restart paper-reader-api
sudo systemctl restart paper-reader-worker@1
sudo systemctl restart paper-reader-worker@2
```

查看 logs：

```bash
sudo journalctl -u paper-reader-api -n 100 --no-pager
sudo journalctl -u paper-reader-worker@1 -n 100 --no-pager
sudo journalctl -u paper-reader-worker@2 -n 100 --no-pager
```


## Usage

### 本地端測試模式

本地端測試模式建議使用：

```env
AUTH_MODE=dev
VITE_API_BASE_URL=http://127.0.0.1:8000
```

啟動順序：

1. 啟動 PostgreSQL。
2. 啟動 FastAPI 後端。
3. 啟動 background worker。
4. 啟動 React 前端。
5. 開啟 `http://localhost:5173/`。

在 dev mode 中，使用者不需要經過學校 SSO，即可測試 PDF 上傳、解析、摘要、翻譯、閱讀、highlight、編輯、重新生成、匯出與刪除等主要功能。

---

### 正式部署模式

正式部署模式使用：

```env
AUTH_MODE=school
VITE_API_BASE_URL=/workspace7/api
```

使用流程如下：

1. 使用者開啟線上系統網址。
2. 若尚未登入，系統導向學校 SSO。
3. 登入成功後，React 呼叫 `session_user.php` 取得 PHP session 中的使用者資訊。
4. React 呼叫 `/workspace7/api/auth/school-login`，由 FastAPI 建立或取得系統使用者，並回傳 JWT。
5. 前端後續 API request 自動帶上 `Authorization: Bearer <token>`。
6. 使用者上傳 PDF。
7. 系統建立 paper record 與 background task。
8. worker 執行 PDF 解析、摘要生成與中文翻譯。
9. 使用者在 ReaderPage 進行英文 / 中文 / PDF 對照閱讀。
10. 使用者可進行 highlight、段落編輯、重新生成摘要、匯出與刪除。

---

### 主要操作

#### 1. Login

線上部署版本開啟：

```text
https://air.cgu.edu.tw/workspace7/
```

若尚未登入，系統會導向學校 SSO。登入成功後，頁面上方會顯示目前登入使用者。

#### 2. Upload PDF

點擊 **Upload PDF**，選擇英文論文 PDF。上傳後系統會建立背景任務，首頁顯示 `Processing` / `Ready` / `Failed` 狀態。

#### 3. Read Paper

點擊 `Ready` 狀態的 paper 進入 ReaderPage，可使用：

- English / 中文切換
- PDF On / Off
- PDF Zoom
- Abstract Summary
- Paper Overview
- Main Sections
- Paragraph Summary
- Key Points

#### 4. Highlight

使用者可選擇顏色並進行：

- Text highlight
- PDF highlight
- Highlight 刪除
- Highlight 重新載入

#### 5. Edit Content

使用者可編輯：

- 段落文字
- bullet list
- 新增段落
- 刪除段落

系統會根據修改後內容重新生成相關摘要、重點與翻譯。

#### 6. Regenerate

點擊 **Regenerate** 重新產生全文摘要與章節摘要。此操作會建立 background task，由 worker 處理。

#### 7. Export

使用者可下載：

- 原始 PDF
- 帶 highlights 的 PDF
- 全文摘要
- 分段落摘要
- 英文內容
- 中文內容
- 中英文對照內容

#### 8. Delete

使用者可刪除論文資料與相關檔案。刪除後首頁列表會更新，該論文無法再被讀取。


## API Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/school-login` | 由前端送入 PHP session user，FastAPI 回傳 JWT |
| GET | `/auth/me` | 取得目前登入使用者 |
| GET | `/papers/` | 取得目前使用者的論文列表 |
| POST | `/upload/pdf` | 上傳 PDF 並建立 parse task |
| GET | `/papers/{paper_id}` | 取得論文閱讀內容 |
| PATCH | `/papers/{paper_id}/title` | 修改論文名稱 |
| POST | `/papers/{paper_id}/translate-zh` | 建立中文翻譯任務 |
| POST | `/papers/{paper_id}/export` | 匯出閱讀資料 |
| DELETE | `/papers/{paper_id}/with-file` | 刪除論文與檔案 |
| PUT | `/paragraphs/{paragraph_id}` | 編輯段落 |
| POST | `/paragraphs/{paragraph_id}/insert-after` | 在段落後新增段落 |
| DELETE | `/paragraphs/{paragraph_id}` | 刪除段落 |
| GET / POST / DELETE | `/highlights/...` | 管理文字與 PDF highlights |
| POST | `/overview/{paper_id}/regenerate` | 建立重新生成摘要任務 |

---

## Project Structure

```text
paper_reader/
├── backend/
│   ├── app/
│   │   ├── main.py                     # FastAPI application entry
│   │   ├── config.py                   # Environment settings
│   │   ├── database.py                 # Database session
│   │   ├── models/
│   │   │   ├── user.py                 # User model
│   │   │   ├── paper.py                # Paper model
│   │   │   ├── paragraph.py            # Paragraph model
│   │   │   └── task.py                 # Background task model
│   │   ├── routers/
│   │   │   ├── auth.py                 # School login / JWT API
│   │   │   ├── upload.py               # PDF upload API
│   │   │   ├── papers.py               # Paper list/detail/export/delete
│   │   │   ├── paragraphs.py           # Paragraph edit/insert/delete
│   │   │   ├── overview.py             # Overview regeneration
│   │   │   ├── highlights.py           # Highlight APIs
│   │   │   └── translation.py          # Translation APIs
│   │   ├── schemas/
│   │   │   ├── auth.py                 # Auth request/response schemas
│   │   │   └── paper.py                # Paper schemas
│   │   ├── services/
│   │   │   ├── auth_service.py         # JWT and user auth logic
│   │   │   ├── api_key_service.py      # Gateway DB API key lookup
│   │   │   ├── llm_client_service.py   # LLM client creation
│   │   │   ├── llm_processor.py        # Paragraph summary/key point generation
│   │   │   ├── translation_service.py  # Chinese translation
│   │   │   ├── overview_generator.py   # Initial overview generation
│   │   │   ├── overview_regenerator.py # Regenerate overview
│   │   │   ├── edit_service.py         # Edit-related regeneration
│   │   │   ├── paper_processing_service.py
│   │   │   └── task_service.py         # Task queue operations
│   │   └── workers/
│   │       └── paper_worker.py         # Background worker process
│   ├── migrations/
│   │   └── 2026_05_school_auth_phase1.sql
│   ├── uploads/                        # Uploaded PDFs and generated files
│   ├── logs/                           # API and worker logs
│   ├── requirements.txt
│   └── .env
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── api/
│   │   │   ├── apiConfig.ts
│   │   │   ├── http.ts
│   │   │   ├── auth.ts
│   │   │   ├── papers.ts
│   │   │   ├── overview.ts
│   │   │   └── highlights.ts
│   │   ├── components/
│   │   │   ├── PdfViewer.tsx
│   │   │   └── ExportModal.tsx
│   │   ├── pages/
│   │   │   ├── HomePage.tsx
│   │   │   └── ReaderPage.tsx
│   │   └── types/
│   │       └── paper.ts
│   ├── package.json
│   ├── vite.config.ts
│   └── dist/
│
└── php/
    ├── auth_check.php
    ├── auth_callback.php
    ├── session_user.php
    └── logout.php
```

---

## Testing

本章節提供完整功能測試流程，建議在提交專題或展示前依序確認。

---

### 1. 基本啟動測試

請分別啟動以下三個服務。

後端 API：

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Windows PowerShell：

```powershell
cd backend
venv\Scripts\activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

背景 worker：

```bash
cd backend
source venv/bin/activate
python -m app.worker_main
```

前端：

```bash
cd frontend
npm run dev
```

確認項目：

- `http://127.0.0.1:8000/docs` 可以開啟。
- `http://localhost:5173/` 可以開啟。
- 前端沒有出現 API 連線錯誤。
- 後端 terminal 沒有 traceback。
- worker terminal 沒有啟動錯誤。

---

### 2. PDF 上傳與背景處理測試

測試步驟：

1. 開啟前端首頁。
2. 點擊 Upload PDF。
3. 選擇一份英文 PDF 論文。
4. 確認首頁出現新論文卡片。
5. 確認狀態由 `Processing` 逐步變為 `Ready`。
6. 若啟用自動翻譯，確認中文翻譯任務也會完成。
7. 若處理失敗，檢查後端與 worker log。

預期結果：

- PDF 可以成功上傳。
- 系統會建立 background task。
- worker 能完成 PDF 解析、摘要生成與中文翻譯。
- 論文狀態最後會變為可閱讀狀態。

---

### 3. ReaderPage 閱讀測試

測試步驟：

1. 點擊 `Ready` 狀態的論文。
2. 確認英文原文、段落摘要與重點正常顯示。
3. 切換中文模式，確認中文翻譯正常顯示。
4. 開啟 PDF 顯示，確認 PDF 可正常載入。
5. 測試 PDF zoom。
6. 測試 PDF On / Off 或文字閱讀模式切換。
7. 點擊 Back，確認可回首頁。

預期結果：

- 英文內容正常顯示。
- 中文內容正常顯示。
- PDF 可與文字摘要對照閱讀。
- 頁面切換不會造成資料遺失。

---

### 4. Highlight 測試

測試步驟：

1. 在文字段落中選取內容並建立 highlight。
2. 在 PDF 中建立 highlight。
3. 切換 highlight 顏色。
4. 重新整理頁面。
5. 確認 highlight 仍存在。
6. 刪除 highlight。
7. 確認 highlight 從畫面與資料中移除。

預期結果：

- 文字 highlight 可建立、保存與刪除。
- PDF highlight 可建立、保存與刪除。
- 重新整理後 highlight 仍能正確載入。

---

### 5. 段落編輯測試

測試步驟：

1. 在 ReaderPage 選擇一個段落。
2. 點擊編輯。
3. 修改少量文字。
4. 儲存。
5. 確認段落內容更新。
6. 確認段落摘要、重點與中文翻譯可重新生成。
7. 重新整理頁面，確認修改後內容仍保留。

預期結果：

- 段落可成功編輯。
- 編輯後相關 AI 生成內容可更新。
- 修改結果會保存至資料庫。
- 不會影響其他 paper 或其他使用者資料。

---

### 6. 全文摘要重新生成測試

測試步驟：

1. 進入 ReaderPage。
2. 點擊 Regenerate Overview。
3. 確認系統建立重新生成任務。
4. 等待 worker 完成處理。
5. 重新整理或查看摘要區域。
6. 確認全文摘要內容更新。

預期結果：

- Regenerate 可以正常建立 background task。
- worker 可以完成全文摘要重新生成。
- 前端可顯示更新後摘要。
- 若任務失敗，前端應顯示錯誤狀態或可重試提示。

---

### 7. 匯出下載測試

測試步驟：

1. 點擊 Download 或 Export。
2. 選擇匯出內容，例如：
   - PDF
   - 全文摘要
   - 分段落摘要
   - 中英文對照
   - 是否包含 highlights
3. 執行下載。
4. 開啟下載檔案，確認內容完整。

預期結果：

- 系統可產生匯出檔。
- 匯出內容包含使用者選擇的項目。
- PDF 與文字摘要可正常下載。
- 若選擇 highlights，輸出應包含標註資訊。

---

### 8. 刪除論文測試

測試步驟：

1. 在首頁或 ReaderPage 點擊 Delete。
2. 確認刪除提示。
3. 執行刪除。
4. 確認首頁列表移除該論文。
5. 重新整理頁面，確認論文不再出現。

預期結果：

- 論文資料可被刪除。
- 相關段落、摘要、highlight 與檔案會一併清理或失效。
- 刪除後無法再透過原本頁面讀取該論文。

---

### 9. 使用者登入與資料隔離測試

正式部署於學校 VM 且使用 `AUTH_MODE=school` 時，需進行以下測試：

1. 開啟線上系統網址。
2. 若尚未登入，系統會導向學校 SSO。
3. 登入後回到 React 前端首頁。
4. 頁面顯示目前登入使用者。
5. 前端向後端取得 JWT token。
6. 後續 API request 會帶上 `Authorization: Bearer <token>`。
7. 使用者只能看到自己上傳的論文。
8. 未帶 token 直接存取 API 時，應回傳未授權錯誤。
9. 帶 A 使用者 token 存取 B 使用者論文時，應回傳 403 或 404。

未帶 token 測試：

```bash
curl -i http://127.0.0.1:8000/auth/me
```

在 `AUTH_MODE=school` 且未帶 token 時，應回傳 401。

前端 Network 應確認：

```text
GET  /workspace7/session_user.php
POST /workspace7/api/auth/school-login
GET  /workspace7/api/papers/
```

且 API request headers 應包含：

```text
Authorization: Bearer <token>
```

預期結果：

- 未登入或未帶 token 無法讀取 API。
- 登入後可正常使用系統。
- 不同使用者之間的論文資料互相隔離。

---

### 10. API Key 測試

正式部署且啟用個人 API key 流程時，使用登入者帳號查 gateway DB：

```sql
SELECT
  user_account,
  user_name,
  role,
  max_rpm,
  max_tokens,
  max_concurrent_requests,
  CONCAT(LEFT(api_key, 8), '...', RIGHT(api_key, 4)) AS masked_api_key
FROM api_keys
WHERE user_account = '<user_account>';
```

測試項目：

1. 登入使用者可查到 API key。
2. 新上傳 PDF 時，worker 可使用該使用者 API key 執行摘要與翻譯。
3. Regenerate overview 可使用該使用者 API key。
4. 段落編輯後重新生成摘要、重點與翻譯可使用該使用者 API key。
5. 若查無 API key，系統應顯示明確錯誤提示，而不是讓任務無限處理中。

預期結果：

- 有 API key 的使用者可正常完成 LLM 任務。
- 無 API key、API key 無效或額度不足時，系統會顯示可理解的錯誤訊息。
- API key 不會傳送到前端。

---

### 11. Worker 與錯誤恢復測試

正式部署時可查看 worker logs：

```bash
sudo journalctl -u paper-reader-worker@1 -n 100 --no-pager
sudo journalctl -u paper-reader-worker@2 -n 100 --no-pager
```

應確認：

- worker 能取得 queued task。
- `parse_overview` 能完成。
- `translate_zh` 能完成。
- `regenerate_overview` 能完成。
- 錯誤任務會正確標記 failed。
- worker 中斷後，任務不會永久卡死。

---

### 12. 正式 VM 部署檢查

正式部署於 Ubuntu VM 時，請確認以下服務：

```bash
sudo systemctl status paper-reader-api --no-pager
sudo systemctl status paper-reader-worker@1 --no-pager
sudo systemctl status paper-reader-worker@2 --no-pager
```

若需要重新啟動：

```bash
sudo systemctl restart paper-reader-api
sudo systemctl restart paper-reader-worker@1
sudo systemctl restart paper-reader-worker@2
```

檢查後端 log：

```bash
sudo journalctl -u paper-reader-api -n 100 --no-pager
```

檢查 worker log：

```bash
sudo journalctl -u paper-reader-worker@1 -n 100 --no-pager
sudo journalctl -u paper-reader-worker@2 -n 100 --no-pager
```

正式部署檢查項目：

- `/workspace7/` 前端可正常開啟。
- `/workspace7/api/` 可正確轉發至 FastAPI。
- Apache reverse proxy 正常。
- FastAPI API service 為 active。
- worker service 為 active。
- PostgreSQL 可正常連線。
- PDF 上傳、解析、摘要、翻譯、閱讀、標註、編輯、匯出與刪除皆可正常運作。
- 使用者登入與資料隔離正常。
- 使用者個人 API key 流程正常。

---

### 13. GitHub 提交前檢查

提交前請確認以下內容沒有進入 Git repository：

```text
.env
.env.production
venv/
node_modules/
dist/
uploads/
logs/
__pycache__/
*.pyc
*.save
*.bak
*.zip
*.tar.gz
```

可使用 PowerShell 檢查：

```powershell
Get-ChildItem -Recurse -Force |
Where-Object {
    $_.FullName -match '\.env|secret|key|password|token|credential|backup|bak|zip|log|uploads|node_modules|venv|dist|\.save'
} |
ForEach-Object { $_.FullName.Replace((Get-Location).Path + "\", "") }
```

敏感字串檢查：

```powershell
Get-ChildItem -Recurse -File -Force |
Where-Object {
    $_.FullName -notmatch '\\node_modules\\|\\venv\\|\\dist\\|\\.git\\|\\uploads\\|\\logs\\'
} |
Select-String -Pattern "sk-","BCDai","GATEWAY_DB_PASSWORD=","JWT_SECRET_KEY=","SESSION_SECRET_KEY=","LLM_API_KEY=","120.126","192.168" |
ForEach-Object {
    "$($_.Path.Replace((Get-Location).Path + '\', '')):$($_.LineNumber): $($_.Line)"
}
```

README 或 `.env.example` 中的 placeholder 可以保留，但真實 API key、DB 密碼、JWT secret 不可提交。


## Error Handling

| Error Case | Expected Handling |
|-----------|-------------------|
| 未登入或未帶 JWT | 回傳 401 |
| 使用者存取他人 paper | 回傳 404 或 403 |
| PDF 檔案不存在 | 顯示找不到原始 PDF |
| PDF 解析失敗 | 任務標記 failed，前端顯示可重新上傳 |
| Overview 生成失敗 | 任務標記 failed，可重新生成 |
| 中文翻譯失敗 | 任務標記 failed，可重新翻譯 |
| 找不到 API Key | 顯示請先申請 API Key |
| API Key 無效或額度不足 | 顯示 AI 服務無法使用 |
| Worker 中斷 | 任務可由後續 worker 恢復或標記失敗 |
| 過久未完成任務 | 依 task timeout / lock 機制處理 |

---

## Implementation Notes

- React 前端不直接使用 PHP session，而是先呼叫 `session_user.php`，再向 FastAPI 交換 JWT。
- JWT token 儲存在前端 localStorage，後續 API 透過 `Authorization: Bearer` 傳送。
- 直接在網址列開 API 不會自動帶 Authorization header，因此在 school mode 下會回傳 missing authorization。
- Background workers 透過 tasks table 取得 queued task，避免 API request 被長時間 LLM 呼叫阻塞。
- `AUTH_MODE=dev` 可作為本機或開發測試模式；正式部署應使用 `AUTH_MODE=school`。
- `LLM_API_KEY` 僅作為 dev fallback；正式 school mode 應依 user_account 查詢 gateway API Key。
- PDF.js worker 需要正確部署至前端靜態資源路徑，避免 PDF 顯示失敗。
- Apache document root 與 `/workspace7/` 對應關係需要確認，避免 React `index.html` 與舊 `index.php` 首頁衝突。
- VM 部署時應避免將 Windows CRLF 格式的 `.env` 直接 source，否則可能造成 boolean parsing 或 DATABASE_URL 錯誤。

---

## Current Deployment Example

```text
https://air.cgu.edu.tw/workspace7/
```

主要服務：

```text
React Frontend: /workspace7/
FastAPI API:    /workspace7/api/
API internal:   http://127.0.0.1:8000/
PostgreSQL:     localhost:5432
Workers:        paper-reader-worker@1, paper-reader-worker@2
```

---

## Limitations and Future Work

- PDF 解析品質仍受原始 PDF 排版影響，複雜雙欄、公式、表格與跨頁段落可能需要持續優化。
- 目前系統以論文閱讀輔助為主，尚未完整加入 AI chat 與知識圖譜功能。
- 多使用者正式上線後，可進一步加入使用量統計、管理者後台與配額提示。
- 可加入更完整的任務管理頁面，讓使用者查看每個 background task 的詳細狀態。
- 可強化 API Key 狀態檢查，在使用者進入系統時提前提示是否尚未申請或額度不足。
- 可加入論文分類、搜尋、標籤與資料夾功能，提升長期使用體驗。
- 可加入段落與 PDF 位置更精準的對齊機制，改善縮放或切換語言後的定位偏差。

---

## Security Notes

- `.env` 不應提交至版本控制。
- 不應在 README、log 或前端程式中暴露真實 API Key、DB 密碼或 JWT secret。
- 正式部署時應使用 HTTPS。
- 學生 API Key 應由後端查詢與使用，不應傳到前端。
- 所有 paper、paragraph、highlight、export、delete API 均應執行 ownership check。
- 測試截圖時應避免露出完整 Authorization token。

---

## Authors

- **劉曉帆** — 長庚大學資訊工程學系  
- Graduation Project: AI-assisted academic paper reading system

---

## License

本專案目前為課程 / 專題用途。若需公開釋出，建議後續補上明確授權條款，例如 MIT License 或學校專題授權說明。
