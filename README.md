# replyguy

Vim-first CLI that turns bookmarked X posts into:

- reply-guy suggestions for other people's posts
- an archived bookmark queue with reply options you can review and post

The repo can be public because all mutable runtime state stays outside the repo
in XDG directories.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/ryangerardwilson/replyguy/main/install.sh | bash
```

If `~/.local/bin` is not already on your `PATH`, add it once to `~/.bashrc`
and reload your shell:

```bash
export PATH="$HOME/.local/bin:$PATH"
source ~/.bashrc
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
  inhale bookmarked X posts now and report how many replies are ready
  # inhale
  replyguy inhale

  run inhale hourly in the background, disable it, or inspect timer plus queue state
  # ti | td | st
  replyguy ti
  replyguy td
  replyguy st

  exhale bookmarked X posts, choose a reply, do a final edit, post it, and remove the bookmark
  # exhale
  replyguy exhale

  show whether inhale is running and what is queued
  # status
  replyguy status

  open the config in your editor
  # conf
  replyguy conf
```

`replyguy inhale` asks the `x` app for bookmarked posts, prepares reply options,
stores the queue under XDG state, and prints how many new items were inhaled and
how many now await exhale.

`replyguy ti` installs an hourly user timer through systemd so inhale keeps
running while you keep bookmarking posts. `replyguy td` disables that timer.
`replyguy st` shows the timer status through `systemctl --user` and then prints
the current replyguy queue summary, including results from manual inhale runs.

`replyguy exhale` walks that queue in the terminal, lets you pick an option,
opens a final edit in your editor, opens the bookmarked post in Google Chrome
Stable, copies the edited reply to the clipboard with `wl-copy`, and removes
the bookmark. That leaves the final send as a manual paste in X.

`replyguy status` shows whether an inhale job is currently running, the last
inhale timestamp, how many items were new in the latest inhale, pending count,
posted-but-not-unbookmarked count, and the latest generation error if one
exists.

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
- bookmark inhale limit
- optional `x_command` override if `replyguy` should call a non-default `x` binary

`replyguy` uses the local `codex` CLI for generation, so you need to be logged in
with `codex login`.

By default, `replyguy` injects only
`/home/ryan/Documents/agent_context/REPLY_GUY_GUIDELINES.md` as standing
context for drafting.

## State

Runtime state lives outside the repo:

- live muse under `~/.local/state/replyguy/`
- job archives under `~/.local/state/replyguy/jobs/`
- bookmark queue under `~/.local/state/replyguy/bookmark_queue.json`

That local state is not committed and is not part of the public repo.

## Runtime Requirements

- `google-chrome-stable` for opening the bookmarked post during `exhale`
- `wl-copy` for putting the selected reply on the clipboard
- `systemd --user` if you want the hourly inhale timer via `replyguy ti`

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

`replyguy -v` prints the installed app version from `_version.py`. Source checkouts keep a placeholder value; tagged release builds should stamp the shipped artifact with the real version.
