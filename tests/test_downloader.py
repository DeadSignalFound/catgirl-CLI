import re
from pathlib import Path

import httpx
import pytest

from catgirl_downloader.downloader import dedupe_candidates, download_candidates, run_download
from catgirl_downloader.models import RemoteImage


def _image(provider: str, category: str, url: str) -> RemoteImage:
    return RemoteImage(provider=provider, category=category, url=url, rating="safe", tags=["catgirl"])


def test_dedupe_candidates_skips_duplicate_urls() -> None:
    first = _image("nekosapi", "catgirl", "https://img.example/dup.webp")
    second = _image("waifu_pics", "neko", "https://img.example/dup.webp")
    unique, duplicates = dedupe_candidates([first, second])

    assert len(unique) == 1
    assert len(duplicates) == 1
    assert duplicates[0].status == "skipped_duplicate"


@pytest.mark.anyio
async def test_retry_on_server_error_then_success(httpx_mock, tmp_path: Path) -> None:
    image = _image("nekosapi", "catgirl", "https://img.example/retry.png")
    httpx_mock.add_response(url=image.url, status_code=500)
    httpx_mock.add_response(
        url=image.url,
        status_code=200,
        headers={"content-type": "image/png"},
        content=b"catgirl",
    )

    results = await download_candidates(
        candidates=[image],
        out_dir=tmp_path,
        concurrency=1,
        retries=3,
        timeout=10.0,
    )

    assert len(results) == 1
    assert results[0].status == "ok"
    assert results[0].path is not None
    assert Path(results[0].path).exists()


@pytest.mark.anyio
async def test_timeout_marks_failure(httpx_mock, tmp_path: Path) -> None:
    image = _image("nekosapi", "catgirl", "https://img.example/timeout.png")
    request = httpx.Request("GET", image.url)
    httpx_mock.add_exception(httpx.ReadTimeout("timed out", request=request))

    results = await download_candidates(
        candidates=[image],
        out_dir=tmp_path,
        concurrency=1,
        retries=0,
        timeout=2.0,
    )

    assert len(results) == 1
    assert results[0].status == "failed"
    assert results[0].error is not None
    assert "timed out" in results[0].error.lower()


@pytest.mark.anyio
async def test_non_image_content_is_rejected(httpx_mock, tmp_path: Path) -> None:
    image = _image("nekosapi", "catgirl", "https://img.example/not-image")
    httpx_mock.add_response(
        url=image.url,
        status_code=200,
        headers={"content-type": "text/html"},
        content=b"<html>not an image</html>",
    )

    results = await download_candidates(
        candidates=[image],
        out_dir=tmp_path,
        concurrency=1,
        retries=2,
        timeout=5.0,
    )

    assert len(results) == 1
    assert results[0].status == "failed"
    assert results[0].error is not None
    assert "non-image" in results[0].error.lower()


@pytest.mark.anyio
async def test_auto_provider_fallback_fills_deficit(httpx_mock, tmp_path: Path) -> None:
    httpx_mock.add_response(
        url=re.compile(r"https://api\.nekosapi\.com/v4/images/random.*"),
        json={
            "value": [
                {
                    "url": "https://img.example/nekos-only.webp",
                    "rating": "safe",
                    "tags": ["catgirl"],
                }
            ]
        },
    )
    httpx_mock.add_response(
        url="https://api.waifu.pics/sfw/neko",
        json={"url": "https://img.example/waifu-fallback.jpg"},
    )
    httpx_mock.add_response(
        url="https://img.example/nekos-only.webp",
        headers={"content-type": "image/webp"},
        content=b"nekos",
    )
    httpx_mock.add_response(
        url="https://img.example/waifu-fallback.jpg",
        headers={"content-type": "image/jpeg"},
        content=b"waifu",
    )

    results, summary, warnings = await run_download(
        count=2,
        provider_name="auto",
        out_dir=tmp_path,
        concurrency=2,
        retries=1,
        timeout=10.0,
        rating="safe",
        theme="catgirl",
    )

    ok_results = [result for result in results if result.status == "ok"]
    providers = {result.provider for result in ok_results}
    assert summary.requested == 2
    assert summary.downloaded == 2
    assert summary.failed == 0
    assert warnings == []
    assert providers == {"nekosapi", "waifu_pics"}


@pytest.mark.anyio
async def test_auto_provider_for_kitsune_uses_multiple_apis(httpx_mock, tmp_path: Path) -> None:
    httpx_mock.add_response(
        url=re.compile(r"https://nekos\.best/api/v2/kitsune\?amount=2"),
        json={"results": [{"url": "https://img.example/kitsune-best.png"}]},
    )
    httpx_mock.add_response(
        url="https://nekos.life/api/v2/img/fox_girl",
        json={"url": "https://img.example/kitsune-life.png"},
    )
    httpx_mock.add_response(
        url="https://img.example/kitsune-best.png",
        headers={"content-type": "image/png"},
        content=b"best",
    )
    httpx_mock.add_response(
        url="https://img.example/kitsune-life.png",
        headers={"content-type": "image/png"},
        content=b"life",
    )

    results, summary, warnings = await run_download(
        count=2,
        provider_name="auto",
        out_dir=tmp_path,
        concurrency=2,
        retries=1,
        timeout=10.0,
        rating="safe",
        theme="kitsune",
    )

    ok_results = [result for result in results if result.status == "ok"]
    providers = {result.provider for result in ok_results}
    assert summary.requested == 2
    assert summary.downloaded == 2
    assert warnings == []
    assert providers == {"nekos_best", "nekos_life"}
