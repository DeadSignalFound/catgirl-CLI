from __future__ import annotations

import logging
import os
import random
from typing import Any, Mapping

import httpx

from catgirl_downloader.models import RemoteImage, Theme, UserRating, normalize_rating

LOGGER = logging.getLogger(__name__)
API_URL = "https://api.rule34.xxx/index.php"
MAX_LIMIT = 100
RANDOM_PID_MAX = 200
RANDOM_POOL_MULTIPLIER = 8
THEME_TAGS: dict[Theme, str] = {
    "femboy": "femboy",
}
RATING_TAGS: dict[UserRating, str | None] = {
    "any": None,
    "safe": "rating:safe",
    "suggestive": "rating:questionable",
    "borderline": "rating:questionable",
    "explicit": "rating:explicit",
}
R34_RATING_MAP = {
    "s": "safe",
    "q": "suggestive",
    "e": "explicit",
    "safe": "safe",
    "questionable": "suggestive",
    "explicit": "explicit",
}


def parse_rule34_payload(payload: Any, *, theme: Theme) -> list[RemoteImage]:
    posts: list[Mapping[str, Any]]
    if isinstance(payload, list):
        posts = [item for item in payload if isinstance(item, Mapping)]
    elif isinstance(payload, Mapping):
        raw_posts = payload.get("post")
        if isinstance(raw_posts, list):
            posts = [item for item in raw_posts if isinstance(item, Mapping)]
        elif isinstance(raw_posts, Mapping):
            posts = [raw_posts]
        else:
            posts = []
    else:
        posts = []

    candidates: list[RemoteImage] = []
    for post in posts:
        raw_url = post.get("file_url") or post.get("sample_url") or post.get("preview_url")
        if not isinstance(raw_url, str) or not raw_url:
            continue
        url = f"https:{raw_url}" if raw_url.startswith("//") else raw_url

        raw_rating = post.get("rating")
        mapped_rating = R34_RATING_MAP.get(raw_rating, None) if isinstance(raw_rating, str) else None
        rating = normalize_rating(mapped_rating)

        tag_field = post.get("tags")
        tags = [theme, "rule34"]
        if isinstance(tag_field, str):
            tags.extend([tag for tag in tag_field.split() if tag])

        candidates.append(
            RemoteImage(
                provider="rule34",
                category=theme,
                url=url,
                rating=rating,
                tags=tags[:32],
            )
        )
    return candidates


class Rule34Provider:
    name = "rule34"
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

        user_id = os.getenv("RULE34_USER_ID", "").strip()
        api_key = os.getenv("RULE34_API_KEY", "").strip()
        if not user_id or not api_key:
            LOGGER.warning("rule34 requires RULE34_USER_ID and RULE34_API_KEY in environment")
            return []

        tags = [THEME_TAGS[theme]]
        rating_tag = RATING_TAGS[rating]
        if rating_tag:
            tags.append(rating_tag)

        request_limit = count
        if randomize:
            request_limit = min(MAX_LIMIT, max(count * RANDOM_POOL_MULTIPLIER, count))

        params: dict[str, str | int] = {
            "page": "dapi",
            "s": "post",
            "q": "index",
            "json": "1",
            "limit": request_limit,
            "tags": " ".join(tags),
            "user_id": user_id,
            "api_key": api_key,
        }
        if randomize:
            params["pid"] = random.randint(0, RANDOM_PID_MAX)

        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            async def request_payload(request_params: Mapping[str, str | int]) -> Any | None:
                try:
                    response = await client.get(API_URL, params=request_params)
                    response.raise_for_status()
                    return response.json()
                except (httpx.HTTPError, ValueError, TypeError) as exc:
                    LOGGER.warning("rule34 request failed: %s", exc)
                    return None

            payload = await request_payload(params)
            if payload is None:
                return []

            if randomize and "pid" in params:
                parsed = parse_rule34_payload(payload, theme=theme)
                if not parsed:
                    fallback_params = dict(params)
                    fallback_params.pop("pid", None)
                    payload = await request_payload(fallback_params)

        if payload is None:
            return []

        candidates = parse_rule34_payload(payload, theme=theme)
        if randomize and candidates:
            random.shuffle(candidates)
        return candidates[:count]
