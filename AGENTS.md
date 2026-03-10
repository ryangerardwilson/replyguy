# replyguy Agent Guide

## Scope
- `replyguy` is a terminal-native reply drafting tool that turns rough rants into usable muses.
- The product is keyboard-first, explicit, local-first, and inspectable. It is not a web dashboard.
- Public repo, private runtime state: keep `rant`, `muse`, archives, and config in XDG paths outside the repo.
- `replyguy` does not post anywhere. It only turns raw inputs into reply suggestions the user can copy-paste manually.

## Product Rules
- `replyguy rant` opens the live rant file in `$VISUAL`, then `$EDITOR`, then `vim`. Exiting the editor processes the file and writes reply suggestions.
- `replyguy muse` opens the latest muse output file, then clears the live file after the editor closes.
- `replyguy` must archive the consumed rant before clearing it.
- Clear the live rant only after the muse file write succeeds.
- If processing fails before the output is committed, leave the live rant intact.
- `replyguy` suggests replies, but the user posts them manually.

## Content Rules
- Keep the writing direct, technically grounded, and anti-sludge.
- Use the user's pasted ideas and the linked post text as the primary material.
- Favor thoughtful, specific, non-cringe replies over generic applause or engagement bait.
- The reply should meet or exceed the literary quality of the source post.
- If the post is elegant, the reply cannot be flatter, duller, or more generic than the post itself.

## Implementation Rules
- Keep the help path import-light and side-effect free.
- Keep HTTP logic out of CLI parsing; use small dedicated client modules.
- Prefer plain JSON config and flat files over heavier local infrastructure.
- Notifications should go through `notify-send` so Mako can display them.
