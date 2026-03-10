# replyguy

Vim-first CLI that turns one local inbox into:

- a daily LinkedIn/X post pair
- reply-guy suggestions for other people's posts
- an archived digest with what was posted and what can be replied with

The repo can be public because all mutable runtime state stays outside the repo
in XDG directories.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/ryangerardwilson/replyguy/main/install.sh | bash
```

## Usage

```text
Replyguy CLI

flags:
  replyguy -h
    show this help
  replyguy -v
    print the installed version
  replyguy -u
    upgrade to the latest release

features:
  open the inbox in your editor, then digest it on exit and act on it
  # gi [<path_to_input_txt_or_md_file>]
  replyguy gi
  replyguy gi ~/tmp/ideas.txt

  open the latest digest output in your editor
  # go
  replyguy go

  open the config in your editor
  # conf
  replyguy conf

  install, disable, or inspect the daily timer
  # ti|td|st
  replyguy ti
  replyguy td
  replyguy st
```

`replyguy gi` may publish directly to LinkedIn and X when the inbox contains
usable post guidance.

## Config

Open the config with:

```bash
replyguy conf
```

Default config path:

```text
~/.config/replyguy/config.json
```

The default config stores:

- Codex model
- Codex reasoning effort
- `codex_context_paths` for local docs that should be injected before drafting
- resume URL
- daily topic source URLs
- timer schedule
- posting command tokens for `x` and `linkedin`

`replyguy` uses the local `codex` CLI for generation, so you need to be logged in
with `codex login`.

## State

Runtime state lives outside the repo:

- live inbox and digest under `~/.local/state/replyguy/`
- job archives under `~/.local/state/replyguy/jobs/`
- SQLite DB under `~/.local/state/replyguy/state.db`

That local state is not committed and is not part of the public repo.

## Source Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py -h
```

## Version And Upgrade

```bash
replyguy -v
replyguy -u
```
