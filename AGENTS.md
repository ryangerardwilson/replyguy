# replyguy Agent Guide

## Scope
- `replyguy` is a terminal-native reply drafting tool for bookmarked X posts.
- The product is keyboard-first, explicit, local-first, and inspectable. It is not a web dashboard.
- Public repo, private runtime state: keep `muse`, archives, and config in XDG paths outside the repo.
- `replyguy` owns reply choice and review; the final send is manual through the browser with clipboard help.

## Product Rules
- `replyguy inhale` fetches bookmarked X posts through the `x` app and prepares replies in the background.
- `replyguy exhale` walks the prepared bookmarked-post queue in the terminal, lets the user choose and edit a reply, opens the post in Google Chrome Stable, copies the reply to the clipboard with `wl-copy`, and removes the bookmark.
- `replyguy status` reports whether inhale is currently running plus the queue state from local files.

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
