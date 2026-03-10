# replyguy Agent Guide

## Scope
- `replyguy` is a terminal-native orchestrator for daily LinkedIn/X posting and local reply drafting from a Vim-first inbox.
- The product is keyboard-first, explicit, local-first, and inspectable. It is not a web dashboard.
- Public repo, private runtime state: keep `gi`, `go`, archives, SQLite, and config in XDG paths outside the repo.
- Use the existing `x` and `linkedin` CLIs for actual posting. Do not reimplement their auth flows here unless the user explicitly asks for that.

## Durable Deviations
- This app intentionally overrides the workspace thought-leadership rule that normally requires explicit approval before posting.
- For `replyguy`, unattended posting triggered locally by `replyguy gi` or the installed timer is allowed because the user explicitly asked for that behavior.
- Keep that exception documented here so later agents do not silently revert it.

## Product Rules
- `replyguy gi` opens the live inbox in `$VISUAL`, then `$EDITOR`, then `vim`. Exiting the editor digests the file and may publish directly to LinkedIn and X.
- `replyguy go` opens the latest digest output file.
- `replyguy` must archive the consumed inbox before clearing it.
- Clear the live inbox only after the digest file and SQLite writes succeed.
- If processing fails before the output is committed, leave the live inbox intact.
- Auto-replies are out of scope. `replyguy` suggests replies, but the user posts them manually.

## Content Rules
- For autonomous daily posting, source order is: latest resume, live discourse, brand voice, then nearby docs.
- Keep the writing direct, technically grounded, and anti-sludge.
- Same crux may recur across days, but avoid repeating the same `crux + angle` pair too soon.
- Keep LinkedIn plain text and keep X within 280 characters.

## Implementation Rules
- Keep the help path import-light and side-effect free.
- Keep HTTP logic out of CLI parsing; use small dedicated client modules.
- Prefer plain JSON config and SQLite over heavier local infrastructure.
- Timer automation should use a user-level `systemd` timer.
- Notifications should go through `notify-send` so Mako can display them.
