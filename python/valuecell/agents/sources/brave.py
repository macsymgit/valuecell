"""Brave Search API client used by the agents' web_search tools."""

import asyncio
import os
import re

import httpx
from loguru import logger

BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"
BRAVE_RESULT_COUNT = 10
BRAVE_TIMEOUT_S = 15.0
BRAVE_MAX_RETRIES = 3
BRAVE_RETRY_DELAY_S = 1.1
_HTML_TAG = re.compile(r"<[^>]+>")


async def brave_search(query: str) -> str:
    """Return the top Brave web results as Markdown (title, URL, snippet).

    Results are returned raw rather than summarized: the calling agent's LLM
    does the summarizing and can cite the exact URLs.
    """
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": os.environ["BRAVE_API_KEY"],
    }
    params = {"q": query, "count": BRAVE_RESULT_COUNT}
    async with httpx.AsyncClient(timeout=BRAVE_TIMEOUT_S) as client:
        for attempt in range(BRAVE_MAX_RETRIES + 1):
            resp = await client.get(BRAVE_SEARCH_URL, headers=headers, params=params)
            # Free plan allows 1 req/s; agents often fire searches back to back.
            if resp.status_code != 429 or attempt == BRAVE_MAX_RETRIES:
                break
            await asyncio.sleep(BRAVE_RETRY_DELAY_S * (attempt + 1))
        resp.raise_for_status()
        results = resp.json().get("web", {}).get("results", [])

    logger.info("Brave search returned {n} results", n=len(results))
    if not results:
        return f"No web results found for: {query}"
    return "\n\n".join(_format_result(i, r) for i, r in enumerate(results, 1))


def _format_result(index: int, result: dict) -> str:
    """Format one Brave result; snippets carry <strong> highlight tags."""
    lines = [f"{index}. {result.get('title', '')}", f"   URL: {result.get('url', '')}"]
    if result.get("age"):
        lines.append(f"   Published: {result['age']}")
    snippets = [result.get("description", ""), *result.get("extra_snippets", [])]
    text = " ".join(_HTML_TAG.sub("", s) for s in snippets if s)
    if text:
        lines.append(f"   {text}")
    return "\n".join(lines)
