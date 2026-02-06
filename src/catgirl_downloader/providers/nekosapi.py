from __future__ import annotations

import logging
from typing import Any, Mapping

import httpx

from catgirl_downloader.models import RemoteImage, Theme, UserRating, normalize_rating

LOGGER = logging.getLogger(__name__)
API_URL = "https://api.nekosapi.com/v4/images/random"
THEME_TAGS: dict[Theme, str] = {
    "catgirl": "catgirl",
}


def parse_nekosapi_payload(payload: Mapping[str, Any], *, theme: Theme = "catgirl") -> list[RemoteImage]:
    raw_items = payload.get("value", [])
    if not isinstance(raw_items, list):
        raise ValueError("nekosapi payload must include a list in 'value'")

    candidates: list[RemoteImage] = []
    for item in raw_items:
        if not isinstance(item, Mapping):
            continue
        url = item.get("url")
        if not isinstance(url, str) or not url:
            continue

        tags_field = item.get("tags", [])
        tags = [tag for tag in tags_field if isinstance(tag, str)] if isinstance(tags_field, list) else []

        candidates.append(
            RemoteImage(
                provider="nekosapi",
                category=theme,
                url=url,
                rating=normalize_rating(item.get("rating") if isinstance(item.get("rating"), str) else None),
                tags=tags,
            )
        )
    return candidates


class NekosApiProvider:
    name = "nekosapi"
    supports_rating_filter = True
    supported_themes: tuple[Theme, ...] = ("catgirl",)
    supported_ratings: tuple[UserRating, ...] = ("any", "safe", "suggestive", "borderline", "explicit")

    async def fetch_candidates(
        self,
        count: int,
        rating: UserRating,
        timeout: float,
        theme: Theme,
    ) -> list[RemoteImage]:
        if count <= 0:
            return []
        if theme not in self.supported_themes:
            return []

        params: dict[str, str | int] = {"tags": THEME_TAGS[theme], "limit": count}
        if rating != "any":
            params["rating"] = rating

        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            try:
                response = await client.get(API_URL, params=params)
                response.raise_for_status()
                payload = response.json()
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                LOGGER.warning("nekosapi request failed: %s", exc)
                return []

        if not isinstance(payload, Mapping):
            LOGGER.warning("nekosapi returned unexpected payload type: %s", type(payload).__name__)
            return []
        return parse_nekosapi_payload(payload, theme=theme)
