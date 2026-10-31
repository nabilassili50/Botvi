"""Lords Mobile bot: on every fresh entry -> close popups -> zoom out to the max -> detect buildings.

    python bot.py              # one run (launches the game if it is not open)
    python bot.py --watch      # watch mode: re-run automatically on every new entry to the game
    python bot.py --no-launch  # do not launch the game, assume it is already open
"""
import argparse
import json
import os
import time
from datetime import datetime

import cv2

import config
from device import Device
from vision import annotate, detect_buildings, find_ui, frame_diff, load_templates


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def close_popups(dev, ui):
    if not any(n.lstrip("_").startswith("close") for n in ui):
        return
    for i in range(config.CLOSE_POPUP_ATTEMPTS):
        pos = find_ui(dev.screenshot(), ui, "close")
        if not pos:
            break
        log(f"closing popup ({i + 1}) at {pos}")
        dev.tap(*pos)
        dev.wait(1.0)


def zoom_out_max(dev):
    """Pinch repeatedly until the screen stops changing (maximum zoom-out)."""
    prev = dev.screenshot()
    stable = 0
    for i in range(config.MAX_ZOOM_ITER):
        dev.pinch_in()
        dev.wait(config.ZOOM_SETTLE)
        cur = dev.screenshot()
        d = frame_diff(prev, cur)
        log(f"zoom #{i + 1}: diff={d:.2f}")
        if d < config.ZOOM_DIFF_THRESHOLD:
            stable += 1
            if stable >= config.ZOOM_STABLE_COUNT:
                log("max zoom-out reached")
                return cur
        else:
            stable = 0
        prev = cur
    log("warning: ran out of attempts before the view became stable")
    return prev


def run_once(dev, launch=True):
    buildings_tpl, ui_tpl = load_templates()
    if not buildings_tpl:
        log(f"warning: no templates in {config.TEMPLATES_DIR}/ - run capture_templates.py first")

    if launch and not dev.is_foreground():
        log("launching the game...")
        dev.launch()
    log(f"waiting {config.LOAD_WAIT}s for the game to load")
    dev.wait(config.LOAD_WAIT)

    close_popups(dev, ui_tpl)
    img = zoom_out_max(dev)

    found = detect_buildings(img, buildings_tpl)
    names = set(b["name"] for b in found)
    missing = sorted(set(buildings_tpl) - names)

    h, w = img.shape[:2]
    result = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "resolution": [w, h],
        "buildings": found,
        "missing": missing,
    }

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    with open(os.path.join(config.OUTPUT_DIR, f"{stamp}.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    with open(os.path.join(config.OUTPUT_DIR, "latest.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    cv2.imwrite(os.path.join(config.OUTPUT_DIR, f"{stamp}.png"), annotate(img, found))

    log(f"detected {len(found)} buildings; missing: {missing or 'none'}")
    return result


def watch(dev):
    was_fg = False
    log("watch mode running. Ctrl+C to stop.")
    while True:
        try:
            fg = dev.is_foreground()
            if fg and not was_fg:
                log("new entry to the game")
                run_once(dev, launch=False)
            was_fg = fg
        except KeyboardInterrupt:
            raise
        except Exception as e:  # noqa: BLE001
            log(f"error: {e}")
        time.sleep(config.WATCH_POLL)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--no-launch", action="store_true")
    ap.add_argument("--serial")
    args = ap.parse_args()

    dev = Device(args.serial)
    log(f"backend={config.BACKEND} screen={dev.size()}")
    try:
        if args.watch:
            watch(dev)
        else:
            run_once(dev, launch=not args.no_launch)
    except KeyboardInterrupt:
        log("stopped")


if __name__ == "__main__":
    main()
