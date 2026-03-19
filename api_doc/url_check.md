# 網址網域風險查詢

## 概覽

透過此 API 查詢指定 URL 的網址網域風險分析結果，由 [ScamAdviser](https://www.scamadviser.com/) 提供分析資料。

本文件涵蓋兩個端點：

| 端點 | 說明 | 上線狀態 |
|------|------|----------|
| `POST /url-check` | 完整分析（最長 25 秒），每次都觸發深度掃描 | ✅ 已上線 |
| `POST /url-check-cache` | 快取查詢（建議先呼叫），命中時毫秒級回應 | ✅ 已上線 |

**建議使用流程**：先呼叫 `/url-check-cache` 查快取；若回 404（無快取）或 503（資料過舊）再呼叫 `/url-check`。

Rate Limit：每組 API Key 限 **1 RPS**，短暫 Burst 上限 **2**（兩個端點各自獨立計數）。

> API Key 取得方式與除錯說明請參考 [README](../README.md)。

---

## 請求格式

**Method**：`POST`

**URL**：`https://hljaj2f6gf.execute-api.ap-northeast-1.amazonaws.com/prod/url-check`

**Headers**：

| Header | 必填 | 說明 |
|--------|------|------|
| `x-api-key` | ✅ | 各隊專屬 API Key |
| `Content-Type` | ✅ | 固定填 `application/json` |

**Request Body**（JSON）：

| 欄位 | 型別 | 必填 | 說明 |
|------|------|------|------|
| `url` | string | ✅ | 欲查詢的 URL |

**範例**：

```bash
curl -X POST "https://hljaj2f6gf.execute-api.ap-northeast-1.amazonaws.com/prod/url-check" \
  -H "x-api-key: <YOUR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://aws.amazon.com"}'
```

---

## 回應格式

**成功（200）**：

Response body 為 ScamAdviser 原始 JSON 回應，完整欄位說明請參考：

> 📖 [ScamAdviser API 文件 — GET /v3/url/get](https://api.scamadviser.cloud/docs/#/Url%2FGet/get_Url_Get_single_3_0_0)

---

## ScamAdviser 查詢行為說明

收到 200 以外的狀態碼並非代表 Adapter 出錯，部分狀態碼是 ScamAdviser 的正常業務回應。ScamAdviser 查詢流程如下：

```
呼叫 /url-check
        │
        ├─ 域名在封鎖清單？ → 是 → 404（停止，不做任何處理）
        │
        ├─ 24 小時內掃描過？ → 是 → 200（立即回傳快取資料）
        │
        ├─ DNS 是否存在？ → 否 ─┬─ 有舊資料 → 503（舊資料，>30天）
        │                       └─ 無資料   → 404（未找到）
        │
        ├─ 網路是否可達？ → 否 ─┬─ 有舊資料 → 503（舊資料，>30天）
        │                       └─ 無資料   → 404（未找到）
        │
        └─ 觸發資料收集，輪詢快取（最長 25 秒）→ 200（回傳最新資料）
```

**503 的處理建議**：代表 ScamAdviser 有此域名的舊資料（超過 30 天），此次呼叫已觸發背景重新掃描。Response body 中仍含有舊的分析資料可供參考，如需最新資料可稍後再呼叫一次。

---

## 錯誤碼

| HTTP Status | 原因 | Response Body |
|-------------|------|---------------|
| `400` | Request body 缺少 `url` 欄位，或 body 不是合法 JSON，或 `url` 格式不合法（需以 http:// 或 https:// 開頭） | `{"message": "..."}` |
| `403` | `x-api-key` 未提供或無效 | API Gateway 標準錯誤訊息 |
| `404` | 域名在 ScamAdviser 封鎖清單、無 DNS 記錄且無歷史資料、或網路不可達且無歷史資料 | ScamAdviser 原始回應 |
| `429` | 超過 Rate Limit（1 RPS / Burst 2） | `{"message": "Too Many Requests"}` |
| `502` | 上游 ScamAdviser 回傳非預期錯誤 | `{"message": "Upstream error"}` |
| `503` | ScamAdviser 有舊資料（> 30 天），可重新呼叫觸發更新掃描 | ScamAdviser 原始回應 |
| `504` | 上游 ScamAdviser 回應逾時（> 20 秒） | `{"message": "Upstream timeout"}` |

---

## Rate Limit 說明

兩個端點（`/url-check`、`/url-check-cache`）各自獨立計數：

- 每組 API Key 獨立計數，**不同隊伍互不影響**
- 穩定速率：**1 RPS**（每秒 1 次）
- 短暫 Burst：最多連續 **2 次**
- 超過後回 `429`，約 **1 秒**後 token 補充，可重試

---

## 快取查詢端點：`POST /url-check-cache`

| 項目 | 值 |
|------|-----|
| Endpoint | `POST /url-check-cache` |
| 上線狀態 | ✅ 已上線 |
| Rate Limit | 每組 API Key 限 **1 RPS**，短暫 Burst 上限 **2**（與 `/url-check` 相同） |

### 建議使用流程

ScamAdviser 建議先查快取，只有在快取無資料時才呼叫完整分析：

```
1. POST /url-check-cache
   ├─ 200 → 快取命中（資料 < 30 天），直接使用
   ├─ 404 → 無快取資料 → 改呼叫 POST /url-check
   └─ 503 → 快取資料 > 30 天 → 可呼叫 POST /url-check 觸發重新掃描
```

此流程可避免每次都觸發完整分析（最長 25 秒），節省時間與成本。

### 請求格式

與 `/url-check` 完全相同，Request Body 填 `{"url": "..."}`。

**範例**：

```bash
curl -X POST "https://hljaj2f6gf.execute-api.ap-northeast-1.amazonaws.com/prod/url-check-cache" \
  -H "x-api-key: <YOUR_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://aws.amazon.com"}'
```

### 回應狀態碼

| HTTP Status | 意義 | 建議處理 |
|-------------|------|----------|
| `200` | 快取命中，資料 < 30 天 | 直接使用 Response body |
| `400` | 缺少 `url` 欄位或格式不合法 | 修正 request |
| `403` | `x-api-key` 未提供或無效 | 確認 API Key |
| `404` | 無快取資料 | 改呼叫 `/url-check` |
| `429` | 超過 Rate Limit | 等待後重試 |
| `502` | 上游非預期錯誤 | 回報問題 |
| `503` | 快取資料 > 30 天（舊資料） | 可呼叫 `/url-check` 觸發重新掃描；Response body 含舊資料可供參考 |
| `504` | 上游逾時 | 稍後重試 |

---

## 黑客松結束後的替代方案

本 Adapter 將於 **2026-04-01** 下架。如果後續仍需使用 ScamAdviser API，可透過 RapidAPI 自行申請帳號直接呼叫：

> 🔗 [ScamAdviser API on RapidAPI](https://rapidapi.com/scamadviser1/api/scamadviser1/)

RapidAPI 版本提供免費 tier，適合低頻使用的情境。

