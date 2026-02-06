import re
from pathlib import Path

from typer.testing import CliRunner

from catgirl_downloader.cli import app, _suggest_repl_completions

runner = CliRunner()


def test_providers_command_lists_known_providers() -> None:
    result = runner.invoke(app, ["providers"])
    assert result.exit_code == 0
    assert "waifu_pics" in result.output
    assert "nekosapi" in result.output
    assert "nekos_best" in result.output
    assert "nekos_life" in result.output
    assert "nekobot" in result.output


def test_categories_command_lists_fixed_mappings() -> None:
    result = runner.invoke(app, ["categories"])
    assert result.exit_code == 0
    assert "waifu_pics" in result.output
    assert "catgirl,neko" in result.output
    assert "nekosapi" in result.output
    assert "catgirl" in result.output
    assert "nekos_best" in result.output
    assert "catgirl,neko,kitsune" in result.output


def test_download_count_three_writes_files(httpx_mock, tmp_path: Path) -> None:
    httpx_mock.add_response(
        url=re.compile(r"https://api\.nekosapi\.com/v4/images/random.*"),
        json={
            "value": [
                {"url": "https://img.example/one.png", "rating": "safe", "tags": ["catgirl"]},
                {"url": "https://img.example/two.png", "rating": "safe", "tags": ["catgirl"]},
                {"url": "https://img.example/three.png", "rating": "safe", "tags": ["catgirl"]},
            ]
        },
    )
    httpx_mock.add_response(
        url="https://img.example/one.png",
        headers={"content-type": "image/png"},
        content=b"1",
    )
    httpx_mock.add_response(
        url="https://img.example/two.png",
        headers={"content-type": "image/png"},
        content=b"2",
    )
    httpx_mock.add_response(
        url="https://img.example/three.png",
        headers={"content-type": "image/png"},
        content=b"3",
    )

    result = runner.invoke(
        app,
        [
            "download",
            "--count",
            "3",
            "--provider",
            "nekosapi",
            "--rating",
            "safe",
            "--out",
            str(tmp_path),
        ],
    )

    files = list((tmp_path / "catgirl").glob("*"))
    assert result.exit_code == 0
    assert len(files) == 3


def test_download_unsupported_waifu_rating_exits_non_zero(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "download",
            "--count",
            "1",
            "--provider",
            "waifu_pics",
            "--rating",
            "suggestive",
            "--out",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 1
    assert "does not support rating" in result.output.lower()


def test_invalid_count_and_rating_fail_fast() -> None:
    bad_count = runner.invoke(app, ["download", "--count", "0"])
    bad_rating = runner.invoke(app, ["download", "--rating", "invalid"])

    assert bad_count.exit_code == 2
    assert bad_rating.exit_code == 2


def test_no_args_launches_interactive_mode(httpx_mock, tmp_path: Path) -> None:
    httpx_mock.add_response(
        url=re.compile(r"https://api\.nekosapi\.com/v4/images/random.*"),
        json={
            "value": [
                {"url": "https://img.example/interactive.png", "rating": "safe", "tags": ["catgirl"]},
            ]
        },
    )
    httpx_mock.add_response(
        url="https://img.example/interactive.png",
        headers={"content-type": "image/png"},
        content=b"interactive",
    )

    user_input = "\n".join(
        [
            "set provider nekosapi",
            "set rating safe",
            f"set out {tmp_path}",
            "set count 1",
            "run",
            "clear",
            "exit",
        ]
    )
    result = runner.invoke(app, [], input=user_input + "\n")

    files = list((tmp_path / "catgirl").glob("*"))
    assert result.exit_code == 0
    assert "CATGIRL INTERACTIVE MODE" in result.output
    assert "catgirl >" in result.output
    assert "unknown command: clear" not in result.output
    assert len(files) == 1


def test_repl_completion_suggests_commands() -> None:
    suggestions, start_position = _suggest_repl_completions("he")
    assert "help" in suggestions
    assert start_position == -2


def test_repl_completion_suggests_set_fields() -> None:
    suggestions, start_position = _suggest_repl_completions("set pro")
    assert "provider" in suggestions
    assert start_position == -3


def test_repl_completion_suggests_set_values() -> None:
    suggestions, start_position = _suggest_repl_completions("set rating s")
    assert "safe" in suggestions
    assert "suggestive" in suggestions
    assert start_position == -1


def test_repl_completion_suggests_theme_values() -> None:
    suggestions, start_position = _suggest_repl_completions("set theme k")
    assert "kitsune" in suggestions
    assert start_position == -1
