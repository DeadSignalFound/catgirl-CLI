# catgirl-downloader

Command line downloader for catgirl/neko/kitsune images from multiple public APIs.

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
catgirl providers
catgirl categories
```

## Interactive Mode

Run `catgirl` with no subcommand to open a REPL prompt:

```text
catgirl >
```

Press `Tab` in REPL mode to autocomplete commands and `set` values.
Themes: `catgirl`, `neko`, `kitsune` (plural aliases also work in REPL: `catgirls`, `nekos`).

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
