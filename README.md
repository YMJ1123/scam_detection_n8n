# Scam Detection n8n + Discord Bot

AWS Hackathon 2026 詐騙識別防範 — 使用 n8n workflow + Groq LLM Router + Discord Bot，自動分析訊息中的網址、電話號碼及截圖是否為詐騙。

## Architecture

```
Discord User
  │  message / image
  ▼
Discord Bot (discord_bot.py)
  │  POST /anti-fraud
  ▼
n8n Webhook
  │
  ├─ Groq LLM Router ── 從文字中抽取 URLs、電話號碼
  │
  ├─ URL Check API ──── 網址信譽分數 (ScamAdviser)
  ├─ Number Check API ─ 電話號碼查詢 (Whoscall)
  ├─ Content Check API ─ 截圖風險分析 (AI)
  │
  └─ Merge + Format ── 合併結果回傳
  │
  ▼
Discord Bot ── Embed 回覆（顏色依風險等級區分）
```

## Features

- **LLM Router**: Groq LLM 自動從使用者訊息中抽取網址和電話號碼
- **URL Check**: 查詢網址的信任分數（0-100）、是否列入黑名單
- **Number Check**: 查詢電話號碼的持有者、業務類別、是否為垃圾電話
- **Content Check**: 上傳截圖進行 AI 詐騙分析
- **Discord 整合**: 支援 `!check`、`@bot`、`/check` 三種觸發方式

## Project Structure

```
.
├── .env.sample              # 環境變數範例
├── .gitignore
├── docker-compose.yml       # n8n + Discord Bot 容器編排
├── Dockerfile               # Discord Bot 容器
├── discord_bot.py           # Discord Bot 程式碼
├── requirements.txt         # Python 依賴
├── n8n_workflow.json         # n8n workflow（可直接匯入）
├── test_apis.py             # 三種 API 測試腳本（Python）
├── test_apis.ps1            # 三種 API 測試腳本（PowerShell）
├── test_webhook.py          # n8n Webhook 端對端測試
├── api_doc/                 # API 詳細文件
│   ├── url_check.md
│   ├── number_check.md
│   └── content_check.md
├── assets/
│   └── test_image.jpg       # Content Check 測試用圖片
└── postman/                 # Postman Collection
    ├── url_check.postman_collection.json
    ├── number_check.postman_collection.json
    └── content_check.postman_collection.json
```

## Quick Start

### 1. Clone & Configure

```bash
git clone https://github.com/YMJ1123/scam_detection_n8n.git
cd scam_detection_n8n
cp .env.sample .env
```

編輯 `.env`，填入你的 API keys：

```
ANTI_FRAUD_API_KEY=your-anti-fraud-api-key
GROQ_API_KEY=gsk_your-groq-api-key
DISCORD_BOT_TOKEN=your-discord-bot-token
```

### 2. Start Services (Docker Compose)

```bash
docker-compose up -d
```

這會啟動：
- **n8n** on `http://localhost:5678`
- **Discord Bot** 自動連線 Discord

### 3. Import n8n Workflow

1. 開啟 `http://localhost:5678`
2. Create new workflow → **Import from File** → 選 `n8n_workflow.json`
3. 確認 Groq LLM Router 節點的 Authorization header 有正確讀取 `$env.GROQ_API_KEY`
4. **啟動 workflow**（右上角 Active 開關打開）

### 4. Test

不需要 Discord 也可以測試 workflow：

```bash
pip install python-dotenv
python test_webhook.py --case mixed
```

預設測試案例：

| Case | 內容 |
|------|------|
| `url` | 查詢 `https://aws.amazon.com` 是否安全 |
| `phone` | 查詢 `+886289667000` 是否為詐騙 |
| `mixed` | 同時包含電話和網址 |
| `none` | 無風險內容 |

### 5. Discord Bot Usage

在 Discord 頻道中：

```
!check 這個網站 https://example.com 安全嗎？
!check 有人用 0912345678 打給我說是銀行
@bot 幫我查一下這個號碼 +886289667000
/check text:幫我分析這封簡訊
```

也可以附上截圖，Bot 會自動上傳進行分析。

## n8n Workflow Nodes

| Node | 說明 |
|------|------|
| Webhook Trigger | 接收 POST `/anti-fraud`，body 包含 `text` 和可選的 `image_base64` |
| Prepare Groq Request | 組裝 LLM prompt |
| Groq LLM Router | 呼叫 Groq API，抽取 URLs、電話號碼 |
| Parse LLM Output | 解析 LLM 回傳的 JSON |
| Call APIs and Merge | 依據抽取結果呼叫對應的防詐 API，合併結果 |
| Respond to Webhook | 回傳 JSON 給 Discord Bot |

## Anti-Fraud API Reference

Base URL: `https://hljaj2f6gf.execute-api.ap-northeast-1.amazonaws.com/prod`

| API | Method | Endpoint | Rate Limit |
|-----|--------|----------|------------|
| URL Check | POST | `/url-check` | 1 RPS, Burst 2 |
| URL Check (Cache) | POST | `/url-check-cache` | 1 RPS, Burst 2 |
| Number Check | GET | `/number-check/{country}/{number}` | 1 RPS, Burst 2 |
| Content Check (Upload) | POST | `/content-check` | 20 RPM, Burst 3 |
| Content Check (Poll) | GET | `/content-check/{job_id}` | 20 RPM, Burst 3 |

詳細文件見 [`api_doc/`](api_doc/) 目錄。

## Standalone API Testing

如果只想測試三種 API（不需要 n8n / Discord）：

```bash
# Python
python test_apis.py
python test_apis.py --only url
python test_apis.py --only number
python test_apis.py --only content --image "assets/test_image.jpg"

# PowerShell
.\test_apis.ps1
.\test_apis.ps1 -Only url
```

## Deployment Notes

- n8n 和 Discord Bot 可以分開部署在不同主機上
- 如果 n8n 在遠端 Linux 主機，將 `.env` 中的 `N8N_WEBHOOK_URL` 改為遠端主機的 IP/域名
- Discord Bot 只需要能連到 n8n 的 Webhook URL 即可
- 防詐 API 將於 **2026-04-01** 下架

## License

This project was created for AWS Hackathon 2026.
