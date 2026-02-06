from __future__ import annotations

import logging
from typing import Any

import httpx

from catgirl_downloader.models import RemoteImage, Theme, UserRating

LOGGER = logging.getLogger(__name__)
API_URL = "https://nekobot.xyz/api/image"
THEME_TYPE: dict[Theme, str] = {
    "catgirl": "neko",
    "neko": "neko",
}


def parse_nekobot_payload(payload: dict[str, Any]) -> str:
    if payload.get("success") is False:
        raise ValueError("nekobot response indicated failure")
    message = payload.get("message")
    if not isinstance(message, str) or not message:
        raise ValueError("nekobot payload missing non-empty 'message' URL")
    return message


class NekobotProvider:
    name = "nekobot"
    supports_rating_filter = False
    supported_themes: tuple[Theme, ...] = ("catgirl", "neko")
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

        image_type = THEME_TYPE[theme]
        params = {"type": image_type}
        candidates: list[RemoteImage] = []

        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            for _ in range(count):
                try:
                    response = await client.get(API_URL, params=params)
                    response.raise_for_status()
                    parsed_url = parse_nekobot_payload(response.json())
                except (httpx.HTTPError, ValueError, TypeError) as exc:
                    LOGGER.warning("nekobot request failed for %s: %s", API_URL, exc)
                    continue
                candidates.append(
                    RemoteImage(
                        provider=self.name,
                        category=theme,
                        url=parsed_url,
                        rating="safe",
                        tags=[theme, "nekobot"],
                    )
                )
        return candidates
