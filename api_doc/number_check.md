# 電話號碼查詢 API

## 概覽

| 項目 | 值 |
|------|-----|
| Endpoint | `GET /number-check/{country}/{number}` |
| 上線狀態 | ✅ 已上線 |
| Rate Limit | 每組 API Key 限 **1 RPS**，短暫 Burst 上限 **2** |

> API Key 取得方式與除錯說明請參考 [README](../README.md)。

---

## 請求格式

**Method**：`GET`

**URL**：`https://hljaj2f6gf.execute-api.ap-northeast-1.amazonaws.com/prod/number-check/{country}/{number}`

**Path Parameters**：

| 參數 | 必填 | 說明 | 範例 |
|------|------|------|------|
| `country` | ✅ | ISO 3166-1 alpha-2 國碼 | `TW` |
| `number` | ✅ | 欲查詢的電話號碼（建議使用 E.164 格式） | `+886289667000` |

**Headers**：

| Header | 必填 | 說明 |
|--------|------|------|
| `x-api-key` | ✅ | 各隊專屬 API Key |

**範例**：

```bash
curl "https://hljaj2f6gf.execute-api.ap-northeast-1.amazonaws.com/prod/number-check/TW/+886289667000" \
  -H "x-api-key: <YOUR_API_KEY>"
```

---

## 回應格式

**成功（200）**：

```json
{
  "data": {
    "business_categories": ["health"],
    "name": "財團法人亞東紀念醫院",
    "region": "TW",
    "spam_category": null
  },
  "query_id": "a820d601-522d-48af-b792-fe9e5cdb140a"
}
```

---

## 錯誤碼

| HTTP Status | 原因 | Response Body |
|-------------|------|---------------|
| `403` | `x-api-key` 未提供或無效 | API Gateway 標準錯誤訊息 |
| `429` | 超過 Rate Limit（1 RPS / Burst 2） | `{"message": "Too Many Requests"}` |
| `504` | 上游回應逾時 | `{"message": "Upstream timeout"}` |

---

## Rate Limit 說明

- 每組 API Key 獨立計數，**不同隊伍互不影響**
- 穩定速率：**1 RPS**（每秒 1 次）
- 短暫 Burst：最多連續 **2 次**
- 超過後回 `429`，約 **1 秒**後 token 補充，可重試

---

## 黑客松結束後的替代方案

本 Adapter 將於 **2026-04-01** 下架。如果後續仍需使用電話號碼查詢功能，可透過底下 Email 聯繫：

> **聯絡 Email**：growth@gogolook.com
