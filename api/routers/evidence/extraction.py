"""
Extraction Module - Diffbot article extraction endpoints
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import httpx

from ...config import DIFFBOT_TOKEN

router = APIRouter()

@router.post("/extract")
async def evidence_extract(request: Dict[str, Any]):
    """Extract article text via Diffbot.
    Input: { url: str }
    Output: { title, author, date, site_name, text, html, tags[] }
    """
    try:
        if not isinstance(request, dict):
            raise HTTPException(status_code=400, detail="invalid payload")
        if not DIFFBOT_TOKEN:
            raise HTTPException(status_code=501, detail="Diffbot not configured")
        url_in = (request.get("url") or "").strip()
        if not url_in:
            raise HTTPException(status_code=400, detail="url required")
        api_url = "https://api.diffbot.com/v3/article"
        params = {
            "token": DIFFBOT_TOKEN,
            "url": url_in,
            "fields": "title,author,date,siteName,tags,images,html,text",
        }
        with httpx.Client(timeout=30) as client:
            r = client.get(api_url, params=params)
            r.raise_for_status()
            js = r.json()
        obj = (js.get("objects") or [None])[0]
        if not obj:
            raise HTTPException(status_code=404, detail="no article found")
        return {
            "title": obj.get("title"),
            "author": obj.get("author"),
            "date": obj.get("date"),
            "site_name": obj.get("siteName"),
            "text": obj.get("text"),
            "html": obj.get("html"),
            "tags": obj.get("tags"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"extract failed: {e}")



