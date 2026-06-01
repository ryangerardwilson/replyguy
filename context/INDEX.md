# replyguy Context Index

Project: replyguy
Context version: 1

## Identity

`replyguy` is a terminal-native reply drafting tool for bookmarked X posts.
It prepares reply options, lets Ryan review them locally, opens the source
post, copies the chosen reply, and leaves final posting manual.

## Load Order

Always start with:

- `/home/ryan/AGENTS.md`
- root CEO behavior from `/home/ryan/Subagents/ceo/`
- this file

Then load only the smallest context set needed for the task.

## Role Map

CMO/reply voice and quality:

- `context/copy/REPLY_GUY_GUIDELINES.md`

CTO/implementation:

- `AGENTS.md`
- `README.md`
- `replyguy/`
- `tests/`

CFO/cost:

- `context/operations/COST.md`

## Conflict Policy

replyguy project facts and reply voice live in this project, not in root CMO.

If a needed replyguy fact is missing, report the missing context instead of
borrowing Ryan personal-site brand, Wiom, ADE, Ooolala, or another project's
context.

## Update Policy

Durable reply voice, taste, rhetorical moves, and reply-quality standards
belong in `context/copy/REPLY_GUY_GUIDELINES.md`. Keep app-internal prompts
neutral and operational.
