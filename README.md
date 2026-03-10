# replyguy

Vim-first CLI that turns one local rant into:

- reply-guy suggestions for other people's posts
- an archived muse with reply options you can copy-paste manually

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
  open the rant file in your editor, then launch drafting in the background
  # rant [<path_to_input_txt_or_md_file>]
  replyguy rant
  replyguy rant ~/tmp/ideas.txt

  open the latest muse output in your editor, then clear it on close
  # muse
  replyguy muse

  open the config in your editor
  # conf
  replyguy conf
```

`replyguy rant` launches the work in the background and returns your terminal
immediately. Completion or failure is reported through Mako via `notify-send`.
`replyguy` does not publish to LinkedIn or X. It only drafts replies for manual
posting.

`replyguy muse` opens the latest generated output and clears the live `muse`
file after you close the editor. Archived per-run muses remain under the jobs
directory.

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
- reply count per target

`replyguy` uses the local `codex` CLI for generation, so you need to be logged in
with `codex login`.

By default, `replyguy` injects only
`/home/ryan/Documents/agent_context/REPLY_GUY_GUIDELINES.md` as standing
context for drafting.

## State

Runtime state lives outside the repo:

- live rant and muse under `~/.local/state/replyguy/`
- job archives under `~/.local/state/replyguy/jobs/`

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
