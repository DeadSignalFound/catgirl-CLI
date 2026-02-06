from __future__ import annotations

import logging
import random
from typing import Any

import httpx

from catgirl_downloader.models import RemoteImage, Theme, UserRating, normalize_rating

LOGGER = logging.getLogger(__name__)
API_BASE = "https://api.waifu.pics"
THEME_ENDPOINT: dict[Theme, str] = {
    "catgirl": "neko",
    "neko": "neko",
    "femboy": "trap",
}


def parse_waifu_pics_payload(payload: dict[str, Any]) -> str:
    url = payload.get("url")
    if not isinstance(url, str) or not url:
        raise ValueError("waifu.pics payload missing non-empty 'url' field")
    return url


class WaifuPicsProvider:
    name = "waifu_pics"
    supports_rating_filter = True
    supported_themes: tuple[Theme, ...] = ("catgirl", "neko", "femboy")
    supported_ratings: tuple[UserRating, ...] = ("any", "safe", "explicit")

    async def fetch_candidates(
        self,
        count: int,
        rating: UserRating,
        timeout: float,
        theme: Theme,
        randomize: bool = False,
    ) -> list[RemoteImage]:
        if count <= 0:
            return []
        if theme not in self.supported_themes or rating not in self.supported_ratings:
            return []

        endpoint_theme = THEME_ENDPOINT[theme]
        candidates: list[RemoteImage] = []
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            for _ in range(count):
                if theme == "femboy":
                    if rating == "safe":
                        return []
                    mode = "nsfw"
                    mapped_rating = "explicit"
                    endpoint = f"{API_BASE}/{mode}/{endpoint_theme}"
                else:
                    mode, mapped_rating = self._resolve_mode(rating)
                    endpoint = f"{API_BASE}/{mode}/{endpoint_theme}"
                try:
                    response = await client.get(endpoint)
                    response.raise_for_status()
                    url = parse_waifu_pics_payload(response.json())
                except (httpx.HTTPError, ValueError, TypeError) as exc:
                    LOGGER.warning("waifu_pics request failed for %s: %s", endpoint, exc)
                    continue

                candidates.append(
                    RemoteImage(
                        provider=self.name,
                        category=theme,
                        url=url,
                        rating=normalize_rating(mapped_rating),
                        tags=[endpoint_theme, theme, "waifu.pics"],
                    )
                )
        return candidates

    @staticmethod
    def _resolve_mode(rating: UserRating) -> tuple[str, str]:
        if rating == "safe":
            return "sfw", "safe"
        if rating == "explicit":
            return "nsfw", "explicit"
        if rating == "any":
            mode = random.choice(("sfw", "nsfw"))
            return (mode, "safe" if mode == "sfw" else "explicit")
        return "sfw", "safe"
