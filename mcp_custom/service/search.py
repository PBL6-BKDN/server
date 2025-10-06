import asyncio
import os
from pprint import pprint
import httpx
from typing import Optional


from readability import Document as ReadabilityDocument
from bs4 import BeautifulSoup


from config import SERP_API_KEY


async def search_information_from_google(query: str, max_results: int = 3):
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            "https://serpapi.com/search.json",
            params={
                "engine": "google",
                "q": query,
                "api_key": SERP_API_KEY,
                "num": max_results,
                "hl": "vi",
                "location": "Vietnam",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        pprint(data.get("organic_results"))
        for item in (data.get("organic_results") or [])[:max_results]:
            results.append(
                {
                    "title": item.get("title"),
                    "link": item.get("link"),
                    "snippet": item.get("snippet"),
                    "date": item.get("date", "Không xác định được ngày"),
                }
            )
        return {"engine": "serpapi_google", "query": query, "results": results}


async def fetch_page_text_extracted(url: str, max_chars: int = 4000) -> str:
    """Tải HTML và trích văn bản chính (readability + BeautifulSoup).

    - Ưu tiên dùng readability để lấy phần nội dung chính
    - Dùng BeautifulSoup loại bỏ script/style và trích text
    - Giới hạn độ dài theo max_chars
    """
    async with httpx.AsyncClient(timeout=20, headers={"User-Agent": "curl/8.4.0"}) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        html: str = resp.text

    content_html: str = html

    try:
        doc = ReadabilityDocument(html)
        content_html = doc.summary() or html
    except Exception:
        content_html = html

    soup = BeautifulSoup(content_html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    # Trích text và chuẩn hóa xuống dòng
    raw_text = soup.get_text(separator="\n")
    lines = [ln.strip() for ln in raw_text.splitlines()]
    lines = [ln for ln in lines if ln]
    text = "\n".join(lines)

    # Cắt độ dài nếu cần
    if len(text) > max_chars:
        text = text[:max_chars]
    return text


if __name__ == "__main__":
    pprint(asyncio.run(search_information_from_google("Làm sao để tán gái", 5)))
    pprint(asyncio.run(fetch_page_text_extracted(
        "https://chinhem.com/chinh-phuc/cach-cua-gai/")))
