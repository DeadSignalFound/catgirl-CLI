# catgirl-downloader

Command line downloader for catgirl/neko/kitsune/femboy images from multiple public APIs.

## Install

```bash
pipx install .
```

## Usage

```bash
# Interactive REPL mode
catgirl

# Direct subcommands
catgirl download --count 5 --theme catgirl
catgirl download --count 8 --theme neko --provider auto
catgirl download --count 6 --theme kitsune --provider auto
catgirl download --count 5 --theme femboy --provider auto
catgirl download --count 5 --theme femboy --provider rule34 -r
catgirl providers
catgirl categories
```

## Ratings

Use `--rating` to filter requested content:

- `any` (default)
- `safe`
- `suggestive`
- `borderline`
- `explicit`

Examples:

```bash
catgirl download --count 5 --theme catgirl --rating safe
catgirl download --count 5 --theme catgirl --rating suggestive
catgirl download --count 5 --theme femboy --provider e621 --rating explicit
catgirl download --count 5 --theme femboy --provider rule34 --rating suggestive
```

Important notes:

- `waifu_pics` supports `any|safe|explicit` only.
- `nekos_best`, `nekos_life`, and `nekobot` support `any|safe` only.
- `femboy` with `waifu_pics` uses `nsfw/trap`, so `safe` is not available there.
- If a provider does not support the selected rating/theme combination, it may return `0` downloads.
- Use `--verbose` to see detailed warnings:

```bash
catgirl download --count 5 --theme femboy --provider rule34 --rating explicit --verbose
```

## Randomized Fetching

Some providers return similar top results repeatedly. Use `-r` (alias for `--randomize`) to randomize query pages/pools:

```bash
catgirl download --count 5 --theme femboy --provider e621 -r
catgirl download --count 5 --theme femboy --provider rule34 -r
```

`-r` is especially useful for `e621` and `rule34`.

## Output Layout

Downloads are now sorted into deeper folders by safety + theme + rating:

```text
downloads/
  sfw/
    catgirl/
      safe/
  nsfw/
    femboy/
      explicit/
      suggestive/
  unknown/
    <theme>/
      unknown/
```

So a safe catgirl image goes to:

```text
downloads/sfw/catgirl/safe/
```

## Interactive Mode

Run `catgirl` with no subcommand to open a REPL prompt:

```text
catgirl >
```

Press `Tab` in REPL mode to autocomplete commands and `set` values.
Themes: `catgirl`, `neko`, `kitsune`, `femboy` (plural aliases also work in REPL: `catgirls`, `nekos`, `femboys`).
Enable randomized fetching in REPL with: `set randomize true`.

Supported commands:

```text
help
show
set <field> <value>
run
providers
categories
clear
exit
```

## API Variety

Current provider set:
- `nekosapi`
- `waifu_pics`
- `nekos_best`
- `nekos_life`
- `nekobot`
- `e621`
- `rule34` (requires env credentials)

## Environment

The app loads `.env` automatically.

Required for femboy APIs:
- `E621_USER_AGENT` (recommended, set to your own value)
- `RULE34_USER_ID` and `RULE34_API_KEY` (required for `rule34` provider)
