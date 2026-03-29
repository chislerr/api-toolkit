import time
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://api-toolkit-yb1l.onrender.com"
API_KEY = os.getenv("API_KEY", "dev-api-key-change-me")
HEADERS = {"X-API-Key": API_KEY}


def check_health():
    print("Checking health...")
    for _ in range(15):
        try:
            r = httpx.get(f"{API_URL}/health", timeout=10.0)
            if r.status_code == 200:
                print("Server is healthy!")
                return True
        except httpx.RequestError:
            pass
        print("Waiting for server to restart...")
        time.sleep(2)
    return False


def check_og_image():
    print("\nTesting /tools/og-image ...")
    payload = {
        "title": "ApyHub OG Image Test",
        "subtitle": "Testing production deployment",
        "bg_color": "#4f46e5",
        "text_color": "#ffffff",
    }
    try:
        r = httpx.post(
            f"{API_URL}/tools/og-image", json=payload, headers=HEADERS, timeout=20.0
        )
        if r.status_code == 200 and r.headers.get("content-type") == "image/png":
            print("  OK — OG Image generated")
        else:
            print(f"  FAIL — {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"  ERROR — {e}")


def check_html_to_md():
    print("\nTesting /tools/html-to-markdown ...")
    payload = {"url": "https://zapier.com/blog/how-to-use-chatgpt/"}
    try:
        r = httpx.post(
            f"{API_URL}/tools/html-to-markdown",
            json=payload,
            headers=HEADERS,
            timeout=30.0,
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("readability_success"):
                print(f"  OK — Title: {data.get('title')}, Chars: {data.get('character_count')}")
            else:
                print("  FAIL — readability_success was false")
        else:
            print(f"  FAIL — {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"  ERROR — {e}")


def check_extract_article():
    print("\nTesting /extract/article ...")
    payload = {"url": "https://zapier.com/blog/how-to-use-chatgpt/"}
    try:
        r = httpx.post(
            f"{API_URL}/extract/article",
            json=payload,
            headers=HEADERS,
            timeout=30.0,
        )
        if r.status_code == 200:
            data = r.json()
            print(f"  OK — Title: {data.get('title', '?')}, Words: {data.get('word_count', 0)}")
        else:
            print(f"  FAIL — {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"  ERROR — {e}")


def check_intel_techstack():
    print("\nTesting /intel/techstack ...")
    payload = {"url": "https://github.com"}
    try:
        r = httpx.post(
            f"{API_URL}/intel/techstack",
            json=payload,
            headers=HEADERS,
            timeout=30.0,
        )
        if r.status_code == 200:
            data = r.json()
            print(f"  OK — Tech stack: {data.get('tech_stack', [])}")
        else:
            print(f"  FAIL — {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"  ERROR — {e}")


def check_pdf_absent():
    print("\nVerifying /pdf endpoints are absent (light deployment) ...")
    try:
        r = httpx.post(
            f"{API_URL}/pdf/from-url",
            json={"url": "https://example.com"},
            headers=HEADERS,
            timeout=10.0,
        )
        if r.status_code == 404:
            print("  OK — PDF endpoint correctly returns 404")
        else:
            print(f"  NOTE — PDF endpoint returned {r.status_code} (Playwright may be installed)")
    except Exception as e:
        print(f"  ERROR — {e}")


if __name__ == "__main__":
    if check_health():
        time.sleep(2)
        check_og_image()
        check_html_to_md()
        check_extract_article()
        check_intel_techstack()
        check_pdf_absent()
        print("\n--- All checks done ---")
    else:
        print("Server did not become healthy in time.")
