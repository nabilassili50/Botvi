"""محرك المهام: ينفّذ الخطوات في flows.py ويعمل الصيد والجمع."""
import time

import config
import flows
from util import log
from vision import find_ui, load_templates


class ArmyLimit(Exception):
    """ظهرت نافذة حد الجيش."""


class StepFailed(Exception):
    pass


class Runner:
    def __init__(self, dev, resource=None):
        self.dev = dev
        self.resource = resource or config.RESOURCE
        self.ui = load_templates()[1]
        self.names = {k.lstrip("_") for k in self.ui}
        self.w, self.h = dev.size()
        if self.w < self.h:               # الشاشة في الوضع العمودي: اللعبة أفقية
            self.w, self.h = self.h, self.w

    # ---- أدوات ----
    def _pos(self, fx, fy):
        return fx * self.w, fy * self.h

    def dismiss_popups(self):
        """يغلق النوافذ المنبثقة (قوالب _close*) قبل كل جولة."""
        if not any(n.startswith("close") for n in self.names):
            return
        for i in range(config.CLOSE_POPUP_ATTEMPTS):
            pos = find_ui(self.dev.screenshot(), self.ui, "close", config.CLOSE_POPUP_THRESHOLD)
            if not pos:
                return
            log(f"closing popup ({i + 1}) at {pos}")
            self.dev.tap(*pos)
            self.dev.wait(1.0)

    def check_army_limit(self, img=None):
        g = flows.ARMY_LIMIT
        if g["detect"] not in self.names:
            return
        img = img if img is not None else self.dev.screenshot()
        if find_ui(img, self.ui, g["detect"], config.UI_THRESHOLD, exact=True):
            log("army limit dialog -> confirm and stop")
            ok = find_ui(img, self.ui, g["confirm"], config.UI_THRESHOLD, exact=True) \
                if g["confirm"] in self.names else None
            if ok:
                self.dev.tap(*ok)
            else:
                self.dev.back()
            self.dev.wait(0.8)
            raise ArmyLimit()

    def wait_for(self, name, timeout, threshold):
        end = time.time() + timeout
        while True:
            img = self.dev.screenshot()
            self.check_army_limit(img)
            pos = find_ui(img, self.ui, name, threshold, exact=True)
            if pos:
                return pos
            if time.time() >= end:
                return None
            time.sleep(config.STEP_POLL)

    def do_step(self, st):
        d = self.dev
        if "sleep" in st:
            time.sleep(st["sleep"])
        elif "back" in st:
            d.back()
        elif "swipe" in st:
            x1, y1, x2, y2 = st["swipe"]
            d.swipe(*self._pos(x1, y1), *self._pos(x2, y2), st.get("ms", 400))
        elif "xy" in st:
            d.tap(*self._pos(*st["xy"]))
        elif "ui" in st:
            name = st["ui"]
            thr = st.get("threshold", config.UI_THRESHOLD)
            pos = None
            if name in self.names:
                pos = self.wait_for(name, st.get("timeout", config.STEP_TIMEOUT), thr)
            if pos:
                d.tap(*pos)
            elif "fixed" in st:
                log(f"'{name}' not found, using fixed point")
                d.tap(*self._pos(*st["fixed"]))
            elif st.get("optional"):
                log(f"'{name}' absent (optional) - skip")
            else:
                why = "no template" if name not in self.names else "not found on screen"
                raise StepFailed(f"{name}: {why}")
        time.sleep(st.get("wait", 0.5))

    def run_flow(self, flow):
        for st in flow:
            self.do_step(st)
        self.check_army_limit()

    # ---- مهمة كاملة ----
    def run_task(self, name):
        cfg = flows.TASKS[name]
        flow = flows.get_flow(name, self.resource)
        limit = getattr(config, cfg["max_key"])
        sent, fails = 0, 0
        log(f"task {name}: start (max {limit})" + (f" resource={self.resource}" if name == "gather" else ""))
        while sent < limit and fails < config.MAX_FAILS:
            try:
                self.run_flow(flow)
                sent += 1
                fails = 0
                log(f"{name}: march #{sent} sent")
            except ArmyLimit:
                log(f"{name}: army limit reached after {sent} marches")
                return sent
            except StepFailed as e:
                fails += 1
                log(f"{name}: step failed ({e}) [{fails}/{config.MAX_FAILS}]")
                for _ in range(2):         # نرجع للحالة الطبيعية
                    self.dev.back()
                    time.sleep(0.6)
        log(f"task {name}: done, {sent} marches")
        return sent

    def run_all(self, names):
        total = {}
        for n in names:
            try:
                total[n] = self.run_task(n)
            except Exception as e:  # noqa: BLE001
                log(f"task {n} error: {e}")
                total[n] = 0
        return total


def missing_templates(names, resource=None, ui=None):
    """يعيد {مهمة: [قوالب ناقصة]} للخطوات الإلزامية (بدون optional/fixed) + قوالب حد الجيش."""
    ui = ui if ui is not None else load_templates()[1]
    have = {k.lstrip("_") for k in ui}
    out = {}
    for n in names:
        need = []
        for st in flows.get_flow(n, resource):
            u = st.get("ui")
            if u and not st.get("optional") and "fixed" not in st and u not in have:
                need.append(u)
        for key in ("detect", "confirm"):
            if flows.ARMY_LIMIT[key] not in have:
                need.append(flows.ARMY_LIMIT[key])
        out[n] = sorted(set(need))
    return out
