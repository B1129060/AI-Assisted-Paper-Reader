# AI 論文閱讀輔助系統

## 1. 專案簡介

AI 論文閱讀輔助系統是一套部署於學校 VM 的 Web-based 論文閱讀平台，主要協助使用者閱讀英文 PDF 論文。系統提供 PDF 上傳、文字解析、段落摘要、重點整理、全文摘要、中文翻譯、PDF 對照閱讀、文字與 PDF 標註、段落編輯、重新生成摘要、匯出與刪除等功能。

本系統的目的不是取代使用者閱讀論文，而是降低閱讀英文論文時的理解成本，讓使用者能更快掌握論文架構、段落重點與翻譯內容，並能保留閱讀過程中的標註與整理結果。

正式部署入口：

```text
https://air.cgu.edu.tw/workspace7/
```

VM 上前端與 PHP 靜態檔案位置：

```text
/var/www/html/
```

後端專案主要位置：

```text
/opt/paper_reader/
```

---

## 2. 系統主要功能

### 2.1 使用者登入與身份驗證

系統整合 School SSO 作為登入身份來源。使用者不需要在本系統另外註冊帳號與密碼，而是透過學校統一登入取得使用者資訊。登入成功後，FastAPI 會建立或取得系統內部 User，並發行 JWT，讓前端後續能以 JWT 呼叫後端 API。

系統會透過 user_id 與 paper ownership 檢查，確保使用者只能查看、修改、匯出與刪除自己的論文資料。

### 2.2 論文上傳與管理

使用者可以在 HomePage 上傳 PDF 論文。系統會檢查檔案格式、大小與使用者限制，建立 paper record，儲存原始 PDF，並建立背景任務進行 PDF 解析與摘要生成。

使用者也可以在首頁查看論文列表，並進行論文改名、下載與刪除。

### 2.3 PDF 解析、摘要與中文翻譯

上傳 PDF 後，系統會建立 `parse_overview` 背景任務，由 worker 解析 PDF 文字、建立 paragraphs、產生段落摘要、key points、全文 overview 與章節摘要。

解析與摘要完成後，系統可接續建立中文翻譯任務，將英文段落翻譯成中文，供使用者在 ReaderPage 中切換閱讀。

### 2.4 ReaderPage 閱讀介面

ReaderPage 是主要閱讀頁面，提供：

- 英文段落、摘要與 key points 顯示
- 中文翻譯切換
- PDF 對照閱讀
- PDF 顯示開關
- PDF zoom 與頁面控制
- references 清單顯示
- 背景任務狀態提示
- highlight、edit、regenerate、export、delete 等操作入口

### 2.5 Highlight 標註

系統支援文字 highlight 與 PDF highlight。使用者可以在解析後的文字區或 PDF 區域建立標註，標註資料會儲存於資料庫，重新整理頁面後仍可載入。

### 2.6 Regenerate 與 Edit 重工作化

使用者可以重新生成 overview，也可以編輯段落、bullet list、新增段落或刪除段落。這些可能需要重新計算摘要、重點與翻譯的操作會建立背景任務，由 worker 處理，避免前端長時間等待。

系統也會檢查同一篇 paper 是否有 active task，避免 edit、regenerate、delete、export 等操作互相衝突。

### 2.7 Export / Download 與 Delete

使用者可以下載原始 PDF，或匯出摘要、翻譯與 highlight 等整理內容。使用者也可以刪除自己上傳的 paper，系統會同步處理相關資料與檔案。


---

## 3. 系統架構

本系統採用前後端分離與背景任務架構，主要分為以下幾層：

| 分層 | 主要組件 | 說明 |
|---|---|---|
| 表示層 | React / Vite / TypeScript | 提供 HomePage、ReaderPage、PDF 對照、標註、編輯與匯出操作介面。 |
| 應用邏輯層 | FastAPI Backend | 處理 API request、JWT 驗證、paper ownership 檢查、資料操作與 task 建立。 |
| 背景任務層 | Python Worker / tasks table | 處理 PDF 解析、摘要、翻譯、Regenerate 與 Edit 類重工作。 |
| 資料層 | PostgreSQL / File Storage | 儲存使用者、論文、段落、摘要、翻譯、標註、task 與上傳檔案。 |
| 外部服務層 | School SSO / Gateway API Key DB / LLM Gateway | 提供登入身份來源、個人 API key 查詢與 AI 摘要翻譯服務。 |

系統主要資料流如下：

```text
使用者瀏覽器
  ↓
Apache / Reverse Proxy
  ↓
React Frontend
  ↓
FastAPI Backend
  ↓
PostgreSQL / File Storage / tasks table
  ↓
Background Worker
  ↓
Gateway API Key DB / LLM Gateway
```

---

## 4. 主要技術

| 類別 | 技術 |
|---|---|
| 前端 | React、Vite、TypeScript |
| 後端 | FastAPI、Pydantic、SQLAlchemy |
| 資料庫 | PostgreSQL |
| 背景任務 | Python Worker、tasks table |
| PDF 解析 | PyMuPDF / pymupdf4llm |
| AI 服務 | OpenAI-compatible API / LLM Gateway |
| 登入驗證 | School SSO、PHP session bridge、JWT |
| Web Server | Apache |
| 服務管理 | systemd service / systemd timer |
| 部署環境 | Ubuntu VM |

---

## 5. 作業文件內容說明

本次作業文件依照物件導向軟體設計課程要求，整理 AI 論文閱讀輔助系統的詞彙表、使用案例圖、使用案例描述、活動圖與類別圖。其中目前文件已完成以下五個部分：

### 5.1 詞彙表

詞彙表整理系統中會出現的重要名詞，例如：

- School SSO
- JWT
- Paper
- Paragraph
- Task
- Worker
- ReaderPage
- Highlight
- References
- Storage Cleanup

每個詞彙皆包含定義與備註，目的是讓讀者先理解本系統的領域概念與資料名稱，避免後續使用案例與活動圖中的名詞不清楚。

### 5.2 使用案例圖

使用案例圖依照系統作業流程分成七類：

1. 使用者登入與權限驗證
2. PDF 上傳與論文建立
3. 背景解析、摘要與中文翻譯
4. ReaderPage 閱讀與任務狀態回饋
5. Highlight 標註
6. Regenerate 與 Edit 重工作化
7. Export / Download 與 Delete

每張使用案例圖都以 Actor、系統邊界、使用案例橢圓、連結線、include 與 extend 關係表示系統功能。使用案例圖主要描述系統「能提供什麼功能」，而不是描述程式如何實作。

### 5.3 使用案例描述

每個使用案例圖對應一組使用案例描述，且每組包含：

- 一個正常情節
- 兩個例外情節

格式採用「Actor 動作 / 系統回應」表格，並使用：

- `TUCBW` 表示 The Use Case Begin With，也就是使用案例開始於某一步。
- `TUCEW` 表示 The Use Case End With，也就是使用案例結束於某一步。

這部分的重點是描述使用者與系統互動時的執行路徑，包括正常成功流程與可能發生的錯誤流程。

### 5.4 活動圖

活動圖依照七個使用案例分類繪製，描述各功能的流程控制、判斷節點與結束狀態。活動圖比使用案例描述更接近流程表達，適合用來呈現：

- 哪些步驟依序執行
- 哪些地方會進入判斷
- 正常流程與例外流程如何分支
- 流程最後如何結束

文件中已包含七張活動圖，對應前述七個功能類別。

### 5.5 類別圖

類別圖描述整個資訊系統的主要類別與關聯，包含：

- School SSO
- User
- Paper
- Paragraph
- PaperOverview
- PaperReference
- Highlight
- Task
- LLM / API key 相關類別

類別圖主要用來呈現系統資料結構與類別之間的關係，例如 User 擁有多篇 Paper，Paper 具有多個 Paragraph、Highlight、Task 與 Reference 等。

---

## 6. 使用方式簡述

1. 使用者開啟系統網址：

```text
https://air.cgu.edu.tw/workspace7/
```

2. 透過 School SSO 完成登入。
3. 在 HomePage 上傳 PDF 論文。
4. 等待系統背景解析、摘要與翻譯。
5. 點選論文進入 ReaderPage。
6. 在 ReaderPage 中閱讀英文、中文翻譯、摘要與 PDF。
7. 視需要進行 highlight、edit、regenerate、export 或 delete。
8. 使用完成後按 Logout，系統會導向登出提示頁。

---

## 7. 注意事項

- AI 摘要與翻譯結果僅作為閱讀輔助，使用者仍應以原始論文為最終依據。
- 掃描圖片型 PDF、複雜多欄排版、公式與表格圖片可能影響解析品質。
- LLM 任務依賴外部 LLM Gateway 與個人 API key，若 API key 無效、額度不足或 Gateway timeout，相關任務可能失敗。