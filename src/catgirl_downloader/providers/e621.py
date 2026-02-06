from __future__ import annotations

import logging
import os
import random
from typing import Any, Mapping

import httpx

from catgirl_downloader.models import RemoteImage, Theme, UserRating, normalize_rating

LOGGER = logging.getLogger(__name__)
API_URL = "https://e621.net/posts.json"
DEFAULT_USER_AGENT = "catgirl-downloader/0.1 (set E621_USER_AGENT in .env)"
MAX_LIMIT = 320
RANDOM_PAGE_MAX = 100
RANDOM_POOL_MULTIPLIER = 8
THEME_TAGS: dict[Theme, str] = {
    "femboy": "femboy",
}
RATING_TAGS: dict[UserRating, str | None] = {
    "any": None,
    "safe": "rating:s",
    "suggestive": "rating:q",
    "borderline": "rating:q",
    "explicit": "rating:e",
}
E621_RATING_MAP = {
    "s": "safe",
    "q": "suggestive",
    "e": "explicit",
}


def parse_e621_payload(payload: Mapping[str, Any], *, theme: Theme) -> list[RemoteImage]:
    posts = payload.get("posts", [])
    if not isinstance(posts, list):
        raise ValueError("e621 payload must include a list in 'posts'")

    candidates: list[RemoteImage] = []
    for post in posts:
        if not isinstance(post, Mapping):
            continue

        file_info = post.get("file")
        if not isinstance(file_info, Mapping):
            continue
        url = file_info.get("url")
        if not isinstance(url, str) or not url:
            continue

        tags_map = post.get("tags")
        tags: list[str] = [theme, "e621"]
        if isinstance(tags_map, Mapping):
            for values in tags_map.values():
                if not isinstance(values, list):
                    continue
                tags.extend([value for value in values if isinstance(value, str)])
                if len(tags) > 32:
                    break

        raw_rating = post.get("rating")
        rating = normalize_rating(E621_RATING_MAP.get(raw_rating, None) if isinstance(raw_rating, str) else None)

        candidates.append(
            RemoteImage(
                provider="e621",
                category=theme,
                url=url,
                rating=rating,
                tags=tags[:32],
            )
        )
    return candidates


class E621Provider:
    name = "e621"
    supports_rating_filter = True
    supported_themes: tuple[Theme, ...] = ("femboy",)
    supported_ratings: tuple[UserRating, ...] = ("any", "safe", "suggestive", "borderline", "explicit")

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
        if theme not in self.supported_themes:
            return []

        tags = [THEME_TAGS[theme]]
        rating_tag = RATING_TAGS[rating]
        if rating_tag:
            tags.append(rating_tag)

        headers = {"User-Agent": os.getenv("E621_USER_AGENT", DEFAULT_USER_AGENT)}
        request_limit = count
        if randomize:
            request_limit = min(MAX_LIMIT, max(count * RANDOM_POOL_MULTIPLIER, count))

        params: dict[str, str | int] = {
            "tags": " ".join(tags),
            "limit": request_limit,
        }
        if randomize:
            params["page"] = random.randint(1, RANDOM_PAGE_MAX)

        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            async def request_payload(request_params: Mapping[str, str | int]) -> Any | None:
                try:
                    response = await client.get(API_URL, params=request_params, headers=headers)
                    response.raise_for_status()
                    return response.json()
                except (httpx.HTTPError, ValueError, TypeError) as exc:
                    LOGGER.warning("e621 request failed: %s", exc)
                    return None

            payload = await request_payload(params)
            if payload is None:
                return []

            if randomize and "page" in params:
                parsed = parse_e621_payload(payload, theme=theme) if isinstance(payload, Mapping) else []
                if not parsed:
                    fallback_params = dict(params)
                    fallback_params.pop("page", None)
                    payload = await request_payload(fallback_params)

        if payload is None:
            return []
        if not isinstance(payload, Mapping):
            return []

        candidates = parse_e621_payload(payload, theme=theme)
        if randomize and candidates:
            random.shuffle(candidates)
        return candidates[:count]
