"""بوت لوردس موبايل: عند كل دخول جديد -> يغلق النوافذ -> يصغّر القلعة للحد الأقصى -> يحدد المباني.

التشغيل:
    python bot.py            # تشغيل واحد (يفتح اللعبة إن لم تكن مفتوحة)
    python bot.py --watch    # مراقبة: يعيد العملية تلقائياً عند كل دخول جديد للعبة
    python bot.py --no-launch  # لا يفتح اللعبة، يفترض أنها مفتوحة
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
        log(f"إغلاق نافذة منبثقة ({i + 1}) عند {pos}")
        dev.tap(*pos)
        dev.wait(1.0)


def zoom_out_max(dev):
    """يكرر القرص حتى تتوقف الصورة عن التغيّر (أقصى تصغير)."""
    prev = dev.screenshot()
    stable = 0
    for i in range(config.MAX_ZOOM_ITER):
        dev.pinch_in()
        dev.wait(config.ZOOM_SETTLE)
        cur = dev.screenshot()
        d = frame_diff(prev, cur)
        log(f"تصغير #{i + 1}: فرق={d:.2f}")
        if d < config.ZOOM_DIFF_THRESHOLD:
            stable += 1
            if stable >= config.ZOOM_STABLE_COUNT:
                log("وصل إلى أقصى تصغير")
                return cur
        else:
            stable = 0
        prev = cur
    log("تحذير: انتهت المحاولات دون استقرار كامل")
    return prev


def run_once(dev, launch=True):
    buildings_tpl, ui_tpl = load_templates()
    if not buildings_tpl:
        log(f"تنبيه: لا توجد قوالب في {config.TEMPLATES_DIR}/ - شغّل capture_templates.py أولاً")

    if launch and not dev.is_foreground():
        log("فتح اللعبة...")
        dev.launch()
    log(f"انتظار التحميل {config.LOAD_WAIT}ث")
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

    log(f"تم تحديد {len(found)} مبنى؛ غير موجود: {missing or 'لا شيء'}")
    return result


def watch(dev):
    was_fg = False
    log("وضع المراقبة يعمل. Ctrl+C للإيقاف.")
    while True:
        try:
            fg = dev.is_foreground()
            if fg and not was_fg:
                log("دخول جديد للعبة")
                run_once(dev, launch=False)
            was_fg = dev.is_foreground()
        except KeyboardInterrupt:
            raise
        except Exception as e:  # noqa: BLE001
            log(f"خطأ: {e}")
        time.sleep(config.WATCH_POLL)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--no-launch", action="store_true")
    ap.add_argument("--serial")
    args = ap.parse_args()

    dev = Device(args.serial)
    log(f"الشاشة: {dev.size()}")
    try:
        if args.watch:
            watch(dev)
        else:
            run_once(dev, launch=not args.no_launch)
    except KeyboardInterrupt:
        log("تم الإيقاف")


if __name__ == "__main__":
    main()
