from __future__ import annotations

import logging
from typing import Any

import httpx

from catgirl_downloader.models import RemoteImage, Theme, UserRating

LOGGER = logging.getLogger(__name__)
API_BASE = "https://nekos.life/api/v2/img"
THEME_ENDPOINT: dict[Theme, str] = {
    "catgirl": "neko",
    "neko": "neko",
    "kitsune": "fox_girl",
}


def parse_nekos_life_payload(payload: dict[str, Any]) -> str:
    url = payload.get("url")
    if not isinstance(url, str) or not url:
        raise ValueError("nekos.life payload missing non-empty 'url' field")
    return url


class NekosLifeProvider:
    name = "nekos_life"
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
        candidates: list[RemoteImage] = []

        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            for _ in range(count):
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    parsed_url = parse_nekos_life_payload(response.json())
                except (httpx.HTTPError, ValueError, TypeError) as exc:
                    LOGGER.warning("nekos_life request failed for %s: %s", url, exc)
                    continue
                candidates.append(
                    RemoteImage(
                        provider=self.name,
                        category=theme,
                        url=parsed_url,
                        rating="safe",
                        tags=[theme, "nekos.life"],
                    )
                )
        return candidates
