from __future__ import annotations

import shutil
import subprocess
from typing import Any

from .bookmark_queue import load_queue, next_pending_item, remove_completed_items, replace_item, save_queue
from .config import load_config
from .editor import edit_text
from .errors import ReplyGuyError
from .x_bridge import remove_bookmark, remove_bookmark_background

REPLY_START = "<!-- reply-start -->"
REPLY_END = "<!-- reply-end -->"


def _print_item(item: dict[str, Any]) -> None:
    print("")
    print("-------------------------------------")
    print("")
    print(f"@{item.get('author_username') or '-'}")
    print(str(item.get("url") or "-"))
    print("")
    print(str(item.get("text") or "").strip() or "-")
    print("")
    options = item.get("reply_options") or []
    if options:
        for index, option in enumerate(options, start=1):
            print(f"{index}. {option}")
        why = str(item.get("why_it_works") or "").strip()
        if why:
            print("")
            print(f"why: {why}")
    else:
        reason = item.get("generation_error") or item.get("skip_reason") or "no prepared replies"
        print(reason)
    print("")


def _cleanup_posted_items(queue: dict[str, Any], config: dict[str, Any]) -> None:
    changed = False
    for item in list(queue.get("items") or []):
        if not isinstance(item, dict):
            continue
        if str(item.get("status") or "") != "posted":
            continue
        if item.get("bookmark_removed"):
            item["status"] = "done"
            changed = True
            continue
        try:
            remove_bookmark(config, str(item.get("tweet_id") or ""))
        except ReplyGuyError:
            continue
        item["bookmark_removed"] = True
        item["status"] = "done"
        changed = True
    if changed:
        remove_completed_items(queue)
        save_queue(queue)


def _defer_item(queue: dict[str, Any], current_item: dict[str, Any]) -> None:
    items = [item for item in queue.get("items") or [] if isinstance(item, dict)]
    tweet_id = str(current_item.get("tweet_id") or "")
    target_index = None
    for index, item in enumerate(items):
        if str(item.get("tweet_id") or "") == tweet_id:
            target_index = index
            break
    if target_index is None:
        return
    item = items.pop(target_index)
    items.append(item)
    queue["items"] = items
    save_queue(queue)


def _edit_buffer(item: dict[str, Any], selected_reply: str) -> str:
    return (
        "# replyguy exhale\n\n"
        "Edit only the text between the reply markers.\n"
        "Everything else is context and will be ignored when posting.\n\n"
        "## post\n"
        f"- author: @{item.get('author_username') or '-'}\n"
        f"- url: {item.get('url') or '-'}\n\n"
        f"{str(item.get('text') or '').strip() or '-'}\n\n"
        "## reply\n"
        f"{REPLY_START}\n"
        f"{selected_reply.strip()}\n"
        f"{REPLY_END}\n"
    )


def _extract_reply(edited: str) -> str:
    start = edited.find(REPLY_START)
    end = edited.find(REPLY_END)
    if start == -1 or end == -1 or end < start:
        return ""
    body = edited[start + len(REPLY_START):end]
    return body.strip()


def _open_in_chrome(url: str) -> None:
    browser = shutil.which("google-chrome-stable")
    if not browser:
        raise ReplyGuyError("missing dependency: google-chrome-stable")
    subprocess.Popen(
        [browser, "--new-tab", url],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def _copy_to_clipboard(text: str) -> None:
    wl_copy = shutil.which("wl-copy")
    if not wl_copy:
        raise ReplyGuyError("missing dependency: wl-copy")
    process = subprocess.Popen(
        [wl_copy],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        start_new_session=True,
    )
    assert process.stdin is not None
    process.stdin.write(text)
    process.stdin.close()


def run_muse_session() -> int:
    config = load_config()
    queue = load_queue()
    _cleanup_posted_items(queue, config)
    queue = load_queue()

    while True:
        item = next_pending_item(queue)
        if item is None:
            print("Nothing is queued for exhale. Run `replyguy inhale` first.")
            return 0

        _print_item(item)
        options = item.get("reply_options") or []
        if options:
            prompt = f"choose 1-{len(options)}, d remove bookmark, s skip, q quit: "
        else:
            prompt = "d remove bookmark, s skip, q quit: "
        answer = input(prompt).strip().lower()

        if answer == "q":
            return 0
        if answer == "s":
            _defer_item(queue, item)
            continue
        if answer == "d":
            remove_bookmark(config, str(item.get("tweet_id") or ""))
            item["bookmark_removed"] = True
            item["status"] = "done"
            replace_item(queue, item)
            remove_completed_items(queue)
            save_queue(queue)
            continue
        if not options:
            print("No prepared reply options for this bookmark.")
            continue
        if not answer.isdigit():
            print("Enter a reply number, `d`, `s`, or `q`.")
            continue

        index = int(answer) - 1
        if index < 0 or index >= len(options):
            print("Invalid reply number.")
            continue

        edited = edit_text(_edit_buffer(item, options[index]), suffix=".md")
        if edited is None:
            print("Editor exited with an error.")
            continue
        edited_reply = _extract_reply(edited)
        if not edited_reply:
            print("Reply was empty; nothing posted.")
            continue

        try:
            _open_in_chrome(str(item.get("url") or ""))
            _copy_to_clipboard(edited_reply)
        except ReplyGuyError as exc:
            item["post_error"] = str(exc)
            replace_item(queue, item)
            save_queue(queue)
            print(f"post failed: {exc}")
            continue
        item["selected_reply"] = edited_reply
        item["post_error"] = ""
        item["bookmark_removed"] = True
        item["status"] = "done"
        replace_item(queue, item)
        remove_completed_items(queue)
        save_queue(queue)
        remove_bookmark_background(config, str(item.get("tweet_id") or ""))
        print(f"opened in chrome and copied to clipboard: {item.get('url') or '-'}")
