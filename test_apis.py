"""
防詐 API 測試腳本
測試三種 API：URL Check、Number Check、Content Check
"""

import os
import json
import time
import base64
import urllib.request
import urllib.error
from pathlib import Path

BASE_URL = "https://hljaj2f6gf.execute-api.ap-northeast-1.amazonaws.com/prod"

def load_api_key():
    env_path = Path(__file__).parent / ".env"
    with open(env_path, "r") as f:
        for line in f:
            if line.startswith("x-api-key="):
                return line.strip().split("=", 1)[1]
    raise RuntimeError("找不到 x-api-key，請確認 .env 檔案")


def api_request(method, path, headers=None, body=None):
    """發送 HTTP 請求，回傳 (status_code, response_body)"""
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, method=method)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_text = e.read().decode("utf-8", errors="replace")
        try:
            return e.code, json.loads(body_text)
        except json.JSONDecodeError:
            return e.code, {"raw": body_text}


def test_url_check(api_key):
    """測試 1：網址網域風險查詢"""
    print("=" * 60)
    print("測試 1：URL Check（網址網域風險查詢）")
    print("=" * 60)

    test_url = "https://aws.amazon.com"
    print(f"查詢網址：{test_url}")

    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
    }

    status, data = api_request("POST", "/url-check", headers, {"url": test_url})
    print(f"HTTP Status: {status}")

    if status == 200:
        score = data.get("score", "N/A")
        domain = data.get("domain", "N/A")
        print(f"  信任分數 (Trust Score): {score}")
        print(f"  域名: {domain}")
        print(f"  score_status: {data.get('score_status', 'N/A')}")
        print(f"  blacklisted: {data.get('blacklisted', 'N/A')}")
        print("  ✅ URL Check 測試成功！")
    else:
        print(f"  ❌ 錯誤回應: {json.dumps(data, ensure_ascii=False, indent=2)}")

    return status


def test_number_check(api_key):
    """測試 2：電話號碼查詢"""
    print("\n" + "=" * 60)
    print("測試 2：Number Check（電話號碼查詢）")
    print("=" * 60)

    country = "TW"
    number = "+886289667000"
    print(f"查詢號碼：{country} {number}")

    headers = {"x-api-key": api_key}

    status, data = api_request("GET", f"/number-check/{country}/{number}", headers)
    print(f"HTTP Status: {status}")

    if status == 200:
        info = data.get("data", {})
        print(f"  名稱: {info.get('name', 'N/A')}")
        print(f"  地區: {info.get('region', 'N/A')}")
        print(f"  類別: {info.get('business_categories', 'N/A')}")
        print(f"  垃圾類別: {info.get('spam_category', 'N/A')}")
        print(f"  query_id: {data.get('query_id', 'N/A')}")
        print("  ✅ Number Check 測試成功！")
    else:
        print(f"  ❌ 錯誤回應: {json.dumps(data, ensure_ascii=False, indent=2)}")

    return status


def test_content_check(api_key, image_path=None):
    """測試 3：內容風險（截圖）查詢"""
    print("\n" + "=" * 60)
    print("測試 3：Content Check（內容風險截圖查詢）")
    print("=" * 60)

    if image_path is None:
        candidates = [
            Path(__file__).parent / "assets" / "test_image.jpg",
            Path(__file__).parent / "test_image.jpg",
        ]
        for p in candidates:
            if p.exists():
                image_path = str(p)
                break

    if image_path is None or not Path(image_path).exists():
        print("  ⚠️  找不到測試圖片，跳過 Content Check。")
        print("  請提供截圖路徑，例如：")
        print('    python test_apis.py --image "screenshot.jpg"')
        return None

    print(f"使用圖片：{image_path}")

    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("utf-8")

    # Step 1：上傳截圖
    print("\n  [Step 1] 上傳截圖...")
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json",
        "Accept-Language": "zh-TW",
    }
    body = {"region": "TW", "image": image_b64}

    status, data = api_request("POST", "/content-check", headers, body)
    print(f"  HTTP Status: {status}")

    if status != 200:
        print(f"  ❌ 上傳失敗: {json.dumps(data, ensure_ascii=False, indent=2)}")
        return status

    job_id = data.get("job_id")
    print(f"  取得 job_id: {job_id}")

    # Step 2：輪詢查詢結果
    print("\n  [Step 2] 輪詢查詢結果...")
    poll_headers = {
        "x-api-key": api_key,
        "Accept-Language": "zh-TW",
    }

    max_attempts = 20
    for attempt in range(1, max_attempts + 1):
        time.sleep(3)
        status, result = api_request("GET", f"/content-check/{job_id}", poll_headers)
        job_status = result.get("status", -1)
        status_map = {0: "pending", 1: "in-progress", 2: "failed", 3: "success"}
        print(f"    第 {attempt} 次查詢 — status: {job_status} ({status_map.get(job_status, 'unknown')})")

        if job_status == 3:
            print(f"\n  分析結果：")
            print(f"    category: {result.get('category', 'N/A')}")
            print(f"    title: {result.get('title', 'N/A')}")
            contents = result.get("content", [])
            for line in contents:
                print(f"    - {line}")
            urls = result.get("urls", [])
            if urls:
                print(f"    urls: {json.dumps(urls, ensure_ascii=False)}")
            numbers = result.get("numbers", [])
            if numbers:
                print(f"    numbers: {json.dumps(numbers, ensure_ascii=False)}")
            print("  ✅ Content Check 測試成功！")
            return 200

        if job_status == 2:
            print("  ❌ 處理失敗")
            return status

    print("  ⚠️  超過最大輪詢次數，請稍後手動查詢")
    return None


def main():
    import argparse
    parser = argparse.ArgumentParser(description="防詐 API 測試腳本")
    parser.add_argument("--image", type=str, default=None, help="Content Check 測試用的截圖路徑")
    parser.add_argument("--only", type=str, choices=["url", "number", "content"], help="只測試指定 API")
    args = parser.parse_args()

    api_key = load_api_key()
    print(f"API Key: {api_key[:8]}...{api_key[-4:]}")
    print()

    results = {}

    if args.only is None or args.only == "url":
        results["url_check"] = test_url_check(api_key)
        time.sleep(1)

    if args.only is None or args.only == "number":
        results["number_check"] = test_number_check(api_key)
        time.sleep(1)

    if args.only is None or args.only == "content":
        results["content_check"] = test_content_check(api_key, args.image)

    print("\n" + "=" * 60)
    print("測試結果總覽")
    print("=" * 60)
    for name, status in results.items():
        icon = "✅" if status == 200 else ("⚠️" if status is None else "❌")
        print(f"  {icon} {name}: HTTP {status}")


if __name__ == "__main__":
    main()
