from __future__ import annotations

import logging
import shlex
import sys
from enum import Enum
from pathlib import Path
from typing import Annotated, Any

import anyio
import typer
from dotenv import find_dotenv, load_dotenv
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from catgirl_downloader.downloader import DownloadRunner
from catgirl_downloader.providers.registry import get_category_mappings, get_provider_rows

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import Completer, Completion
except Exception:  # pragma: no cover - optional dependency fallback
    PromptSession = None
    Completer = object  # type: ignore[assignment]
    Completion = None  # type: ignore[assignment]

app = typer.Typer(
    add_completion=False,
    invoke_without_command=True,
    help="Download catgirl/neko/kitsune/femboy images from public APIs.",
)

CONSOLE = Console(highlight=False)


def _load_environment() -> None:
    # Prefer the shell's current directory so installed entry points pick up local .env files.
    cwd_env = Path.cwd() / ".env"
    if cwd_env.exists():
        load_dotenv(dotenv_path=cwd_env)
        return

    discovered = find_dotenv(usecwd=True)
    if discovered:
        load_dotenv(dotenv_path=discovered)


_load_environment()


class ProviderChoice(str, Enum):
    AUTO = "auto"
    WAIFU_PICS = "waifu_pics"
    NEKOSAPI = "nekosapi"
    NEKOS_BEST = "nekos_best"
    NEKOS_LIFE = "nekos_life"
    NEKOBOT = "nekobot"
    E621 = "e621"
    RULE34 = "rule34"


class RatingChoice(str, Enum):
    ANY = "any"
    SAFE = "safe"
    SUGGESTIVE = "suggestive"
    BORDERLINE = "borderline"
    EXPLICIT = "explicit"


class ThemeChoice(str, Enum):
    CATGIRL = "catgirl"
    NEKO = "neko"
    KITSUNE = "kitsune"
    FEMBOY = "femboy"


REPL_COMMANDS = ["help", "show", "set", "run", "providers", "categories", "clear", "exit", "quit"]
SETTABLE_FIELDS = [
    "count",
    "provider",
    "theme",
    "rating",
    "randomize",
    "out",
    "concurrency",
    "retries",
    "timeout",
    "verbose",
]
SET_FIELD_SUGGESTIONS: dict[str, list[str]] = {
    "count": ["1", "5", "10", "25", "50", "100"],
    "provider": [choice.value for choice in ProviderChoice],
    "theme": [choice.value for choice in ThemeChoice],
    "rating": [choice.value for choice in RatingChoice],
    "out": ["./downloads"],
    "concurrency": ["1", "2", "4", "8", "16"],
    "retries": ["0", "1", "2", "3", "4", "5"],
    "timeout": ["10", "20", "30", "60", "120"],
    "verbose": ["true", "false", "yes", "no", "1", "0"],
    "randomize": ["true", "false", "yes", "no", "1", "0"],
    "random": ["true", "false", "yes", "no", "1", "0"],
}


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.ERROR
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


def _display_value(value: object) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def _print_title(text: str) -> None:
    CONSOLE.print()
    CONSOLE.print(Text(text, style="bold bright_blue"))


def _print_kv_rows(rows: list[tuple[str, object]]) -> None:
    table = Table(
        box=box.SIMPLE_HEAD,
        show_header=False,
        pad_edge=False,
        expand=False,
    )
    table.add_column("key", style="bold cyan", no_wrap=True)
    table.add_column("value", style="bright_magenta")
    for key, value in rows:
        table.add_row(key, _display_value(value))
    CONSOLE.print(table)


def _print_summary(requested: int, downloaded: int, duplicates: int, failed: int, output_dir: str) -> None:
    _print_title("Run Summary")
    _print_kv_rows(
        [
            ("Requested", requested),
            ("Downloaded", downloaded),
            ("Duplicates", duplicates),
            ("Failed", failed),
            ("Output", output_dir),
        ]
    )

    if downloaded == requested and failed == 0:
        status_style = "bold green"
        status_text = "Success"
    elif downloaded > 0:
        status_style = "bold yellow"
        status_text = "Partial"
    else:
        status_style = "bold red"
        status_text = "Failed"
    CONSOLE.print(Text(f"Status: {status_text}", style=status_style))


def _validate_range(name: str, value: int | float, minimum: int | float, maximum: int | float) -> None:
    if value < minimum or value > maximum:
        raise typer.BadParameter(f"{name} must be between {minimum} and {maximum}.")


def _parse_provider(value: str) -> ProviderChoice:
    normalized = value.strip().lower()
    try:
        return ProviderChoice(normalized)
    except ValueError as exc:
        allowed = ", ".join(choice.value for choice in ProviderChoice)
        raise typer.BadParameter(f"provider must be one of: {allowed}") from exc


def _parse_rating(value: str) -> RatingChoice:
    normalized = value.strip().lower()
    try:
        return RatingChoice(normalized)
    except ValueError as exc:
        allowed = ", ".join(choice.value for choice in RatingChoice)
        raise typer.BadParameter(f"rating must be one of: {allowed}") from exc


def _parse_theme(value: str) -> ThemeChoice:
    normalized = value.strip().lower()
    aliases = {
        "catgirls": "catgirl",
        "nekos": "neko",
        "femboys": "femboy",
    }
    normalized = aliases.get(normalized, normalized)
    try:
        return ThemeChoice(normalized)
    except ValueError as exc:
        allowed = ", ".join(choice.value for choice in ThemeChoice)
        raise typer.BadParameter(f"theme must be one of: {allowed}") from exc


def _parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    truthy = {"1", "true", "yes", "y", "on"}
    falsy = {"0", "false", "no", "n", "off"}
    if normalized in truthy:
        return True
    if normalized in falsy:
        return False
    raise typer.BadParameter("boolean must be one of: true,false,yes,no,1,0")


def _suggest_matches(options: list[str], prefix: str) -> list[str]:
    lowered_prefix = prefix.lower()
    return [option for option in options if option.lower().startswith(lowered_prefix)]


def _suggest_repl_completions(text_before_cursor: str) -> tuple[list[str], int]:
    stripped = text_before_cursor.lstrip()
    if not stripped:
        return REPL_COMMANDS, 0

    tokens = stripped.split()
    ends_with_space = text_before_cursor.endswith(" ")

    if len(tokens) == 1 and not ends_with_space:
        current = tokens[0]
        return _suggest_matches(REPL_COMMANDS, current), -len(current)

    command = tokens[0].lower()
    if command != "set":
        return [], 0

    if len(tokens) == 1 and ends_with_space:
        return SETTABLE_FIELDS, 0

    if len(tokens) == 2 and not ends_with_space:
        field_prefix = tokens[1]
        return _suggest_matches(SETTABLE_FIELDS, field_prefix), -len(field_prefix)

    field = tokens[1].lower() if len(tokens) > 1 else ""
    options = SET_FIELD_SUGGESTIONS.get(field, [])
    if not options:
        return [], 0
    if ends_with_space:
        return options, 0
    value_prefix = tokens[-1]
    return _suggest_matches(options, value_prefix), -len(value_prefix)


if PromptSession is not None and Completion is not None:
    class ReplCompleter(Completer):
        def get_completions(self, document: Any, complete_event: Any) -> Any:
            suggestions, start_position = _suggest_repl_completions(document.text_before_cursor)
            for suggestion in suggestions:
                yield Completion(suggestion, start_position=start_position)


def _format_settings(settings: dict[str, object]) -> list[tuple[str, object]]:
    return [
        ("count", settings["count"]),
        ("provider", settings["provider"]),
        ("theme", settings["theme"]),
        ("rating", settings["rating"]),
        ("randomize", settings["randomize"]),
        ("out", settings["out"]),
        ("concurrency", settings["concurrency"]),
        ("retries", settings["retries"]),
        ("timeout", settings["timeout"]),
        ("verbose", settings["verbose"]),
    ]


def _print_repl_help() -> None:
    _print_title("Interactive Commands")
    help_table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold bright_cyan")
    help_table.add_column("Command", style="cyan", no_wrap=True)
    help_table.add_column("Description", style="white")
    help_table.add_row("help", "Show this help")
    help_table.add_row("show", "Print current settings")
    help_table.add_row("set <field> <value>", "Update one setting")
    help_table.add_row("run", "Execute download with current settings")
    help_table.add_row("providers", "Show provider capabilities")
    help_table.add_row("categories", "Show provider to theme mappings")
    help_table.add_row("clear", "Clear screen and redraw layout")
    help_table.add_row("exit | quit", "Leave interactive mode")
    help_table.add_row("Tab", "Autocomplete commands and set values")
    CONSOLE.print(help_table)
    CONSOLE.print(
        Text(
            "Fields: count, provider, theme, rating, randomize, out, concurrency, retries, timeout, verbose",
            style="dim",
        )
    )


def _print_settings(settings: dict[str, object]) -> None:
    _print_title("Current Settings")
    _print_kv_rows(_format_settings(settings))


def _build_repl_session() -> Any | None:
    if PromptSession is None:
        return None
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return None
    return PromptSession(completer=ReplCompleter(), complete_while_typing=True)


def _read_repl_line(session: Any | None) -> str:
    if session is not None:
        return session.prompt("catgirl > ").strip()
    typer.secho("catgirl > ", fg=typer.colors.BRIGHT_MAGENTA, bold=True, nl=False)
    return input().strip()


def _update_setting(settings: dict[str, object], field: str, raw_value: str) -> None:
    key = field.strip().lower()
    if key == "count":
        value = int(raw_value)
        _validate_range("count", value, 1, 200)
        settings["count"] = value
        return
    if key == "provider":
        settings["provider"] = _parse_provider(raw_value)
        return
    if key == "theme":
        settings["theme"] = _parse_theme(raw_value)
        return
    if key == "rating":
        settings["rating"] = _parse_rating(raw_value)
        return
    if key in {"randomize", "random", "r"}:
        settings["randomize"] = _parse_bool(raw_value)
        return
    if key == "out":
        settings["out"] = Path(raw_value)
        return
    if key == "concurrency":
        value = int(raw_value)
        _validate_range("concurrency", value, 1, 16)
        settings["concurrency"] = value
        return
    if key == "retries":
        value = int(raw_value)
        _validate_range("retries", value, 0, 5)
        settings["retries"] = value
        return
    if key == "timeout":
        value = float(raw_value)
        _validate_range("timeout", value, 1.0, 120.0)
        settings["timeout"] = value
        return
    if key == "verbose":
        settings["verbose"] = _parse_bool(raw_value)
        return
    raise typer.BadParameter(f"unknown field '{field}'")


def _print_banner(autocomplete_enabled: bool) -> None:
    title = Text("CATGIRL INTERACTIVE MODE", style="bold bright_blue")
    body = Text()
    body.append("Type ")
    body.append("help", style="bold cyan")
    body.append(" for commands. Use ")
    body.append("run", style="bold cyan")
    body.append(" to download.\n")
    body.append("Prompt: ", style="dim")
    body.append("catgirl >", style="bold magenta")
    if autocomplete_enabled:
        body.append("\nTab completion: ", style="dim")
        body.append("enabled", style="bold green")
    else:
        body.append("\nTab completion: ", style="dim")
        body.append("unavailable in this terminal", style="yellow")
    CONSOLE.print(Panel(body, title=title, border_style="bright_blue", box=box.ROUNDED, expand=False))


def _run_download(
    *,
    count: int,
    provider: ProviderChoice,
    out: Path,
    concurrency: int,
    retries: int,
    timeout: float,
    theme: ThemeChoice,
    rating: RatingChoice,
    randomize: bool,
    verbose: bool,
) -> int:
    _configure_logging(verbose)
    out_dir = Path(out)
    runner = DownloadRunner(
        count=count,
        provider_name=provider.value,
        out_dir=out_dir,
        concurrency=concurrency,
        retries=retries,
        timeout=timeout,
        theme=theme.value,
        rating=rating.value,
        randomize=randomize,
    )

    try:
        anyio.run(runner.run)
    except KeyboardInterrupt:
        CONSOLE.print(Text("Download cancelled by user.", style="bold yellow"))
        summary = runner.summary()
        _print_summary(
            requested=summary.requested,
            downloaded=summary.downloaded,
            duplicates=summary.duplicates,
            failed=summary.failed,
            output_dir=summary.output_dir,
        )
        return 1

    for warning in runner.warnings:
        CONSOLE.print(Text(f"Warning: {warning}", style="bold yellow"))

    summary = runner.summary()
    _print_summary(
        requested=summary.requested,
        downloaded=summary.downloaded,
        duplicates=summary.duplicates,
        failed=summary.failed,
        output_dir=summary.output_dir,
    )
    return runner.exit_code()


@app.callback()
def main(ctx: typer.Context) -> None:
    if ctx.invoked_subcommand is not None:
        return

    settings: dict[str, object] = {
        "count": 1,
        "provider": ProviderChoice.AUTO,
        "theme": ThemeChoice.CATGIRL,
        "rating": RatingChoice.ANY,
        "randomize": False,
        "out": Path("./downloads"),
        "concurrency": 4,
        "retries": 3,
        "timeout": 20.0,
        "verbose": False,
    }

    session = _build_repl_session()
    _print_banner(autocomplete_enabled=session is not None)
    _print_settings(settings)

    while True:
        try:
            raw = _read_repl_line(session)
        except (EOFError, KeyboardInterrupt):
            CONSOLE.print(Text("\nGoodbye.", style="dim"))
            raise typer.Exit(code=0) from None

        if not raw:
            continue

        try:
            parts = shlex.split(raw, posix=False)
            command = parts[0].lower()

            if command in {"exit", "quit"}:
                CONSOLE.print(Text("Goodbye.", style="dim"))
                raise typer.Exit(code=0)
            if command == "help":
                _print_repl_help()
                continue
            if command == "clear":
                typer.clear()
                _print_banner(autocomplete_enabled=session is not None)
                _print_settings(settings)
                continue
            if command == "show":
                _print_settings(settings)
                continue
            if command == "providers":
                providers()
                continue
            if command == "categories":
                categories()
                continue
            if command == "set":
                if len(parts) < 3:
                    raise typer.BadParameter("usage: set <field> <value>")
                field = parts[1]
                value = " ".join(parts[2:])
                _update_setting(settings, field, value)
                display_key = field.strip().lower()
                if display_key in {"random", "r"}:
                    display_key = "randomize"
                CONSOLE.print(
                    Text(
                        f"Updated {display_key} = {_display_value(settings[display_key])}",
                        style="bold green",
                    )
                )
                continue
            if command == "run":
                CONSOLE.print(Text("Starting download...", style="bold bright_cyan"))
                code = _run_download(
                    count=settings["count"],  # type: ignore[arg-type]
                    provider=settings["provider"],  # type: ignore[arg-type]
                    out=settings["out"],  # type: ignore[arg-type]
                    concurrency=settings["concurrency"],  # type: ignore[arg-type]
                    retries=settings["retries"],  # type: ignore[arg-type]
                    timeout=settings["timeout"],  # type: ignore[arg-type]
                    theme=settings["theme"],  # type: ignore[arg-type]
                    rating=settings["rating"],  # type: ignore[arg-type]
                    randomize=settings["randomize"],  # type: ignore[arg-type]
                    verbose=settings["verbose"],  # type: ignore[arg-type]
                )
                if code == 0:
                    CONSOLE.print(Text("Run completed successfully.", style="bold green"))
                else:
                    CONSOLE.print(Text("Run completed with failures.", style="bold yellow"))
                continue
            CONSOLE.print(Text(f"Unknown command: {command}", style="bold red"))
        except (ValueError, typer.BadParameter) as exc:
            CONSOLE.print(Text(f"Error: {exc}", style="bold red"))


@app.command("providers")
def providers() -> None:
    """Show provider capabilities."""
    _print_title("Providers")
    table = Table(
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold bright_cyan",
    )
    table.add_column("Name", style="bright_magenta", no_wrap=True)
    table.add_column("Themes", style="bright_yellow")
    table.add_column("Rating Filter", style="bright_cyan", no_wrap=True)
    table.add_column("Rating Notes", style="white")
    table.add_column("Status", style="green", no_wrap=True)
    for row in get_provider_rows():
        table.add_row(
            row["name"],
            row["themes"],
            row["rating_filter"],
            row["rating_notes"],
            row["status"],
        )
    CONSOLE.print(table)


@app.command("categories")
def categories() -> None:
    """Show provider to theme mappings."""
    _print_title("Categories")
    table = Table(box=box.SIMPLE_HEAVY, show_header=True, header_style="bold bright_cyan")
    table.add_column("Provider", style="bright_magenta", no_wrap=True)
    table.add_column("Themes", style="bright_yellow")
    mappings = get_category_mappings()
    for provider_name, category in mappings.items():
        table.add_row(provider_name, category)
    CONSOLE.print(table)


@app.command("download")
def download(
    count: Annotated[int, typer.Option("--count", min=1, max=200, help="Number of images to download.")] = 1,
    provider: Annotated[
        ProviderChoice,
        typer.Option("--provider", help="Provider name or auto fallback strategy."),
    ] = ProviderChoice.AUTO,
    out: Annotated[Path, typer.Option("--out", help="Output directory root.")] = Path("./downloads"),
    concurrency: Annotated[
        int,
        typer.Option("--concurrency", min=1, max=16, help="Concurrent download workers."),
    ] = 4,
    retries: Annotated[
        int,
        typer.Option("--retries", min=0, max=5, help="Retries for transient failures."),
    ] = 3,
    timeout: Annotated[
        float,
        typer.Option("--timeout", min=1.0, max=120.0, help="Request timeout in seconds."),
    ] = 20.0,
    theme: Annotated[
        ThemeChoice,
        typer.Option("--theme", help="Target image theme."),
    ] = ThemeChoice.CATGIRL,
    rating: Annotated[
        RatingChoice,
        typer.Option("--rating", help="Requested content rating."),
    ] = RatingChoice.ANY,
    randomize: Annotated[
        bool,
        typer.Option(
            "--randomize",
            "-r",
            help="Randomize provider queries to avoid repeated top results.",
        ),
    ] = False,
    verbose: Annotated[bool, typer.Option("--verbose", help="Enable debug logging.")] = False,
) -> None:
    """Download catgirl/neko/kitsune/femboy images."""
    code = _run_download(
        count=count,
        provider=provider,
        out=out,
        concurrency=concurrency,
        retries=retries,
        timeout=timeout,
        theme=theme,
        rating=rating,
        randomize=randomize,
        verbose=verbose,
    )
    raise typer.Exit(code=code)
