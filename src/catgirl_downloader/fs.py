from __future__ import annotations

import hashlib
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

CONTENT_TYPE_EXTENSION_MAP = {
    "jpeg": "jpg",
    "pjpeg": "jpg",
    "svg+xml": "svg",
    "x-icon": "ico",
    "vnd.microsoft.icon": "ico",
}


def rating_safety_bucket(rating: str) -> str:
    normalized = rating.strip().lower()
    if normalized == "safe":
        return "sfw"
    if normalized in {"suggestive", "borderline", "explicit"}:
        return "nsfw"
    return "unknown"


def ensure_media_dir(base_dir: Path, category: str, rating: str) -> Path:
    bucket = rating_safety_bucket(rating)
    normalized_category = category.strip().lower() or "unknown"
    normalized_rating = rating.strip().lower() or "unknown"
    target_dir = base_dir / bucket / normalized_category / normalized_rating
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


def extension_from_content_type(content_type: str | None, url: str) -> str:
    if content_type:
        normalized = content_type.split(";", maxsplit=1)[0].strip().lower()
        if normalized.startswith("image/"):
            subtype = normalized.split("/", maxsplit=1)[1]
            mapped = CONTENT_TYPE_EXTENSION_MAP.get(subtype, subtype)
            if "+" in mapped and mapped != "svg+xml":
                mapped = mapped.split("+", maxsplit=1)[0]
            if re.fullmatch(r"[a-z0-9]{1,10}", mapped):
                return f".{mapped}"

    suffix = Path(urlparse(url).path).suffix.lower()
    if re.fullmatch(r"\.[a-z0-9]{1,10}", suffix):
        return suffix
    return ".img"


def build_filename(
    provider: str,
    url: str,
    extension: str,
    now: datetime | None = None,
) -> str:
    current = now or datetime.now(timezone.utc)
    timestamp = current.strftime("%Y%m%dT%H%M%S")
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    normalized_extension = extension if extension.startswith(".") else f".{extension}"
    return f"{provider}_{timestamp}_{digest}{normalized_extension}"


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            delete=False,
            dir=path.parent,
            prefix=path.stem + "_",
            suffix=".tmp",
        ) as tmp_file:
            tmp_file.write(data)
            temp_path = tmp_file.name
        os.replace(temp_path, path)
    except Exception:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
        raise
