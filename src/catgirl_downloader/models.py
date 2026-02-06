from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Rating = Literal["safe", "suggestive", "borderline", "explicit", "unknown"]
UserRating = Literal["any", "safe", "suggestive", "borderline", "explicit"]
Theme = Literal["catgirl", "neko", "kitsune", "femboy"]
DownloadStatus = Literal["ok", "failed", "skipped_duplicate"]

VALID_USER_RATINGS: set[str] = {"any", "safe", "suggestive", "borderline", "explicit"}
KNOWN_RATINGS: set[str] = {"safe", "suggestive", "borderline", "explicit", "unknown"}
VALID_THEMES: set[str] = {"catgirl", "neko", "kitsune", "femboy"}


def normalize_rating(value: str | None) -> Rating:
    if value is None:
        return "unknown"
    lowered = value.strip().lower()
    if lowered in KNOWN_RATINGS:
        return lowered  # type: ignore[return-value]
    return "unknown"


@dataclass(slots=True)
class RemoteImage:
    provider: str
    category: str
    url: str
    rating: Rating = "unknown"
    tags: list[str] = field(default_factory=list)


@dataclass(slots=True)
class DownloadResult:
    url: str
    path: str | None
    provider: str
    status: DownloadStatus
    error: str | None = None


@dataclass(slots=True)
class DownloadSummary:
    requested: int
    downloaded: int
    failed: int
    duplicates: int
    output_dir: str
