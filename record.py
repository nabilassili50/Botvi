"""تسجيل تلقائي: نفّذ المهمة بيدك مرة واحدة داخل اللعبة والبوت يحوّلها إلى مهمة.

    python bot.py --record اسم_المهمة [--rec-start city|world|any] [--rec-zoom] [--rec-every ثوانٍ]

كيف يعمل:
  1) يقرأ لمسات الشاشة الحقيقية بـ getevent (عبر Shizuku/adb) ويحوّلها لإحداثيات الشاشة.
  2) يلتقط لقطات خلفية متتالية؛ لكل ضغطة يقصّ قالباً (96x96 حول نقطة اللمس) من لقطة ما قبل الضغطة.
  3) عند الانتهاء يحفظ القوالب في templates/_<اسم>_sNN/ ويكتب الخطوات في recorded_flows.json.
  4) شغّل المهمة بعدها: python bot.py --task اسم_المهمة

الإيقاف: Ctrl+C في Termux، أو اسحب من حافة الشاشة السفلية (إيماءة الرئيسية)، أو --rec-seconds.
نصيحة: انتظر نحو ثانيتين بين كل ضغطة وأخرى كي تُلتقط لقطة نظيفة لكل ضغطة.
"""
import json
import os
import re
import shutil
import threading
import time
from datetime import datetime

import cv2

import config
import flows
from util import log

REC_FILE = ".lords_rec.txt"
LINE = re.compile(r"\[\s*(\d+\.\d+)\]\s*(?:\S+:\s*)?([0-9a-fA-F]{4})\s+([0-9a-fA-F]{4})\s+([0-9a-fA-F]{8})")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,30}$")

TAP_MAX_PX = 35            # أقصى حركة لتعدّ ضغطة
LONG_PRESS_S = 0.7         # أطول من هذا بلا حركة = ضغطة مطوّلة
EDGE_STOP = 0.975          # بداية اللمسة تحت هذه النسبة من الارتفاع = إيماءة الرئيسية = إيقاف
FAST_GAP_S = 1.2           # ضغطة بعد أقل من هذا من سابقتها: لقطتها قد تكون قديمة فلا نقصّ لها قالباً
MIN_HALF, MAX_HALF = 22, 48
MIN_TEXTURE = 14.0         # أدنى تباين (انحراف معياري) ليصلح القص كقالب


def to_screen(u, v, rot):
    """من إحداثيات اللمس المطبّعة (0-1) إلى إحداثيات الشاشة المطبّعة حسب دوران الشاشة."""
    return {0: (u, v), 90: (v, 1 - u), 180: (1 - u, 1 - v), 270: (1 - v, u)}[rot]


class TouchTracker:
    """يحوّل أحداث evdev (type, code, value) إلى لمسات كاملة: {t0, t1, pts:[(t,x,y)], maxn}."""

    def __init__(self):
        self.slot = 0
        self.slots = {}
        self.btn = False
        self.has_id = False
        self.g = None
        self.done = []

    def feed(self, t, typ, code, val):
        if typ == 3:
            if code == 0x2F:                         # ABS_MT_SLOT
                self.slot = val
                return
            st = self.slots.setdefault(self.slot, {"id": -1, "x": None, "y": None})
            if code == 0x39:                         # ABS_MT_TRACKING_ID
                self.has_id = True
                st["id"] = -1 if val == 0xFFFFFFFF else val
            elif code == 0x35:
                st["x"] = val
            elif code == 0x36:
                st["y"] = val
        elif typ == 1 and code == 0x14A:             # BTN_TOUCH
            self.btn = bool(val)
        elif typ == 0 and code == 0:                 # SYN_REPORT
            self._syn(t)

    def _active(self):
        if self.has_id:
            act = [(k, s) for k, s in sorted(self.slots.items())
                   if s["id"] >= 0 and s["x"] is not None and s["y"] is not None]
        else:
            s = self.slots.get(0) or next(iter(self.slots.values()), None)
            act = [(0, s)] if (self.btn and s and s["x"] is not None and s["y"] is not None) else []
        return act

    def _syn(self, t):
        act = self._active()
        if act:
            x, y = act[0][1]["x"], act[0][1]["y"]
            if self.g is None:
                self.g = {"t0": t, "pts": [], "maxn": 0}
            self.g["pts"].append((t, x, y))
            self.g["maxn"] = max(self.g["maxn"], len(act))
        elif self.g is not None:
            self.g["t1"] = t
            self.done.append(self.g)
            self.g = None


class Recorder:
    def __init__(self, dev, name, start="city", every=0, interval=0.8, max_seconds=0, zoom=False):
        if not NAME_RE.match(name or ""):
            raise SystemExit("اسم المهمة: حروف إنجليزية وأرقام و_ فقط، ويبدأ بحرف (مثل arena2)")
        old = flows.TASKS.get(name)
        if old and not old.get("recorded"):
            raise SystemExit(f"الاسم «{name}» محجوز لمهمة مدمجة؛ اختر اسماً آخر")
        self.dev, self.name, self.start, self.every = dev, name, start, every
        self.interval, self.max_seconds, self.zoom = interval, max_seconds, zoom
        self.tracker = TouchTracker()
        self.touch = None
        self.rot = None
        self.W = self.H = 0
        self.ring = []                    # [(وقت بدء الالتقاط, صورة)]
        self._stop = threading.Event()
        self._nlines = 0
        self.events = []                  # لمسات مسجلة: dict (انظر _on_gesture)
        self._prev_up_wall = None
        self.stopped_by_edge = False
        self.calibrated = False

    # ---------------- تحويل ----------------
    def _norm(self, x, y):
        t = self.touch
        u = (x - t["xmin"]) / max(1, t["xmax"] - t["xmin"])
        v = (y - t["ymin"]) / max(1, t["ymax"] - t["ymin"])
        return min(1.0, max(0.0, u)), min(1.0, max(0.0, v))

    def _px(self, x, y):
        sx, sy = to_screen(*self._norm(x, y), self.rot)
        return sx * self.W, sy * self.H

    def _calibrate(self, g):
        """لمسة الزاوية العلوية اليسرى تحدد دوران الشاشة بالنسبة للوحة اللمس."""
        t = self.touch
        panel_land = (t["xmax"] - t["xmin"]) >= (t["ymax"] - t["ymin"])
        disp_land = self.W >= self.H
        cands = (0, 180) if panel_land == disp_land else (90, 270)
        u, v = self._norm(g["pts"][0][1], g["pts"][0][2])
        best = min(cands, key=lambda r: sum(c * c for c in to_screen(u, v, r)))
        sx, sy = to_screen(u, v, best)
        self.rot = best
        self.calibrated = True
        if sx > 0.35 or sy > 0.35:
            log(f"warning: calibration tap was far from the top-left corner ({sx:.2f},{sy:.2f}); rotation={best}")
        else:
            log(f"calibrated: rotation={best}")

    # ---------------- لقطات الخلفية ----------------
    def _shots_loop(self):
        while not self._stop.is_set():
            t = time.time()
            try:
                img = self.dev.screenshot()
                self.ring.append((t, img))
                del self.ring[:-8]
            except Exception as e:  # noqa: BLE001
                log(f"rec: screenshot error {e}")
            self._stop.wait(self.interval)

    def _shot_before(self, wall_down):
        cands = [s for s in self.ring if s[0] <= wall_down - 0.15]
        if cands:
            return cands[-1][1]
        return self.ring[0][1] if self.ring else None

    # ---------------- معالجة الأحداث ----------------
    def process(self, text, now=None):
        """يعالج نص getevent (الأسطر الكاملة الجديدة فقط)."""
        now = now if now is not None else time.time()
        lines = text[: text.rfind("\n") + 1].splitlines()
        new = lines[self._nlines:]
        self._nlines = len(lines)
        for ln in new:
            m = LINE.search(ln)
            if m:
                self.tracker.feed(float(m.group(1)), int(m.group(2), 16), int(m.group(3), 16), int(m.group(4), 16))
        while self.tracker.done:
            self._on_gesture(self.tracker.done.pop(0), now)

    def _on_gesture(self, g, read_wall):
        if not self.calibrated:
            self._calibrate(g)
            log("جاهز - ابدأ تنفيذ المهمة الآن (انتظر ثانيتين بين الضغطات). للإيقاف: اسحب من أسفل الشاشة أو Ctrl+C")
            return
        dur = g["t1"] - g["t0"]
        x0, y0 = self._px(g["pts"][0][1], g["pts"][0][2])
        x1, y1 = self._px(g["pts"][-1][1], g["pts"][-1][2])
        if g["maxn"] >= 2:
            log("rec: pinch ignored (البوت يصغّر بنفسه)")
            return
        if y0 > EDGE_STOP * self.H:
            self.stopped_by_edge = True
            self._stop.set()
            log("rec: bottom-edge gesture -> stop")
            return
        wall_up = read_wall
        wall_down = wall_up - dur
        gap = None if self._prev_up_wall is None else wall_down - self._prev_up_wall
        self._prev_up_wall = wall_up
        dist = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
        ev = {"t0": g["t0"], "t1": g["t1"], "dur": dur, "fast": gap is not None and gap < FAST_GAP_S,
              "shot": self._shot_before(wall_down)}
        if dist >= TAP_MAX_PX:
            ev.update(kind="swipe", x0=x0, y0=y0, x1=x1, y1=y1)
        elif dur >= LONG_PRESS_S:
            ev.update(kind="long", x0=x0, y0=y0, x1=x0, y1=y0)
        else:
            ev.update(kind="tap", x0=x0, y0=y0, x1=x0, y1=y0)
        self.events.append(ev)
        log(f"rec: #{len(self.events)} {ev['kind']} ({int(x0)},{int(y0)})"
            + (f"->({int(x1)},{int(y1)})" if ev["kind"] == "swipe" else ""))

    # ---------------- التشغيل ----------------
    def run(self):
        dev = self.dev
        self.touch = dev._touch_info()
        img0 = dev.screenshot()
        self.H, self.W = img0.shape[:2]
        if self.zoom:
            from bot import zoom_out_max
            log("rec: تثبيت المنظر (تصغير + إزالة الإزاحة) قبل التسجيل")
            zoom_out_max(dev)
        dev._sh(f"rm -f /sdcard/{REC_FILE}")
        proc = dev.bg(f"getevent -t {self.touch['path']} > /sdcard/{REC_FILE} 2>&1")
        th = threading.Thread(target=self._shots_loop, daemon=True)
        th.start()
        print("\n>>> اضغط الآن بإصبعك على أقصى الزاوية العلوية اليسرى من الشاشة (للمعايرة)\n", flush=True)
        t_start = time.time()
        try:
            while not self._stop.is_set():
                time.sleep(0.35)
                self.process(dev.read_shared(REC_FILE))
                if self.max_seconds and time.time() - t_start > self.max_seconds:
                    log("rec: time limit reached")
                    break
        except KeyboardInterrupt:
            log("rec: stopped by user")
        finally:
            self._stop.set()
            time.sleep(0.5)
            try:
                self.process(dev.read_shared(REC_FILE))      # آخر ما وصل
            except Exception:  # noqa: BLE001
                pass
            proc.terminate()
            try:
                dev._sh("pkill -f 'getevent -t' 2>/dev/null; killall getevent 2>/dev/null; rm -f /sdcard/" + REC_FILE)
            except Exception:  # noqa: BLE001
                pass
        return self.finalize()

    # ---------------- الإنهاء: قوالب + خطوات ----------------
    def finalize(self, root=None):
        root = root or os.path.dirname(os.path.abspath(__file__))
        evs = self.events
        if not evs:
            log("rec: لا توجد ضغطات مسجلة - لم يُحفظ شيء")
            return None
        tdir = os.path.join(root, config.TEMPLATES_DIR)
        out = os.path.join(root, config.OUTPUT_DIR, f"rec_{self.name}")
        shutil.rmtree(out, ignore_errors=True)
        os.makedirs(out, exist_ok=True)
        if os.path.isdir(tdir):                                   # تسجيل جديد بنفس الاسم يستبدل القديم
            for d in os.listdir(tdir):
                if re.fullmatch(rf"_{re.escape(self.name)}_s\d+", d):
                    shutil.rmtree(os.path.join(tdir, d), ignore_errors=True)
        steps, report = [], []
        for i, ev in enumerate(evs, 1):
            nxt = evs[i]["t0"] - ev["t1"] if i < len(evs) else 1.0
            wait = round(min(10.0, max(0.6, nxt)), 1)
            fx0, fy0 = ev["x0"] / self.W, ev["y0"] / self.H
            if ev["kind"] == "swipe":
                step = {"swipe": [round(fx0, 4), round(fy0, 4), round(ev["x1"] / self.W, 4), round(ev["y1"] / self.H, 4)],
                        "ms": int(min(1500, max(150, ev["dur"] * 1000))), "wait": wait}
            elif ev["kind"] == "long":
                step = {"swipe": [round(fx0, 4), round(fy0, 4), round(fx0, 4), round(fy0, 4)],
                        "ms": int(min(3000, max(600, ev["dur"] * 1000))), "wait": wait}
            else:
                step = self._tap_step(i, ev, fx0, fy0, wait, tdir, report)
            steps.append(step)
            self._preview(out, i, ev)
        data = {}
        path = flows.RECORDED_PATH
        if root != os.path.dirname(os.path.abspath(__file__)):
            path = os.path.join(root, "recorded_flows.json")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            pass
        data[self.name] = {"steps": steps, "start": self.start, "every": self.every, "zoom": bool(self.zoom),
                           "size": [self.W, self.H], "recorded": datetime.now().isoformat(timespec="seconds")}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        with open(os.path.join(out, "steps.json"), "w", encoding="utf-8") as f:
            json.dump(steps, f, ensure_ascii=False, indent=2)
        n_tpl = sum(1 for s in steps if "ui" in s)
        log(f"rec: حُفظت المهمة «{self.name}»: {len(steps)} خطوة ({n_tpl} بقالب، {len(steps) - n_tpl} بنقطة/سحب)")
        for r in report:
            log("rec: " + r)
        log(f"rec: صور المراجعة في {config.OUTPUT_DIR}/rec_{self.name}/  ·  للتشغيل: python bot.py --task {self.name}")
        return steps

    def _tap_step(self, i, ev, fx, fy, wait, tdir, report):
        img = ev["shot"]
        plain = {"xy": [round(fx, 4), round(fy, 4)], "wait": wait}
        if img is None:
            report.append(f"#{i}: بلا لقطة -> نقطة فقط")
            return plain
        if ev["fast"]:
            report.append(f"#{i}: ضغطة سريعة بعد سابقتها -> نقطة فقط (لقطتها قد تكون قديمة)")
            return plain
        x, y = int(round(ev["x0"])), int(round(ev["y0"]))
        h, w = img.shape[:2]
        half = min(MAX_HALF, x, y, w - 1 - x, h - 1 - y)
        if half < MIN_HALF:
            report.append(f"#{i}: عند حافة الشاشة -> نقطة فقط")
            return plain
        crop = img[y - half:y + half, x - half:x + half]
        if float(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY).std()) < MIN_TEXTURE:
            report.append(f"#{i}: منطقة بلا تفاصيل -> نقطة فقط")
            return plain
        name = f"{self.name}_s{i:02d}"
        d = os.path.join(tdir, "_" + name)
        os.makedirs(d, exist_ok=True)
        cv2.imwrite(os.path.join(d, f"{name}_1.png"), crop)
        return {"ui": name, "fixed": [round(fx, 4), round(fy, 4)], "near": True, "wait": wait}

    @staticmethod
    def _preview(out, i, ev):
        img = ev["shot"]
        if img is None:
            return
        pic = img.copy()
        cv2.circle(pic, (int(ev["x0"]), int(ev["y0"])), 28, (0, 0, 255), 3)
        if ev["kind"] == "swipe":
            cv2.arrowedLine(pic, (int(ev["x0"]), int(ev["y0"])), (int(ev["x1"]), int(ev["y1"])), (0, 255, 255), 4)
        cv2.putText(pic, str(i), (int(ev["x0"]) + 30, int(ev["y0"]) - 30), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
        cv2.imwrite(os.path.join(out, f"s{i:02d}.jpg"), pic, [cv2.IMWRITE_JPEG_QUALITY, 70])
