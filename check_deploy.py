import time
import httpx

API_URL = "https://api-toolkit-yb1l.onrender.com"

def check_health():
    print("Checking health...")
    for _ in range(15): # Wait up to 30 seconds for deploy
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
    print("Testing /tools/og-image endpoint...")
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv("API_KEY", "your-development-api-key")
    headers = {"X-API-Key": api_key}
    
    payload = {
        "title": "ApyHub OG Image Test",
        "subtitle": "Testing production deployment",
        "bg_color": "#4f46e5",
        "text_color": "#ffffff"
    }
    
    try:
        r = httpx.post(f"{API_URL}/tools/og-image", json=payload, headers=headers, timeout=20.0)
        if r.status_code == 200 and r.headers.get("content-type") == "image/png":
            print("Success! OG Image generated on production.")
            with open("prod_test_og.png", "wb") as f:
                f.write(r.content)
            print("Saved to prod_test_og.png")
        else:
            print(f"Failed to generate OG image. Status details: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"Error during request: {e}")

def check_html_to_md():
    print("Testing /tools/html-to-markdown endpoint...")
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    api_key = os.getenv("API_KEY", "your-development-api-key")
    headers = {"X-API-Key": api_key}
    
    payload = {
        "url": "https://zapier.com/blog/how-to-use-chatgpt/"
    }
    
    try:
        r = httpx.post(f"{API_URL}/tools/html-to-markdown", json=payload, headers=headers, timeout=30.0)
        if r.status_code == 200:
            data = r.json()
            if data.get("readability_success"):
                print("Success! HTML converted to Markdown on production.")
                print(f"Title: {data.get('title')}")
                print(f"Character Count: {data.get('character_count')}")
            else:
                print("Failed: API returned 200 but readability_success was false.")
        else:
            print(f"Failed to generate Markdown. Status details: {r.status_code} - {r.text}")
    except Exception as e:
        print(f"Error during request: {e}")

if __name__ == "__main__":
    if check_health():
        time.sleep(10)
        check_og_image()
        check_html_to_md()
