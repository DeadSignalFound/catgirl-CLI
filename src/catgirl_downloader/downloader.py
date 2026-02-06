from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import anyio
import httpx

from catgirl_downloader.fs import (
    atomic_write_bytes,
    build_filename,
    ensure_category_dir,
    extension_from_content_type,
)
from catgirl_downloader.models import DownloadResult, DownloadSummary, RemoteImage, Theme, UserRating
from catgirl_downloader.providers.registry import get_auto_provider_order, get_provider

LOGGER = logging.getLogger(__name__)
BACKOFF_SCHEDULE = (0.5, 1.0, 2.0)


def dedupe_candidates(candidates: Sequence[RemoteImage]) -> tuple[list[RemoteImage], list[DownloadResult]]:
    seen_urls: set[str] = set()
    unique: list[RemoteImage] = []
    duplicate_results: list[DownloadResult] = []

    for item in candidates:
        if item.url in seen_urls:
            duplicate_results.append(
                DownloadResult(
                    url=item.url,
                    path=None,
                    provider=item.provider,
                    status="skipped_duplicate",
                    error="Duplicate URL in candidate list",
                )
            )
            continue
        seen_urls.add(item.url)
        unique.append(item)
    return unique, duplicate_results


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.RequestError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


def _retry_delay(attempt_index: int) -> float:
    if attempt_index < len(BACKOFF_SCHEDULE):
        return BACKOFF_SCHEDULE[attempt_index]
    return BACKOFF_SCHEDULE[-1]


async def _download_one(
    client: httpx.AsyncClient,
    image: RemoteImage,
    out_dir: Path,
    retries: int,
) -> DownloadResult:
    for attempt in range(retries + 1):
        try:
            response = await client.get(image.url)
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            if not content_type.lower().startswith("image/"):
                raise ValueError(f"Non-image content type: {content_type or 'missing'}")

            extension = extension_from_content_type(content_type, image.url)
            category_dir = ensure_category_dir(out_dir, image.category)
            file_name = build_filename(image.provider, image.url, extension)
            destination = category_dir / file_name
            atomic_write_bytes(destination, response.content)

            return DownloadResult(
                url=image.url,
                path=str(destination),
                provider=image.provider,
                status="ok",
                error=None,
            )
        except Exception as exc:
            if attempt < retries and _is_retryable(exc):
                await anyio.sleep(_retry_delay(attempt))
                continue
            return DownloadResult(
                url=image.url,
                path=None,
                provider=image.provider,
                status="failed",
                error=str(exc),
            )

    return DownloadResult(
        url=image.url,
        path=None,
        provider=image.provider,
        status="failed",
        error="Unreachable retry branch",
    )


async def download_candidates(
    candidates: Sequence[RemoteImage],
    out_dir: Path,
    concurrency: int,
    retries: int,
    timeout: float,
) -> list[DownloadResult]:
    if not candidates:
        return []

    semaphore = anyio.Semaphore(concurrency)
    results: list[DownloadResult] = []

    async with httpx.AsyncClient(timeout=httpx.Timeout(timeout), follow_redirects=True) as client:
        async def worker(item: RemoteImage) -> None:
            async with semaphore:
                result = await _download_one(client, item, out_dir, retries)
                results.append(result)

        async with anyio.create_task_group() as task_group:
            for candidate in candidates:
                task_group.start_soon(worker, candidate)

    return results


@dataclass
class DownloadRunner:
    count: int
    provider_name: str
    out_dir: Path
    concurrency: int
    retries: int
    timeout: float
    rating: UserRating
    theme: Theme = "catgirl"
    warnings: list[str] = field(default_factory=list)
    results: list[DownloadResult] = field(default_factory=list)

    async def run(self) -> list[DownloadResult]:
        candidates = await self._fetch_candidates()
        unique_candidates, duplicate_results = dedupe_candidates(candidates)
        self.results.extend(duplicate_results)

        # Keep the requested upper bound strict even if providers over-return.
        if len(unique_candidates) > self.count:
            unique_candidates = unique_candidates[: self.count]

        downloaded = await download_candidates(
            candidates=unique_candidates,
            out_dir=self.out_dir,
            concurrency=self.concurrency,
            retries=self.retries,
            timeout=self.timeout,
        )
        self.results.extend(downloaded)
        return self.results

    async def _fetch_candidates(self) -> list[RemoteImage]:
        if self.provider_name == "auto":
            return await self._fetch_auto_candidates()
        return await self._fetch_single_provider(self.provider_name, self.count)

    async def _fetch_single_provider(self, provider_name: str, count: int) -> list[RemoteImage]:
        provider = get_provider(provider_name)
        if self.theme not in provider.supported_themes:
            self.warnings.append(
                f"{provider_name} does not support theme '{self.theme}'. "
                f"Supported: {', '.join(provider.supported_themes)}."
            )
            return []
        if self.rating not in provider.supported_ratings:
            self.warnings.append(
                f"{provider_name} does not support rating '{self.rating}'. "
                f"Supported: {', '.join(provider.supported_ratings)}."
            )
            return []
        return await provider.fetch_candidates(count, self.rating, self.timeout, self.theme)

    async def _fetch_auto_candidates(self) -> list[RemoteImage]:
        collected: list[RemoteImage] = []
        remaining = self.count
        for provider_name in get_auto_provider_order(self.rating, self.theme):
            if remaining <= 0:
                break
            fetched = await self._fetch_single_provider(provider_name, remaining)
            collected.extend(fetched)
            remaining = self.count - len(collected)
        return collected[: self.count]

    def summary(self) -> DownloadSummary:
        downloaded = sum(1 for result in self.results if result.status == "ok")
        failed = sum(1 for result in self.results if result.status == "failed")
        duplicates = sum(1 for result in self.results if result.status == "skipped_duplicate")
        return DownloadSummary(
            requested=self.count,
            downloaded=downloaded,
            failed=failed,
            duplicates=duplicates,
            output_dir=str(self.out_dir.resolve()),
        )

    def exit_code(self) -> int:
        summary = self.summary()
        if summary.downloaded == self.count:
            return 0
        return 1


async def run_download(
    count: int,
    provider_name: str,
    out_dir: Path,
    concurrency: int,
    retries: int,
    timeout: float,
    rating: UserRating,
    theme: Theme = "catgirl",
) -> tuple[list[DownloadResult], DownloadSummary, list[str]]:
    runner = DownloadRunner(
        count=count,
        provider_name=provider_name,
        out_dir=out_dir,
        concurrency=concurrency,
        retries=retries,
        timeout=timeout,
        rating=rating,
        theme=theme,
    )
    results = await runner.run()
    return results, runner.summary(), runner.warnings
