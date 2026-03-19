# 防詐 API 測試腳本 (PowerShell)
# 測試三種 API：URL Check、Number Check、Content Check
param([string]$ImagePath, [string]$Only)

$ErrorActionPreference = "Stop"

$BASE_URL = "https://hljaj2f6gf.execute-api.ap-northeast-1.amazonaws.com/prod"

# 讀取 API Key
$envFile = Join-Path $PSScriptRoot ".env"
$envContent = Get-Content $envFile -Raw
if ($envContent -match "x-api-key=(.+)") {
    $API_KEY = $Matches[1].Trim()
} else {
    Write-Error "找不到 x-api-key，請確認 .env 檔案"
    exit 1
}

Write-Host "API Key: $($API_KEY.Substring(0,8))...$($API_KEY.Substring($API_KEY.Length-4))"
Write-Host ""

# ============================================================
# 測試 1：URL Check（網址網域風險查詢）
# ============================================================
function Test-UrlCheck {
    Write-Host ("=" * 60)
    Write-Host "測試 1：URL Check（網址網域風險查詢）"
    Write-Host ("=" * 60)

    $testUrl = "https://aws.amazon.com"
    Write-Host "查詢網址：$testUrl"

    $headers = @{
        "x-api-key"    = $API_KEY
        "Content-Type" = "application/json"
    }
    $body = @{ url = $testUrl } | ConvertTo-Json

    try {
        $response = Invoke-RestMethod -Method POST `
            -Uri "$BASE_URL/url-check" `
            -Headers $headers `
            -Body ([System.Text.Encoding]::UTF8.GetBytes($body)) `
            -TimeoutSec 30

        Write-Host "HTTP Status: 200"
        Write-Host "  信任分數 (Trust Score): $($response.score)"
        Write-Host "  域名: $($response.domain)"
        Write-Host "  score_status: $($response.score_status)"
        Write-Host "  blacklisted: $($response.blacklisted)"
        Write-Host "  ✅ URL Check 測試成功！"
        return 200
    }
    catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        Write-Host "HTTP Status: $statusCode"
        Write-Host "  ❌ 錯誤: $_"
        return $statusCode
    }
}

# ============================================================
# 測試 2：Number Check（電話號碼查詢）
# ============================================================
function Test-NumberCheck {
    Write-Host ""
    Write-Host ("=" * 60)
    Write-Host "測試 2：Number Check（電話號碼查詢）"
    Write-Host ("=" * 60)

    $country = "TW"
    $number = "+886289667000"
    Write-Host "查詢號碼：$country $number"

    $headers = @{ "x-api-key" = $API_KEY }

    try {
        $response = Invoke-RestMethod -Method GET `
            -Uri "$BASE_URL/number-check/$country/$number" `
            -Headers $headers `
            -TimeoutSec 30

        Write-Host "HTTP Status: 200"
        Write-Host "  名稱: $($response.data.name)"
        Write-Host "  地區: $($response.data.region)"
        Write-Host "  類別: $($response.data.business_categories -join ', ')"
        Write-Host "  垃圾類別: $($response.data.spam_category)"
        Write-Host "  query_id: $($response.query_id)"
        Write-Host "  ✅ Number Check 測試成功！"
        return 200
    }
    catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        Write-Host "HTTP Status: $statusCode"
        Write-Host "  ❌ 錯誤: $_"
        return $statusCode
    }
}

# ============================================================
# 測試 3：Content Check（內容風險截圖查詢）
# ============================================================
function Test-ContentCheck {
    param([string]$ImagePath)

    Write-Host ""
    Write-Host ("=" * 60)
    Write-Host "測試 3：Content Check（內容風險截圖查詢）"
    Write-Host ("=" * 60)

    if (-not $ImagePath) {
        $candidates = @(
            (Join-Path $PSScriptRoot "assets\test_image.jpg"),
            (Join-Path $PSScriptRoot "test_image.jpg")
        )
        foreach ($p in $candidates) {
            if (Test-Path $p) { $ImagePath = $p; break }
        }
    }

    if (-not $ImagePath -or -not (Test-Path $ImagePath)) {
        Write-Host "  ⚠️  找不到測試圖片，跳過 Content Check。"
        Write-Host "  請提供截圖路徑，例如："
        Write-Host '    .\test_apis.ps1 -ImagePath "screenshot.jpg"'
        return $null
    }

    Write-Host "使用圖片：$ImagePath"

    $imageBytes = [System.IO.File]::ReadAllBytes($ImagePath)
    $imageB64 = [System.Convert]::ToBase64String($imageBytes)

    # Step 1：上傳截圖
    Write-Host ""
    Write-Host "  [Step 1] 上傳截圖..."
    $headers = @{
        "x-api-key"       = $API_KEY
        "Content-Type"    = "application/json"
        "Accept-Language" = "zh-TW"
    }
    $body = @{ region = "TW"; image = $imageB64 } | ConvertTo-Json
    $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($body)

    try {
        $uploadResp = Invoke-RestMethod -Method POST `
            -Uri "$BASE_URL/content-check" `
            -Headers $headers `
            -Body $bodyBytes `
            -TimeoutSec 30

        Write-Host "  HTTP Status: 200"
        $jobId = $uploadResp.job_id
        Write-Host "  取得 job_id: $jobId"
    }
    catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        Write-Host "  HTTP Status: $statusCode"
        Write-Host "  ❌ 上傳失敗: $_"
        return $statusCode
    }

    # Step 2：輪詢查詢結果
    Write-Host ""
    Write-Host "  [Step 2] 輪詢查詢結果..."
    $pollHeaders = @{
        "x-api-key"       = $API_KEY
        "Accept-Language" = "zh-TW"
    }

    $statusMap = @{ 0 = "pending"; 1 = "in-progress"; 2 = "failed"; 3 = "success" }

    for ($attempt = 1; $attempt -le 20; $attempt++) {
        Start-Sleep -Seconds 3

        try {
            $result = Invoke-RestMethod -Method GET `
                -Uri "$BASE_URL/content-check/$jobId" `
                -Headers $pollHeaders `
                -TimeoutSec 30

            $jobStatus = $result.status
            $statusLabel = if ($statusMap.ContainsKey($jobStatus)) { $statusMap[$jobStatus] } else { "unknown" }
            Write-Host "    第 $attempt 次查詢 — status: $jobStatus ($statusLabel)"

            if ($jobStatus -eq 3) {
                Write-Host ""
                Write-Host "  分析結果："
                Write-Host "    category: $($result.category)"
                Write-Host "    title: $($result.title)"
                foreach ($line in $result.content) {
                    Write-Host "    - $line"
                }
                if ($result.urls) {
                    Write-Host "    urls: $($result.urls | ConvertTo-Json -Compress)"
                }
                if ($result.numbers) {
                    Write-Host "    numbers: $($result.numbers | ConvertTo-Json -Compress)"
                }
                Write-Host "  ✅ Content Check 測試成功！"
                return 200
            }

            if ($jobStatus -eq 2) {
                Write-Host "  ❌ 處理失敗"
                return 500
            }
        }
        catch {
            Write-Host "    第 $attempt 次查詢 — 錯誤: $_"
        }
    }

    Write-Host "  ⚠️  超過最大輪詢次數，請稍後手動查詢"
    return $null
}

# ============================================================
# 執行測試
# ============================================================
$results = @{}

if (-not $Only -or $Only -eq "url") {
    $results["url_check"] = Test-UrlCheck
    Start-Sleep -Seconds 1
}

if (-not $Only -or $Only -eq "number") {
    $results["number_check"] = Test-NumberCheck
    Start-Sleep -Seconds 1
}

if (-not $Only -or $Only -eq "content") {
    $results["content_check"] = Test-ContentCheck -ImagePath $ImagePath
}

Write-Host ""
Write-Host ("=" * 60)
Write-Host "測試結果總覽"
Write-Host ("=" * 60)
foreach ($name in $results.Keys) {
    $status = $results[$name]
    $icon = if ($status -eq 200) { "✅" } elseif ($null -eq $status) { "⚠️" } else { "❌" }
    Write-Host "  $icon ${name}: HTTP $status"
}
