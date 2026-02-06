from __future__ import annotations

import logging
from typing import Any, Mapping

import httpx

from catgirl_downloader.models import RemoteImage, Theme, UserRating

LOGGER = logging.getLogger(__name__)
API_BASE = "https://nekos.best/api/v2"
THEME_ENDPOINT: dict[Theme, str] = {
    "catgirl": "neko",
    "neko": "neko",
    "kitsune": "kitsune",
}


def parse_nekos_best_payload(payload: Mapping[str, Any], *, theme: Theme) -> list[RemoteImage]:
    items = payload.get("results", [])
    if not isinstance(items, list):
        raise ValueError("nekos.best payload must include a list in 'results'")

    candidates: list[RemoteImage] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        url = item.get("url")
        if not isinstance(url, str) or not url:
            continue
        candidates.append(
            RemoteImage(
                provider="nekos_best",
                category=theme,
                url=url,
                rating="safe",
                tags=[theme, "nekos.best"],
            )
        )
    return candidates


class NekosBestProvider:
    name = "nekos_best"
    supports_rating_filter = False
    supported_themes: tuple[Theme, ...] = ("catgirl", "neko", "kitsune")
    supported_ratings: tuple[UserRating, ...] = ("any", "safe")

    async def fetch_candidates(
        self,
        count: int,
        rating: UserRating,
        timeout: float,
        theme: Theme,
    ) -> list[RemoteImage]:
        if count <= 0:
            return []
        if theme not in self.supported_themes or rating not in self.supported_ratings:
            return []

        endpoint = THEME_ENDPOINT[theme]
        url = f"{API_BASE}/{endpoint}"
        params = {"amount": count}

        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                LOGGER.warning("nekos_best request failed for %s: %s", url, exc)
                return []

        if not isinstance(payload, Mapping):
            return []
        return parse_nekos_best_payload(payload, theme=theme)
