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
from util import log, record_round
from vision import annotate, detect_buildings, find_ui, frame_diff, load_templates


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


def run_tasks(dev, names, loop, launch=True, resource=None, level=None):
    from tasks import Runner, missing_templates
    import flows
    bad = [n for n in names if n not in flows.TASKS]
    if bad:
        raise SystemExit(f"مهمة مجهولة: {bad} (المتاح: {list(flows.TASKS)})")
    if level and level not in range(1, 6):
        raise SystemExit("--level يجب أن يكون بين 1 و5")
    if resource and resource not in flows.RESOURCES:
        raise SystemExit(f"مورد مجهول: {resource} (المتاح: {list(flows.RESOURCES)})")
    lacking = {k: v for k, v in missing_templates(names, resource, level=level).items() if v}
    if lacking:
        log(f"warning: missing templates: {lacking}  (شغّل --check للتفاصيل)")

    def start_game():
        log("launching the game...")
        dev.launch()
        dev.wait(config.LOAD_WAIT)

    if launch and not dev.is_foreground():
        start_game()
    runner = Runner(dev, resource, level)
    idle = 0
    while True:
        if not dev.is_foreground():
            if launch and config.AUTO_RELAUNCH and loop:
                log("game not in foreground -> relaunch")
                start_game()
            else:
                log("game not in foreground - waiting")
        else:
            try:
                runner.dismiss_popups()
                res = runner.run_all(names)
            except Exception as e:  # noqa: BLE001
                log(f"round error: {e}")
                res = {n: 0 for n in names}
            st = record_round(res)
            log(f"round: {res} | total: {st['marches']}")
            idle = 0 if runner.all_blocked(names) else (idle + 1 if sum(res.values()) == 0 else 0)
            if loop and launch and config.AUTO_RELAUNCH and idle >= config.RESTART_AFTER_IDLE_ROUNDS:
                log(f"{idle} idle rounds -> restart the game")
                dev.stop()
                dev.wait(2)
                start_game()
                idle = 0
        if not loop:
            return
        time.sleep(config.LOOP_PAUSE)


def check(names, resource=None, level=None):
    """يفحص القوالب الناقصة لكل مهمة بدون لمس الجهاز."""
    from tasks import missing_templates
    import flows
    names = names or list(flows.TASKS)
    bad = [n for n in names if n not in flows.TASKS]
    if bad:
        raise SystemExit(f"مهمة مجهولة: {bad}")
    ok = True
    for n, need in missing_templates(names, resource, level=level).items():
        if need:
            ok = False
            print(f"{n}: ناقص -> " + ", ".join(f"_{x}" for x in need))
        else:
            print(f"{n}: كل القوالب موجودة")
    raise SystemExit(0 if ok else 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--no-launch", action="store_true")
    ap.add_argument("--serial")
    ap.add_argument("--task", help="مهام للتنفيذ مفصولة بفاصلة: gather,hunt")
    ap.add_argument("--loop", action="store_true", help="كرّر المهام كل config.LOOP_PAUSE ثانية")
    ap.add_argument("--resource", help="مورد الجمع: ore|wood|food|stone|gold")
    ap.add_argument("--level", type=int, help="جمع من منطقة المستوى N (1-5) عبر مخطط المناطق مع السحب للبحث")
    ap.add_argument("--check", action="store_true", help="يعرض القوالب الناقصة للمهام ويخرج")
    args = ap.parse_args()

    if args.check:
        check([t.strip() for t in (args.task or "").split(",") if t.strip()], args.resource, args.level)

    dev = Device(args.serial)
    log(f"backend={config.BACKEND} screen={dev.size()}")
    try:
        if args.task:
            run_tasks(dev, [t.strip() for t in args.task.split(",") if t.strip()], args.loop,
                      launch=not args.no_launch, resource=args.resource, level=args.level)
        elif args.watch:
            watch(dev)
        else:
            run_once(dev, launch=not args.no_launch)
    except KeyboardInterrupt:
        log("stopped")


if __name__ == "__main__":
    main()
