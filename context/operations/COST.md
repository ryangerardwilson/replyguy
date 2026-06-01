# replyguy Cost Context

## Purpose

This file owns cost-sensitive context for `replyguy`.

## Current Cost Shape

- `replyguy` uses the local `codex` CLI for reply generation.
- Generation cost depends on the configured Codex subscription/model behavior,
  not on infrastructure owned by this repo.
- The default config currently uses a high-reasoning model setting for quality.
- `replyguy timer install` can run an hourly user-level systemd timer that
  inhales bookmarked posts in the background.
- Runtime state is local XDG state/config/cache, not hosted infrastructure.

## Rules

- Do not add hosted infrastructure, queues, databases, paid APIs, or external
  workers without explicit user approval.
- Treat higher model/reasoning settings and hourly background runs as spend and
  quota surfaces.
- Before increasing generation frequency, model tier, reply count, or
  background automation, name the likely cost/quota impact.
- Keep the default app prompt neutral and keep user-specific voice in project
  context, so another user can lower cost or swap guidelines without changing
  code.
- If exact Codex billing/subscription limits are needed, report the missing
  billing context instead of guessing.
