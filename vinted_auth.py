from curl_cffi import requests as curl_requests
from urllib.parse import urlencode, urlsplit, parse_qs
from typing import Any, Dict, List
from vinted_bypass import load_cookies, get_vinted_cookies
import random
import asyncio

missing_ids = ['catalog', 'status']

user_agents = [
    'Mozilla/5.0 (iPhone; CPU iPhone OS 15_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
    'Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.74 Mobile Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36',
]

app_version = '22.6.1'


def parse_url(url: str) -> Dict[str, str]:
    parts = urlsplit(url)
    query = parse_qs(parts.query)
    results = {}

    for q, v in query.items():
        is_array = False
        if q.endswith('[]'):
            q = q.rstrip('[]')
            is_array = True
        if q in missing_ids:
            q += '_id'
        if not q.endswith('s') and is_array:
            q += 's'
        results[q] = ','.join(v)
    return results


def format_cookies_for_header(cookies: List[Dict[str, str]]) -> str:
    return "; ".join([f"{c['name']}={c['value']}" for c in cookies])


def search_with_params(url: str, cookies: List[Dict[str, str]], user_agent: str = None) -> Any:
    query = parse_url(url)
    cookie_header = format_cookies_for_header(cookies)
    user_agent = user_agent or random.choice(user_agents)

    headers = {
        'User-Agent': user_agent,
        'x-app-version': app_version,
        'Accept': 'application/json',
        'Cookie': cookie_header
    }

    try:
        response = curl_requests.get(
            url='https://www.vinted.fr/api/v2/catalog/items?' + urlencode(query),
            headers=headers,
            impersonate="chrome110",
            timeout=10
        )
    except Exception as e:
        return {"code": 500, "error": str(e)}

    if response.status_code == 401:
        return {"code": 100, "message": "Unauthorized (401)"}
    elif response.status_code == 403:
        return {"code": 403, "message": "Forbidden (403)"}
    elif response.status_code != 200:
        return {"code": response.status_code, "message": response.text}

    return response.json()


async def fetch_items_with_cookies(cookies: List[Dict[str, str]], search_url: str):
    data = search_with_params(search_url, cookies)
    if isinstance(data, dict) and data.get("code"):
        return data

    items = []
    for item in data.get("items", []):
        # photos : array of photo objects with "url" usually
        photos = []
        for p in item.get("photos", [])[:3]:
            # sometimes photos are nested in different keys; we try common ones
            url = p.get("url") or p.get("full_size") or p.get("medium") or None
            if url:
                photos.append(url)

        # fallback to old 'photo' if present
        if not photos and item.get("photo") and isinstance(item["photo"], dict):
            url = item["photo"].get("url")
            if url:
                photos.append(url)

        # seller info (defensive)
        user = item.get("user") or {}
        positive_rate = user.get("positive_feedback_rate") or user.get("positive_feedback_rate_percent") or 0
        # sometimes API gives 0-100% or 0-1, normalise to 0..1
        if positive_rate > 1:
            positive_rate = float(positive_rate) / 100.0
        # feedback count keys vary
        feedback_count = user.get("feedback_count") or user.get("feedbacks_count") or 0

        created_at = item.get("created_at_ts") or item.get("created_at") or None

        items.append({
            "title": item.get("title", "Sans titre"),
            "url": item.get("url", ""),
            "price": item.get("price", item.get("price_with_shipping") or {}),
            "photos": photos,
            "brand": item.get("brand_title") or item.get("brand", "Inconnue"),
            "size": item.get("size_title") or item.get("size", "Non précisée"),
            "condition": item.get("status") or item.get("item_condition") or "Non indiqué",
            "created_at": created_at,
            "seller_positive_rate": float(positive_rate),
            "seller_feedbacks": int(feedback_count or 0),
            "attributes": item.get("attributes", [])
        })

    return items


async def fetch_items_with_cookies_and_user_agent(cookies: List[Dict[str, str]], search_url: str, user_agent: str):
    data = search_with_params(search_url, cookies, user_agent=user_agent)
    if isinstance(data, dict) and data.get("code"):
        return data

    items = []
    for item in data.get("items", []):
        photos = []
        for p in item.get("photos", [])[:3]:
            url = p.get("url") or p.get("full_size") or p.get("medium") or None
            if url:
                photos.append(url)
        if not photos and item.get("photo") and isinstance(item["photo"], dict):
            url = item["photo"].get("url")
            if url:
                photos.append(url)

        user = item.get("user") or {}
        positive_rate = user.get("positive_feedback_rate") or user.get("positive_feedback_rate_percent") or 0
        if positive_rate > 1:
            positive_rate = float(positive_rate) / 100.0
        feedback_count = user.get("feedback_count") or user.get("feedbacks_count") or 0

        created_at = item.get("created_at_ts") or item.get("created_at") or None

        items.append({
            "title": item.get("title", "Sans titre"),
            "url": item.get("url", ""),
            "price": item.get("price", item.get("price_with_shipping") or {}),
            "photos": photos,
            "brand": item.get("brand_title") or item.get("brand", "Inconnue"),
            "size": item.get("size_title") or item.get("size", "Non précisée"),
            "condition": item.get("status") or item.get("item_condition") or "Non indiqué",
            "created_at": created_at,
            "seller_positive_rate": float(positive_rate),
            "seller_feedbacks": int(feedback_count or 0),
            "attributes": item.get("attributes", [])
        })

    return items


async def get_cookies():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, get_vinted_cookies)


def get_random_user_agent():
    return random.choice(user_agents)