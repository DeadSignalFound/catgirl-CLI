import re

import pytest

from catgirl_downloader.providers.nekobot import NekobotProvider, parse_nekobot_payload
from catgirl_downloader.providers.nekos_best import NekosBestProvider, parse_nekos_best_payload
from catgirl_downloader.providers.nekos_life import NekosLifeProvider, parse_nekos_life_payload
from catgirl_downloader.providers.nekosapi import NekosApiProvider, parse_nekosapi_payload
from catgirl_downloader.providers.waifu_pics import WaifuPicsProvider, parse_waifu_pics_payload


def test_parse_waifu_pics_payload() -> None:
    url = parse_waifu_pics_payload({"url": "https://img.example/catgirl.png"})
    assert url == "https://img.example/catgirl.png"


def test_parse_nekosapi_payload() -> None:
    payload = {
        "value": [
            {
                "url": "https://img.example/catgirl.webp",
                "rating": "safe",
                "tags": ["catgirl", "kemonomimi"],
            }
        ]
    }
    parsed = parse_nekosapi_payload(payload)
    assert len(parsed) == 1
    assert parsed[0].provider == "nekosapi"
    assert parsed[0].category == "catgirl"
    assert parsed[0].rating == "safe"
    assert "catgirl" in parsed[0].tags


@pytest.mark.anyio
async def test_waifu_provider_fetch_safe(httpx_mock) -> None:
    httpx_mock.add_response(
        url="https://api.waifu.pics/sfw/neko",
        json={"url": "https://img.example/waifu-safe.png"},
    )

    provider = WaifuPicsProvider()
    candidates = await provider.fetch_candidates(count=1, rating="safe", timeout=10.0, theme="catgirl")

    assert len(candidates) == 1
    assert candidates[0].provider == "waifu_pics"
    assert candidates[0].category == "catgirl"
    assert candidates[0].rating == "safe"
    assert candidates[0].url == "https://img.example/waifu-safe.png"


@pytest.mark.anyio
async def test_nekosapi_provider_fetch(httpx_mock) -> None:
    httpx_mock.add_response(
        url=re.compile(r"https://api\.nekosapi\.com/v4/images/random.*"),
        json={
            "value": [
                {
                    "url": "https://img.example/neko1.webp",
                    "rating": "suggestive",
                    "tags": ["catgirl"],
                },
                {
                    "url": "https://img.example/neko2.webp",
                    "rating": "safe",
                    "tags": ["catgirl", "girl"],
                },
            ]
        },
    )

    provider = NekosApiProvider()
    candidates = await provider.fetch_candidates(count=2, rating="safe", timeout=10.0, theme="catgirl")

    assert len(candidates) == 2
    assert candidates[0].provider == "nekosapi"
    assert candidates[0].category == "catgirl"
    assert candidates[0].url == "https://img.example/neko1.webp"


def test_parse_nekos_best_payload() -> None:
    payload = {"results": [{"url": "https://img.example/kitsune.png"}]}
    parsed = parse_nekos_best_payload(payload, theme="kitsune")
    assert len(parsed) == 1
    assert parsed[0].provider == "nekos_best"
    assert parsed[0].category == "kitsune"


def test_parse_nekos_life_payload() -> None:
    url = parse_nekos_life_payload({"url": "https://img.example/neko.jpg"})
    assert url == "https://img.example/neko.jpg"


def test_parse_nekobot_payload() -> None:
    url = parse_nekobot_payload({"success": True, "message": "https://img.example/neko.png"})
    assert url == "https://img.example/neko.png"


@pytest.mark.anyio
async def test_nekos_best_provider_fetch_kitsune(httpx_mock) -> None:
    httpx_mock.add_response(
        url=re.compile(r"https://nekos\.best/api/v2/kitsune\?amount=2"),
        json={
            "results": [
                {"url": "https://img.example/k1.png"},
                {"url": "https://img.example/k2.png"},
            ]
        },
    )

    provider = NekosBestProvider()
    candidates = await provider.fetch_candidates(count=2, rating="safe", timeout=10.0, theme="kitsune")

    assert len(candidates) == 2
    assert candidates[0].provider == "nekos_best"
    assert candidates[0].category == "kitsune"


@pytest.mark.anyio
async def test_nekos_life_provider_fetch(httpx_mock) -> None:
    httpx_mock.add_response(
        url="https://nekos.life/api/v2/img/fox_girl",
        json={"url": "https://img.example/f1.jpg"},
    )
    httpx_mock.add_response(
        url="https://nekos.life/api/v2/img/fox_girl",
        json={"url": "https://img.example/f2.jpg"},
    )

    provider = NekosLifeProvider()
    candidates = await provider.fetch_candidates(count=2, rating="any", timeout=10.0, theme="kitsune")

    assert len(candidates) == 2
    assert all(candidate.provider == "nekos_life" for candidate in candidates)
    assert all(candidate.category == "kitsune" for candidate in candidates)


@pytest.mark.anyio
async def test_nekobot_provider_fetch(httpx_mock) -> None:
    httpx_mock.add_response(
        url=re.compile(r"https://nekobot\.xyz/api/image\?type=neko"),
        json={"success": True, "message": "https://img.example/n1.jpg"},
    )

    provider = NekobotProvider()
    candidates = await provider.fetch_candidates(count=1, rating="any", timeout=10.0, theme="neko")

    assert len(candidates) == 1
    assert candidates[0].provider == "nekobot"
    assert candidates[0].category == "neko"
