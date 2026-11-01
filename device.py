import os
import re
import subprocess
import time

import cv2
import numpy as np

import config

# evdev constants (decimal, as accepted by sendevent)
EV_SYN, EV_KEY, EV_ABS = 0, 1, 3
BTN_TOUCH = 330
ABS_MT_SLOT = 47
ABS_MT_TOUCH_MAJOR = 48
ABS_MT_POSITION_X = 53
ABS_MT_POSITION_Y = 54
ABS_MT_TRACKING_ID = 57
ABS_MT_PRESSURE = 58
ABS_MT_WIDTH_MAJOR = 50
SYN_MT_REPORT = 2

SHARED_SHOT = ".lords_shot.png"
SHARED_OUT = ".lords_out.txt"


class Device:
    """Runs shell commands on the phone through adb (PC / adb pair) or rish (Termux + Shizuku)."""

    def __init__(self, serial=None):
        self.serial = serial or config.SERIAL
        self._u2 = None
        self._touch = None

    # ---------- shell backend ----------
    def _sh(self, cmd, binary=False, timeout=30, expect=False):
        if config.BACKEND == "rish":
            full = ["rish", "-c", cmd]
        else:
            full = ["adb"] + (["-s", self.serial] if self.serial else []) + \
                   ["exec-out" if binary else "shell", cmd]
        # rish أحياناً يرجّع مخرجاً فارغاً (خاصة لو stdin طرفية): نمنع stdin ونعيد المحاولة
        if expect and not binary and config.BACKEND == "rish":
            for _ in range(3):
                out = self._sh_file(cmd, timeout=timeout)
                if out.strip():
                    return out
                time.sleep(0.6)
        tries = 4 if (expect and not binary) else 1
        for i in range(tries):
            try:
                r = subprocess.run(full, capture_output=True, timeout=timeout,
                                   stdin=subprocess.DEVNULL)
            except FileNotFoundError:
                raise RuntimeError(f"'{full[0]}' not found. See README (Termux / Shizuku).")
            if r.returncode != 0:
                raise RuntimeError(f"{full[0]} failed: {cmd[:60]}\n{r.stderr.decode(errors='ignore')}")
            if binary:
                return r.stdout
            out = r.stdout.decode(errors="ignore")
            if out.strip() or not expect:
                return out
            time.sleep(0.6)
        return out

    def _sh_file(self, cmd, timeout=30):
        """rish: نكتب المخرج في /sdcard ونقرأه من Termux (أوثق من الأنبوب الذي يضيع/يتشوّه)."""
        self._sh(f"{cmd} > /sdcard/{SHARED_OUT} 2>&1", timeout=timeout)
        path = os.path.expanduser(f"~/storage/shared/{SHARED_OUT}")
        try:
            with open(path, errors="ignore") as f:
                return f.read()
        except OSError:
            return ""

    @staticmethod
    def _decode(data):
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if img is None and b"\r\n" in data:      # pty-style CRLF mangling
            img = cv2.imdecode(np.frombuffer(data.replace(b"\r\n", b"\n"), np.uint8),
                               cv2.IMREAD_COLOR)
        return img

    def screenshot(self):
        img = None
        if config.BACKEND != "rish":
            img = self._decode(self._sh("screencap -p", binary=True))
        if img is None and config.BACKEND == "rish":
            # fallback: write to shared storage and read it from Termux
            self._sh(f"screencap -p /sdcard/{SHARED_SHOT}")
            path = os.path.expanduser(f"~/storage/shared/{SHARED_SHOT}")
            with open(path, "rb") as f:
                img = self._decode(f.read())
        if img is None:
            raise RuntimeError("Could not decode screenshot")
        return img

    def size(self):
        try:
            out = self._sh("wm size 2>&1", expect=True)
            m = re.findall(r"(\d+)x(\d+)", out)
            if m:
                return tuple(map(int, m[-1]))
        except Exception:  # noqa: BLE001
            pass
        h, w = self.screenshot().shape[:2]
        return w, h

    def tap(self, x, y):
        self._sh(f"input tap {int(x)} {int(y)}")

    def swipe(self, x1, y1, x2, y2, ms=400):
        self._sh(f"input swipe {int(x1)} {int(y1)} {int(x2)} {int(y2)} {int(ms)}")

    def back(self):
        self._sh("input keyevent 4")

    def launch(self, package=None):
        pkg = package or config.PACKAGE
        self._sh(f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1")

    def stop(self, package=None):
        self._sh(f"am force-stop {package or config.PACKAGE}")

    def is_foreground(self, package=None):
        pkg = package or config.PACKAGE
        out = self._sh("dumpsys window | grep mCurrentFocus", expect=True)
        for line in out.splitlines():
            if "mCurrentFocus" in line:
                return pkg in line
        return False

    # ---------- pinch via sendevent (no helper app needed) ----------
    def _touch_info(self):
        """Find the touch device and its coordinate range from getevent."""
        if self._touch:
            return self._touch
        out = self._sh("getevent -pl 2>&1", expect=True)
        if "ABS_MT_POSITION_X" not in out:
            cache = os.path.expanduser("~/ev.txt")      # rish -c "getevent -pl" > ~/ev.txt
            if os.path.exists(cache):
                out = open(cache, errors="ignore").read()
        best = None
        for block in re.split(r"(?m)^add device \d+:\s*", out)[1:]:
            path = block.split("\n", 1)[0].strip()
            mx = re.search(r"ABS_MT_POSITION_X\s*:.*?min\s+(-?\d+),\s*max\s+(\d+)", block)
            my = re.search(r"ABS_MT_POSITION_Y\s*:.*?min\s+(-?\d+),\s*max\s+(\d+)", block)
            if not (mx and my):
                continue
            info = {
                "path": path,
                "xmin": int(mx.group(1)), "xmax": int(mx.group(2)),
                "ymin": int(my.group(1)), "ymax": int(my.group(2)),
                "slot": "ABS_MT_SLOT" in block,          # بروتوكول B (وإلا A: لمس قديم بدون slots)
                "tid": "ABS_MT_TRACKING_ID" in block,
                "width": "ABS_MT_WIDTH_MAJOR" in block,
                "pressure": "ABS_MT_PRESSURE" in block,
                "major": "ABS_MT_TOUCH_MAJOR" in block,
            }
            if "INPUT_PROP_DIRECT" in block:
                best = info
                break
            best = best or info
        if not best:
            raise RuntimeError("No multi-touch screen found in getevent output")
        self._touch = best
        return best

    def _pinch_script(self, inward=True):
        t = self._touch_info()
        ev = t["path"]
        cx = (t["xmin"] + t["xmax"]) // 2
        cy = (t["ymin"] + t["ymax"]) // 2
        span = t["ymax"] - t["ymin"]
        d0 = min(int(span * 0.30 * config.PINCH_PERCENT / 80), span // 2 - 10)
        d1 = int(span * 0.04)
        if not inward:                      # قرص للخارج = تكبير (للاختبار)
            d0, d1 = d1, d0
        steps = max(8, min(config.PINCH_STEPS, 20))
        s = []

        def e(typ, code, val):
            s.append(f"sendevent {ev} {typ} {code} {val}")

        def extras():
            if t["pressure"]:
                e(EV_ABS, ABS_MT_PRESSURE, 50)
            if t["major"]:
                e(EV_ABS, ABS_MT_TOUCH_MAJOR, 8)
            if t["width"]:
                e(EV_ABS, ABS_MT_WIDTH_MAJOR, 8)

        if t["slot"]:
            # ---- بروتوكول B ----
            for slot, tid, y in ((0, 100, cy - d0), (1, 101, cy + d0)):
                e(EV_ABS, ABS_MT_SLOT, slot)
                e(EV_ABS, ABS_MT_TRACKING_ID, tid)
                e(EV_ABS, ABS_MT_POSITION_X, cx)
                e(EV_ABS, ABS_MT_POSITION_Y, y)
                extras()
            e(EV_KEY, BTN_TOUCH, 1)
            e(EV_SYN, 0, 0)
            for i in range(1, steps + 1):
                d = int(d0 + (d1 - d0) * i / steps)
                e(EV_ABS, ABS_MT_SLOT, 0)
                e(EV_ABS, ABS_MT_POSITION_Y, cy - d)
                e(EV_ABS, ABS_MT_SLOT, 1)
                e(EV_ABS, ABS_MT_POSITION_Y, cy + d)
                e(EV_SYN, 0, 0)
            for slot in (0, 1):
                e(EV_ABS, ABS_MT_SLOT, slot)
                e(EV_ABS, ABS_MT_TRACKING_ID, -1)
            e(EV_KEY, BTN_TOUCH, 0)
            e(EV_SYN, 0, 0)
        else:
            # ---- بروتوكول A: كل إطار يعيد كل نقاط اللمس ثم SYN_REPORT ----
            def frame(d, first=False):
                for tid, y in ((0, cy - d), (1, cy + d)):
                    if t["tid"]:
                        e(EV_ABS, ABS_MT_TRACKING_ID, tid)
                    e(EV_ABS, ABS_MT_POSITION_X, cx)
                    e(EV_ABS, ABS_MT_POSITION_Y, y)
                    extras()
                    e(EV_SYN, SYN_MT_REPORT, 0)
                if first:
                    e(EV_KEY, BTN_TOUCH, 1)
                e(EV_SYN, 0, 0)
                s.append("sleep 0.02")

            frame(d0, first=True)
            for i in range(1, steps + 1):
                frame(int(d0 + (d1 - d0) * i / steps))
            e(EV_SYN, SYN_MT_REPORT, 0)       # رفع الإصبعين: إطار فارغ
            e(EV_SYN, 0, 0)
            e(EV_KEY, BTN_TOUCH, 0)
            e(EV_SYN, 0, 0)
        return "; ".join(s)

    def _pinch_sendevent(self, inward=True):
        self._sh(self._pinch_script(inward), timeout=120)

    def pinch_out(self):
        """قرص للخارج (تكبير) - للتشخيص فقط."""
        return self._pinch_sendevent(inward=False)

    # ---------- pinch via uiautomator2 (PC + adb only) ----------
    @property
    def u2(self):
        if self._u2 is None:
            import uiautomator2 as u2
            self._u2 = u2.connect(self.serial) if self.serial else u2.connect()
        return self._u2

    def _pinch_u2(self):
        last = None
        for selector in ({"className": "android.widget.FrameLayout"},
                         {"resourceId": "android:id/content"}):
            try:
                self.u2(**selector).pinch_in(percent=config.PINCH_PERCENT,
                                             steps=config.PINCH_STEPS)
                return
            except Exception as e:  # noqa: BLE001
                last = e
        raise RuntimeError(f"u2 pinch failed: {last}")

    def pinch_in(self):
        """Pinch inwards = zoom the map out. Backend from config.PINCH_BACKEND."""
        backend = config.PINCH_BACKEND
        if backend == "sendevent" or config.BACKEND == "rish":
            return self._pinch_sendevent()
        if backend == "u2":
            return self._pinch_u2()
        try:  # auto
            return self._pinch_sendevent()
        except Exception as e:  # noqa: BLE001
            print(f"sendevent failed ({e}); trying uiautomator2", flush=True)
            return self._pinch_u2()

    def wait(self, seconds):
        time.sleep(seconds)
