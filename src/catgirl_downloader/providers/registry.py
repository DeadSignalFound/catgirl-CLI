from __future__ import annotations

from catgirl_downloader.models import Theme, UserRating
from catgirl_downloader.providers.base import Provider
from catgirl_downloader.providers.e621 import E621Provider
from catgirl_downloader.providers.nekosapi import NekosApiProvider
from catgirl_downloader.providers.nekobot import NekobotProvider
from catgirl_downloader.providers.nekos_best import NekosBestProvider
from catgirl_downloader.providers.nekos_life import NekosLifeProvider
from catgirl_downloader.providers.rule34 import Rule34Provider
from catgirl_downloader.providers.waifu_pics import WaifuPicsProvider

_PROVIDERS: dict[str, Provider] = {
    "waifu_pics": WaifuPicsProvider(),
    "nekosapi": NekosApiProvider(),
    "nekos_best": NekosBestProvider(),
    "nekos_life": NekosLifeProvider(),
    "nekobot": NekobotProvider(),
    "e621": E621Provider(),
    "rule34": Rule34Provider(),
}

_RATING_NOTES: dict[str, str] = {
    "waifu_pics": "any|safe|explicit",
    "nekosapi": "safe|suggestive|borderline|explicit",
    "nekos_best": "any|safe",
    "nekos_life": "any|safe",
    "nekobot": "any|safe",
    "e621": "any|safe|suggestive|borderline|explicit",
    "rule34": "any|safe|suggestive|borderline|explicit",
}


def list_provider_names() -> list[str]:
    return list(_PROVIDERS.keys())


def list_providers() -> list[Provider]:
    return list(_PROVIDERS.values())


def get_provider(name: str) -> Provider:
    if name not in _PROVIDERS:
        raise KeyError(f"Unknown provider: {name}")
    return _PROVIDERS[name]


def get_category_mappings() -> dict[str, str]:
    return {
        name: ",".join(provider.supported_themes)
        for name, provider in _PROVIDERS.items()
    }


def get_provider_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for name, provider in _PROVIDERS.items():
        rows.append(
            {
                "name": name,
                "themes": ",".join(provider.supported_themes),
                "rating_filter": "yes" if provider.supports_rating_filter else "no",
                "rating_notes": _RATING_NOTES.get(name, "unknown"),
                "status": "enabled",
            }
        )
    return rows


def get_supported_themes(provider_name: str) -> tuple[Theme, ...]:
    return get_provider(provider_name).supported_themes


def get_supported_ratings(provider_name: str) -> tuple[UserRating, ...]:
    return get_provider(provider_name).supported_ratings


def get_auto_provider_order(rating: UserRating, theme: Theme) -> list[str]:
    if theme == "catgirl":
        order = ["nekosapi", "waifu_pics", "nekos_life", "nekobot", "nekos_best"]
    elif theme == "neko":
        order = ["waifu_pics", "nekos_best", "nekos_life", "nekobot", "nekosapi"]
    elif theme == "femboy":
        order = ["waifu_pics", "e621", "rule34"]
    else:
        order = ["nekos_best", "nekos_life", "nekosapi", "waifu_pics", "nekobot"]

    filtered: list[str] = []
    for provider_name in order:
        provider = get_provider(provider_name)
        if theme not in provider.supported_themes:
            continue
        if rating not in provider.supported_ratings:
            continue
        filtered.append(provider_name)
    return filtered
