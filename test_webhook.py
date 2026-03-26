"""
End-to-end test for the n8n Anti-Fraud Webhook.
Simulates what the Discord bot sends to n8n.

Usage:
  python test_webhook.py                     # test with default message
  python test_webhook.py --text "your text"  # test with custom text
  python test_webhook.py --image test.jpg    # test with image
"""

import argparse
import base64
import json
import os
import urllib.request
import urllib.error
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

WEBHOOK_URL = os.getenv("N8N_WEBHOOK_URL", "http://localhost:5678/webhook/anti-fraud")


def test_webhook(text: str, image_path: str = None):
    payload = {
        "text": text,
        "bedrock_api_key": os.getenv("BEDROCK_API_KEY", ""),
        "anti_fraud_api_key": os.getenv("ANTI_FRAUD_API_KEY", ""),
    }

    if image_path and Path(image_path).exists():
        with open(image_path, "rb") as f:
            payload["image_base64"] = base64.b64encode(f.read()).decode("utf-8")
        print(f"Image attached: {image_path}")

    print(f"Webhook URL: {WEBHOOK_URL}")
    print(f"Input text: {text}")
    print("-" * 60)
    print("Sending request...")

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        WEBHOOK_URL,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            print(f"HTTP {resp.status} OK")
            print("=" * 60)
            print("DISPLAY TEXT:")
            print(body.get("display_text", "(empty)"))
            print("=" * 60)
            print("\nFull JSON response:")
            print(json.dumps(body, ensure_ascii=False, indent=2))
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} Error")
        print(e.read().decode("utf-8", errors="replace"))
    except urllib.error.URLError as e:
        print(f"Connection error: {e.reason}")
        print("Make sure n8n is running and the workflow is active.")


TEST_CASES = {
    "url": "我收到一封信叫我去 https://aws.amazon.com 登入，這個網站安全嗎？",
    "phone": "有人用 +886289667000 打電話給我，說是銀行要確認資料，是真的嗎？",
    "mixed": "收到簡訊說我中獎了，要我打 0289667000 或上 https://aws.amazon.com 領獎，感覺很可疑",
    "none": "今天天氣真好，適合出去走走",
}


def main():
    parser = argparse.ArgumentParser(description="Test n8n Anti-Fraud Webhook")
    parser.add_argument("--text", type=str, default=None, help="Custom text to analyze")
    parser.add_argument("--image", type=str, default=None, help="Image file path")
    parser.add_argument(
        "--case",
        type=str,
        choices=list(TEST_CASES.keys()),
        default="mixed",
        help="Predefined test case (default: mixed)",
    )
    parser.add_argument("--url", type=str, default=None, help="Override webhook URL")
    args = parser.parse_args()

    global WEBHOOK_URL
    if args.url:
        WEBHOOK_URL = args.url

    text = args.text if args.text else TEST_CASES[args.case]
    test_webhook(text, args.image)


if __name__ == "__main__":
    main()
