from __future__ import annotations

from typing import Protocol

from catgirl_downloader.models import RemoteImage, Theme, UserRating


class Provider(Protocol):
    name: str
    supports_rating_filter: bool
    supported_themes: tuple[Theme, ...]
    supported_ratings: tuple[UserRating, ...]

    async def fetch_candidates(
        self,
        count: int,
        rating: UserRating,
        timeout: float,
        theme: Theme,
    ) -> list[RemoteImage]:
        ...
