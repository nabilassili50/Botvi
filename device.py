import re
import subprocess
import time

import cv2
import numpy as np

import config

# ثوابت evdev (أرقام عشرية لأن sendevent يقبلها)
EV_SYN, EV_KEY, EV_ABS = 0, 1, 3
BTN_TOUCH = 330
ABS_MT_SLOT = 47
ABS_MT_TOUCH_MAJOR = 48
ABS_MT_POSITION_X = 53
ABS_MT_POSITION_Y = 54
ABS_MT_TRACKING_ID = 57
ABS_MT_PRESSURE = 58


class Device:
    def __init__(self, serial=None):
        self.serial = serial or config.SERIAL
        self._u2 = None
        self._touch = None

    # ---------- ADB ----------
    def _adb(self, *args, binary=False, timeout=30):
        cmd = ["adb"] + (["-s", self.serial] if self.serial else []) + list(args)
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        if r.returncode != 0:
            raise RuntimeError(f"adb failed: {' '.join(cmd[:6])}...\n{r.stderr.decode(errors='ignore')}")
        return r.stdout if binary else r.stdout.decode(errors="ignore")

    def screenshot(self):
        data = self._adb("exec-out", "screencap", "-p", binary=True)
        img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise RuntimeError("تعذر قراءة لقطة الشاشة")
        return img

    def size(self):
        out = self._adb("shell", "wm", "size")
        m = re.findall(r"(\d+)x(\d+)", out)
        w, h = map(int, m[-1])
        return w, h

    def tap(self, x, y):
        self._adb("shell", "input", "tap", str(int(x)), str(int(y)))

    def launch(self, package=None):
        pkg = package or config.PACKAGE
        self._adb("shell", "monkey", "-p", pkg, "-c", "android.intent.category.LAUNCHER", "1")

    def is_foreground(self, package=None):
        pkg = package or config.PACKAGE
        out = self._adb("shell", "dumpsys", "window")
        for line in out.splitlines():
            if "mCurrentFocus" in line:
                return pkg in line
        return False

    # ---------- القرص عبر sendevent (يعمل على Termux/الجهاز مباشرة بدون وكيل) ----------
    def _touch_info(self):
        """يكتشف جهاز اللمس ونطاق إحداثياته من getevent."""
        if self._touch:
            return self._touch
        out = self._adb("shell", "getevent", "-pl")
        best = None
        for block in re.split(r"(?m)^add device \d+:\s*", out)[1:]:
            path = block.split("\n", 1)[0].strip()
            mx = re.search(r"ABS_MT_POSITION_X\s*:.*?min\s+(-?\d+),\s*max\s+(\d+)", block)
            my = re.search(r"ABS_MT_POSITION_Y\s*:.*?min\s+(-?\d+),\s*max\s+(\d+)", block)
            if not (mx and my and "ABS_MT_SLOT" in block):
                continue
            info = {
                "path": path,
                "xmin": int(mx.group(1)), "xmax": int(mx.group(2)),
                "ymin": int(my.group(1)), "ymax": int(my.group(2)),
                "pressure": "ABS_MT_PRESSURE" in block,
                "major": "ABS_MT_TOUCH_MAJOR" in block,
            }
            if "INPUT_PROP_DIRECT" in block:
                best = info
                break
            best = best or info
        if not best:
            raise RuntimeError("لم أجد شاشة لمس متعددة النقاط في getevent")
        self._touch = best
        return best

    def _pinch_script(self):
        t = self._touch_info()
        ev = t["path"]
        cx = (t["xmin"] + t["xmax"]) // 2
        cy = (t["ymin"] + t["ymax"]) // 2
        span = t["ymax"] - t["ymin"]
        d0 = min(int(span * 0.30 * config.PINCH_PERCENT / 80), span // 2 - 10)
        d1 = int(span * 0.04)
        steps = max(8, min(config.PINCH_STEPS, 20))
        s = []

        def e(typ, code, val):
            s.append(f"sendevent {ev} {typ} {code} {val}")

        def contact_extras():
            if t["pressure"]:
                e(EV_ABS, ABS_MT_PRESSURE, 50)
            if t["major"]:
                e(EV_ABS, ABS_MT_TOUCH_MAJOR, 8)

        # لمس الإصبعين
        for slot, tid, y in ((0, 100, cy - d0), (1, 101, cy + d0)):
            e(EV_ABS, ABS_MT_SLOT, slot)
            e(EV_ABS, ABS_MT_TRACKING_ID, tid)
            e(EV_ABS, ABS_MT_POSITION_X, cx)
            e(EV_ABS, ABS_MT_POSITION_Y, y)
            contact_extras()
        e(EV_KEY, BTN_TOUCH, 1)
        e(EV_SYN, 0, 0)

        # تحريك الإصبعين نحو المركز
        for i in range(1, steps + 1):
            d = int(d0 + (d1 - d0) * i / steps)
            e(EV_ABS, ABS_MT_SLOT, 0)
            e(EV_ABS, ABS_MT_POSITION_Y, cy - d)
            e(EV_ABS, ABS_MT_SLOT, 1)
            e(EV_ABS, ABS_MT_POSITION_Y, cy + d)
            e(EV_SYN, 0, 0)

        # رفع الإصبعين
        for slot in (0, 1):
            e(EV_ABS, ABS_MT_SLOT, slot)
            e(EV_ABS, ABS_MT_TRACKING_ID, -1)
        e(EV_KEY, BTN_TOUCH, 0)
        e(EV_SYN, 0, 0)
        return "; ".join(s)

    def _pinch_sendevent(self):
        self._adb("shell", self._pinch_script(), timeout=90)

    # ---------- القرص عبر uiautomator2 (للحاسوب) ----------
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
        raise RuntimeError(f"فشل القرص عبر u2: {last}")

    def pinch_in(self):
        """قرص للداخل = تصغير الخريطة. الواجهة الخلفية من config.PINCH_BACKEND."""
        backend = config.PINCH_BACKEND
        if backend == "sendevent":
            return self._pinch_sendevent()
        if backend == "u2":
            return self._pinch_u2()
        try:  # auto
            return self._pinch_sendevent()
        except Exception as e:  # noqa: BLE001
            print(f"sendevent فشل ({e}); أجرّب uiautomator2", flush=True)
            return self._pinch_u2()

    def wait(self, seconds):
        time.sleep(seconds)
