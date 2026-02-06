import re
from datetime import datetime, timezone

from catgirl_downloader.fs import build_filename, extension_from_content_type


def test_extension_from_content_type_takes_priority() -> None:
    extension = extension_from_content_type("image/png; charset=binary", "https://example.com/file.bin")
    assert extension == ".png"


def test_extension_from_url_fallback() -> None:
    extension = extension_from_content_type(None, "https://example.com/image.webp?token=123")
    assert extension == ".webp"


def test_extension_defaults_to_img() -> None:
    extension = extension_from_content_type("text/plain", "https://example.com/download")
    assert extension == ".img"


def test_build_filename_format() -> None:
    now = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    file_name = build_filename("nekosapi", "https://example.com/image.png", ".png", now=now)
    assert re.fullmatch(r"nekosapi_20260102T030405_[0-9a-f]{10}\.png", file_name)
