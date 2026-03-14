import asyncio
from services.html_to_md import extract_markdown_from_url

async def test():
    # Let's test with a typically cluttered news or blog article
    url = "https://zapier.com/blog/how-to-use-chatgpt/"
    print(f"Testing HTML to Markdown extraction against: {url}")
    
    result = await extract_markdown_from_url(url)
    
    if "error" in result:
        print("Test failed with error:", result["error"])
        return
        
    print(f"\n--- SUCCESS ---")
    print(f"Title: {result.get('title')}")
    print(f"Character Count: {result.get('character_count')}")
    print(f"Markdown snippet preview:\n")
    
    md_text = result.get('markdown', '')
    print(md_text[:500] + "\n\n... [TRUNCATED] ... \n\n" + md_text[-300:])
    
if __name__ == "__main__":
    asyncio.run(test())
