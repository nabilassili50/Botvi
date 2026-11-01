"""محرك المهام: ينفّذ الخطوات في flows.py ويعمل الصيد والجمع."""
import math
import os
import time

import cv2

import config
import flows
import positions
from util import log
from vision import _ignored, find_all_ui, find_ui, load_templates


class ArmyLimit(Exception):
    """ظهرت نافذة حد الجيش."""


class EnergyEmpty(Exception):
    """نفدت طاقة الصيد."""


class StepFailed(Exception):
    pass


class Runner:
    def __init__(self, dev, resource=None, level=None):
        self.dev = dev
        self.resource = resource or config.RESOURCE
        self.level = level                 # 1..5: الجمع حسب منطقة المستوى
        self._need_jump = True
        self._jump_idx = 0
        self._scan_i = 0
        self._target = None                # آخر وحش نصيده (x, y)
        self._skip = []                    # وحوش تعذّر صيدها في هذه الجولة
        self.blocked = {}                  # مهمة -> وقت إعادة المحاولة (بعد نفاد الطاقة)
        self.last_castle = 0.0             # وقت آخر تنفيذ لمهام القلعة
        self.round_failures = 0            # مهام فشلت (MAX_FAILS) في هذه الجولة - لكشف التعليق
        self.ui = load_templates()[1]
        self.names = {k.lstrip("_") for k in self.ui}
        self.saved = positions.load()      # نقاط محفوظة بدون قوالب (positions.json)
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

    def _dismiss(self):
        """يغلق نافذة مفتوحة بقالب X إن وُجد. لا يضغط Back أبداً (على الخريطة يفتح نافذة الخروج من اللعبة)."""
        img = self.dev.screenshot()
        for n in sorted(self.names):
            if n.startswith("close") or n == "map_close":
                pos = find_ui(img, self.ui, n, config.CLOSE_POPUP_THRESHOLD, exact=True)
                if pos:
                    self.dev.tap(*pos)
                    time.sleep(0.8)
                    return True
        return False

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

    def check_energy(self, img=None):
        g = flows.ENERGY_EMPTY
        if g["detect"] not in self.names:
            return
        img = img if img is not None else self.dev.screenshot()
        if not find_ui(img, self.ui, g["detect"], config.UI_THRESHOLD, exact=True):
            return
        log("energy empty dialog -> cancel (no refill from bag) and stop hunting")
        cancel = find_ui(img, self.ui, g["cancel"], config.UI_THRESHOLD, exact=True) \
            if g["cancel"] in self.names else None
        if cancel:
            self.dev.tap(*cancel)
        elif not self._dismiss():
            self.dev.back()                  # نافذة بلا زر معروف: Back يغلقها غالباً
        self.dev.wait(0.8)
        for _ in range(2):                 # نخرج من شاشة الأبطال/النافذة إن بقيت مفتوحة
            img = self.dev.screenshot()
            if any(find_ui(img, self.ui, n, config.UI_THRESHOLD, exact=True)
                   for n in ("hunt_go", "hunt_btn") if n in self.names):
                pos = find_ui(img, self.ui, "close", config.CLOSE_POPUP_THRESHOLD)
                if pos:
                    self.dev.tap(*pos)
                else:
                    self.dev.back()
                self.dev.wait(0.8)
        raise EnergyEmpty()

    def wait_for(self, name, timeout, threshold):
        end = time.time() + timeout
        while True:
            img = self.dev.screenshot()
            self.check_army_limit(img)
            self.check_energy(img)
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
        elif "ui" in st and st.get("repeat"):
            name = st["ui"]
            for _ in range(int(st["repeat"])):        # يضغط ما دام القالب ظاهراً
                if name not in self.names:
                    break
                pos = find_ui(self.dev.screenshot(), self.ui, name, st.get("threshold", config.UI_THRESHOLD), exact=True)
                if not pos:
                    break
                self.dev.tap(*pos)
                time.sleep(st.get("wait", 0.5))
        elif "ui" in st:
            name = st["ui"]
            thr = st.get("threshold", config.UI_THRESHOLD)
            pos = None
            if name in self.names:
                pos = self.wait_for(name, st.get("timeout", config.STEP_TIMEOUT), thr)
            if pos:
                d.tap(*pos)
            elif name in self.saved:
                log(f"'{name}' not found by template, using saved point")
                d.tap(*self._pos(*self.saved[name]))
            elif "fixed" in st:
                log(f"'{name}' not found, using fixed point")
                d.tap(*self._pos(*st["fixed"]))
            elif st.get("optional"):
                log(f"'{name}' absent (optional) - skip")
            else:
                why = "no template" if name not in self.names else "not found on screen"
                raise StepFailed(f"{name}: {why}")
        time.sleep(st.get("wait", 0.5))

    # ---- الجمع حسب مستوى المنطقة ----
    def open_zone(self):
        """يفتح مخطط مناطق الموارد ويضغط نقطة من حلقة المستوى (نقطة مختلفة في كل قفزة)."""
        for st in flows.ZONE_OPEN:
            self.do_step(st)
        pts = flows.zone_points(self.level, self.w, self.h)
        fx, fy = pts[self._jump_idx % len(pts)]
        self._jump_idx += 1
        log(f"zone: level {self.level} point #{self._jump_idx} ({fx:.2f},{fy:.2f})")
        self.dev.tap(*self._pos(fx, fy))
        time.sleep(config.ZONE_SETTLE)
        if "map_close" in self.names:
            pos = find_ui(self.dev.screenshot(), self.ui, "map_close", config.UI_THRESHOLD, exact=True)
            if pos:
                self.dev.tap(*pos)
                time.sleep(1.0)
        self._need_jump = False
        self._scan_i = 0

    def find_node(self, img, used):
        """عقدة من المورد المطلوب بجانب شارة المستوى المطلوب. يعيد (x, y) أو None."""
        nodes = [n for n in find_all_ui(img, self.ui, f"node_{self.resource}", config.NODE_THRESHOLD)
                 if not _ignored(n[0], n[1], img.shape)]          # نتجاهل أيقونات الواجهة العلوية والسفلية
        badges = find_all_ui(img, self.ui, f"lvl_{self.level}", config.NODE_THRESHOLD)
        best = None
        for bx, by, _ in badges:
            near = [(math.hypot(nx - bx, ny - by), nx, ny) for nx, ny, _ in nodes
                    if not any(abs(nx - ux) < 40 and abs(ny - uy) < 40 for ux, uy in used)]
            if near:
                d, nx, ny = min(near)
                if d <= config.NODE_BADGE_DIST and (best is None or d < best[0]):
                    best = (d, nx, ny)
        self._debug(img, "node", [(x, y, (0, 200, 0), "node") for x, y, _ in nodes]
                    + [(x, y, (255, 120, 0), f"L{self.level}") for x, y, _ in badges]
                    + ([(best[1], best[2], (0, 0, 255), "PICK")] if best else []))
        return (best[1], best[2]) if best else None

    def scan_swipe(self):
        dx, dy = flows.SCAN_DIRS[self._scan_i % len(flows.SCAN_DIRS)]
        self._scan_i += 1
        cx, cy = self.w / 2, self.h / 2
        lx, ly = dx * self.w * config.SWIPE_FRAC / 2, dy * self.h * config.SWIPE_FRAC / 2
        self.dev.swipe(cx + lx, cy + ly, cx - lx, cy - ly, config.SWIPE_MS)
        time.sleep(1.0)

    def zone_march(self):
        """يرسل جيشاً واحداً لعقدة مطابقة في منطقة المستوى."""
        if self._need_jump:
            self.open_zone()
        used = []
        thr = config.UI_THRESHOLD
        for _ in range(config.ZONE_SWIPES + 1):
            img = self.dev.screenshot()
            self.check_army_limit(img)
            pos = self.find_node(img, used)
            if pos:
                log(f"node {self.resource} L{self.level} at {pos}")
                self.dev.tap(*pos)
                time.sleep(1.2)
                btn = self.wait_for("gather_btn", 3, thr)
                if not btn:                      # عقدة محتلة/نافذة غير متوقعة
                    used.append(pos)
                    self._dismiss()
                    continue
                self.dev.tap(*btn)
                time.sleep(1.5)
                dep = self.wait_for("march_btn", config.STEP_TIMEOUT, thr)
                if not dep:
                    raise StepFailed("march_btn: not found on screen")
                self.dev.tap(*dep)
                time.sleep(1.5)
                self.check_army_limit()
                return
            self.scan_swipe()
            used = []
        self._need_jump = True                   # المحاولة القادمة تقفز لنقطة أخرى
        raise StepFailed(f"no {self.resource} L{self.level} node found")

    # ---- الصيد الذكي: نفس الوحش حتى يموت ثم وحش آخر، حتى تنتهي الطاقة ----
    def find_monster(self, img, near=None):
        hits = []
        for name in self.names:
            if name.startswith("monster"):
                hits += [(x, y) for x, y, _ in find_all_ui(img, self.ui, name, config.NODE_THRESHOLD)]
        h, w = img.shape[:2]
        hits = [p for p in hits if not _ignored(p[0], p[1], img.shape)
                and not any(abs(p[0] - sx) < 60 and abs(p[1] - sy) < 60 for sx, sy in self._skip)]
        if not hits:
            self._debug(img, "monster-none", [])
            return None
        if near:
            d, p = min((math.hypot(x - near[0], y - near[1]), (x, y)) for x, y in hits)
            pick = p if d <= config.MONSTER_NEAR_PX else None
        else:
            pick = min(hits, key=lambda p: math.hypot(p[0] - w / 2, p[1] - h / 2))
        self._debug(img, "monster", [(x, y, (0, 255, 255), "mon") for x, y in hits]
                    + ([(pick[0], pick[1], (0, 0, 255), "PICK")] if pick else []))
        return pick

    def _open_popup(self, pos):
        """يضغط الوحش ويعيد موضع زر «صيد الوحش» أو None إن لم تظهر النافذة."""
        self.dev.tap(*pos)
        time.sleep(1.2)
        return self.wait_for("hunt_btn", 3, config.UI_THRESHOLD)

    def _reopen_target(self):
        """يعيد فتح نافذة نفس الوحش بعد الهجمة. الخريطة قد تتحرك قليلاً ومظهر الوحش يتغير
        (شريط الدم واسم اللاعب)، لذلك نجرّب موضعه الأخير وما حوله. يعيد زر الصيد أو None."""
        img = self.dev.screenshot()
        self.check_army_limit(img)
        self.check_energy(img)
        bx, by = self.find_monster(img, near=self._target) or self._target
        for dx, dy in ((0, 0), (0, -40), (40, 0), (-40, 0), (0, 40), (40, -40), (-40, -40), (0, -80)):
            btn = self._open_popup((bx + dx, by + dy))
            if btn:
                self._target = (bx + dx, by + dy)
                return btn
            self._dismiss()
        return None

    def hunt_march(self):
        thr = config.UI_THRESHOLD
        if self._need_jump and self.level:
            self.open_zone()
        btn, pos = None, None
        if self._target:                             # نكمل على نفس الوحش
            for attempt in range(config.HUNT_RETRIES):
                btn = self._reopen_target()
                if btn:
                    pos = self._target
                    break
                # قد يكون الوحش في معركة مع جيشنا: ننتظر ثم نعيد قبل أن نعتبره مات
                log(f"same monster: no hunt button (try {attempt + 1}/{config.HUNT_RETRIES})")
                time.sleep(config.HUNT_RETRY_WAIT)
            if not btn:
                log("monster finished (or gone) -> look for another")
                self._target = None
        if not btn:
            for _ in range(config.ZONE_SWIPES + 1):
                img = self.dev.screenshot()
                self.check_army_limit(img)
                self.check_energy(img)
                pos = self.find_monster(img)
                if pos:
                    btn = self._open_popup(pos)
                    if btn:
                        break
                    self._skip.append(pos)           # ليس وحشاً صالحاً للصيد
                    self._dismiss()
                    continue
                self.scan_swipe()
                self._skip = []
            if not btn:
                self._need_jump = True
                raise StepFailed("no huntable monster found")
        self.dev.tap(*btn)
        time.sleep(1.0)
        keep = self.wait_for("equip_keep", 2, thr)    # «إبقاء المعدات الحالية» - لا نضغط «اذهب للتغيير» أبداً
        if keep:
            self.dev.tap(*keep)
            time.sleep(1.0)
        go = self.wait_for("hunt_go", config.STEP_TIMEOUT, thr)
        if not go:
            raise StepFailed("hunt_go: not found on screen")
        self.dev.tap(*go)
        time.sleep(1.5)
        self.check_energy()
        self.check_army_limit()
        self._target = pos
        time.sleep(config.HUNT_WAIT)

    def all_blocked(self, names):
        now = time.time()
        return bool(names) and all(self.blocked.get(n, 0) > now for n in names)

    # ---- المدينة / الخريطة ----
    def _debug(self, img, label, marks):
        """يحفظ صورة عليها دوائر لما رآه البوت: marks = [(x, y, (B,G,R), نص)]. آخر 60 صورة فقط."""
        if not config.DEBUG:
            return
        try:
            d = os.path.join(config.OUTPUT_DIR, "debug")
            os.makedirs(d, exist_ok=True)
            o = img.copy()
            for x, y, col, txt in marks:
                cv2.circle(o, (int(x), int(y)), 24, col, 4)
                cv2.putText(o, txt, (int(x) - 20, int(y) - 28), cv2.FONT_HERSHEY_SIMPLEX, 0.6, col, 2)
            self._dbg_n = getattr(self, "_dbg_n", 0) + 1
            cv2.imwrite(os.path.join(d, f"{self._dbg_n:04d}_{label}.jpg"), o, [cv2.IMWRITE_JPEG_QUALITY, 70])
            old = sorted(os.listdir(d))[:-60]
            for f in old:
                os.remove(os.path.join(d, f))
        except OSError:
            pass

    def _visible(self, name, img=None):
        if name not in self.names:
            return None
        img = img if img is not None else self.dev.screenshot()
        return find_ui(img, self.ui, name, config.UI_THRESHOLD, exact=True)

    def ensure_city(self):
        """إن كنا على الخريطة (يظهر زر القلعة city_btn) ننتقل للمدينة."""
        pos = self._visible("city_btn")
        if pos:
            log("-> city")
            self.dev.tap(*pos)
            time.sleep(config.LOAD_WAIT / 3)

    def ensure_world(self):
        """إن كنا في المدينة (يظهر زر الخريطة world_map) ننتقل للخريطة."""
        pos = self._visible("world_map")
        if pos:
            log("-> world map")
            self.dev.tap(*pos)
            time.sleep(config.LOAD_WAIT / 3)

    def run_castle(self):
        """مهام القلعة بالترتيب. المهمة التي ينقصها قالب تُتجاوز، وفشل مهمة لا يوقف البقية."""
        self.ensure_city()
        self.dismiss_popups()
        done = 0
        for name, steps in flows.CASTLE_TASKS.items():
            need = [st["ui"] for st in steps if "ui" in st and not st.get("optional") and "fixed" not in st]
            miss = [n for n in need if n not in self.names and n not in self.saved]
            if miss:
                log(f"castle/{name}: skipped, missing templates {miss}")
                continue
            try:
                if name == "saga":
                    self.run_saga()
                else:
                    self.run_flow(steps)
                done += 1
                log(f"castle/{name}: done")
            except (StepFailed, ArmyLimit) as e:
                log(f"castle/{name}: failed ({e})")
            for _ in range(2):                          # نغلق ما بقي مفتوحاً
                if not self._dismiss():
                    break
        self.last_castle = time.time()
        return done

    # ---- الملحمة البطولية ----
    def _on_saga(self, img=None):
        return bool(self._visible("saga_title", img))

    def _saga_open(self):
        if self._on_saga():
            return True
        b = self.wait_for("saga_building", 4, 0.78) if "saga_building" in self.names else None
        if not b and "saga_building" in self.saved:
            log("'saga_building' not found by template, using saved point")
            b = self._pos(*self.saved["saga_building"])
        if not b:
            raise StepFailed("saga_building: not found on screen")
        self.dev.tap(*b)
        time.sleep(1.2)
        c = self.wait_for("saga_compass", 4, config.UI_THRESHOLD)
        if not c:
            self._dismiss()
            raise StepFailed("saga_compass: not found after tapping the building")
        self.dev.tap(*c)
        time.sleep(1.5)
        if not self.wait_for("saga_title", 8, config.UI_THRESHOLD):
            raise StepFailed("saga screen did not open")
        return True

    def _saga_claim_all(self):
        n = 0
        for _ in range(8):
            if not self._on_saga():
                self._dismiss()
                if not self._on_saga():
                    break
            pos = self._visible("saga_claim")
            if not pos:
                break
            self.dev.tap(*pos)
            n += 1
            log(f"saga: claim #{n}")
            time.sleep(1.8)
            for _ in range(3):                      # شاشة المكافآت: نغلقها بالـ X حتى نعود لخريطة الملحمة
                if self._on_saga():
                    break
                if not self._dismiss():
                    self.dev.tap(*self._pos(0.5, 0.9))   # بعض الشاشات تُغلق بلمسة فارغة
                    time.sleep(0.8)
        return n

    def _saga_close_popup(self):
        for i in range(3):
            img = self.dev.screenshot()
            if not any(self._visible(n, img) for n in ("saga_auto", "saga_remove", "saga_assign")):
                return
            if i < 2:
                self.dev.tap(*self._pos(*flows.SAGA_NEUTRAL))
            else:
                self.dev.back()
            time.sleep(0.9)

    def _saga_start_all(self):
        started = 0
        for i, (fx, fy) in enumerate(flows.SAGA_SLOTS, 1):
            if not self._on_saga():
                self._dismiss()
                if not self._on_saga():
                    log("saga: left the saga screen unexpectedly - stop")
                    break
            self.dev.tap(*self._pos(fx, fy))
            time.sleep(1.3)
            img = self.dev.screenshot()
            auto = self._visible("saga_auto", img)
            if auto:
                self.dev.tap(*auto)                  # يختار أفضل 5 أبطال (5/5)
                time.sleep(1.0)
                img = self.dev.screenshot()
            go = self._visible("saga_assign", img)
            if go and (auto or self._visible("saga_remove", img)):
                self.dev.tap(*go)
                started += 1
                log(f"saga: island #{i} started")
                time.sleep(1.8)
            else:
                log(f"saga: island #{i} not startable (busy / limit reached)")
            self._saga_close_popup()
        return started

    def run_saga(self):
        if time.time() - getattr(self, "last_saga", 0) < 120:
            return 0
        self.last_saga = time.time()
        self.ensure_city()
        self.dismiss_popups()                         # يغلق لافتات الإعلانات
        self._saga_open()
        claimed = self._saga_claim_all()
        started = self._saga_start_all()
        for _ in range(3):                            # خروج من الملحمة إلى القلعة
            if not self._dismiss():
                break
        log(f"saga: claimed {claimed}, started {started}")
        return started

    def run_flow(self, flow):
        for st in flow:
            self.do_step(st)
        self.check_army_limit()

    # ---- مهمة كاملة ----
    def run_task(self, name):
        if name == "castle":
            if time.time() - self.last_castle < config.CASTLE_EVERY_SEC:
                return 0
            log("task castle: start")
            return self.run_castle()
        if name == "saga":
            miss = [st["ui"] for st in flows.CASTLE_TASKS["saga"] if st["ui"] not in self.names]
            if miss:
                log(f"saga: skipped, missing templates {miss}")
                return 0
            log("task saga: start")
            try:
                return self.run_saga()
            except StepFailed as e:
                log(f"saga: failed ({e})")
                self._dismiss()
                return 0
        if name in ("hunt", "gather"):
            self.ensure_world()
        cfg = flows.TASKS[name]
        zone = bool(self.level) and name == "gather"
        hunt = name == "hunt"
        flow = None if (zone or hunt) else flows.get_flow(name, self.resource)
        limit = getattr(config, cfg["max_key"]) or 10 ** 6
        sent, fails = 0, 0
        log(f"task {name}: start (max {limit})" + (f" resource={self.resource}" if name == "gather" else "") + (f" zone-level={self.level}" if zone else ""))
        while sent < limit and fails < config.MAX_FAILS:
            try:
                if hunt:
                    self.hunt_march()
                elif zone:
                    self.zone_march()
                else:
                    self.run_flow(flow)
                sent += 1
                fails = 0
                log(f"{name}: march #{sent} sent")
            except EnergyEmpty:
                self.blocked[name] = time.time() + config.ENERGY_RETRY_SEC
                self._target = None
                log(f"{name}: energy finished after {sent} attacks; retry in {config.ENERGY_RETRY_SEC // 60} min")
                return sent
            except ArmyLimit:
                log(f"{name}: army limit reached after {sent} marches")
                return sent
            except StepFailed as e:
                fails += 1
                log(f"{name}: step failed ({e}) [{fails}/{config.MAX_FAILS}]")
                if zone or hunt:
                    self._dismiss()                       # على الخريطة: لا Back (يفتح نافذة الخروج)
                else:
                    for _ in range(2):                    # نرجع للحالة الطبيعية
                        self.dev.back()
                        time.sleep(0.6)
        if fails >= config.MAX_FAILS:
            self.round_failures += 1
        log(f"task {name}: done, {sent} marches")
        return sent

    def run_all(self, names):
        total = {}
        self.round_failures = 0
        for n in names:
            if self.blocked.get(n, 0) > time.time():
                log(f"task {n}: waiting for energy ({int(self.blocked[n] - time.time())}s left)")
                total[n] = 0
                continue
            try:
                total[n] = self.run_task(n)
            except Exception as e:  # noqa: BLE001
                log(f"task {n} error: {e}")
                total[n] = 0
        return total


def missing_templates(names, resource=None, ui=None, level=None):
    """يعيد {مهمة: [قوالب ناقصة]} للخطوات الإلزامية (بدون optional/fixed) + قوالب حد الجيش."""
    ui = ui if ui is not None else load_templates()[1]
    have = {k.lstrip("_") for k in ui}
    have |= set(positions.load())          # النقطة المحفوظة تغني عن القالب
    out = {}
    for n in names:
        need = []
        if n == "castle":
            for steps in flows.CASTLE_TASKS.values():
                need += [st["ui"] for st in steps
                         if "ui" in st and not st.get("optional") and "fixed" not in st and st["ui"] not in have]
            out[n] = sorted(set(need))
            continue
        if n == "saga":
            out[n] = sorted({st["ui"] for st in flows.CASTLE_TASKS["saga"] if st["ui"] not in have})
            continue
        if n == "hunt":
            if not any(h.startswith("monster") for h in have):
                need.append("monster")
            need += [t for t in ("hunt_btn", "hunt_go", "energy_empty") if t not in have]
        elif level and n == "gather":
            res = resource or config.RESOURCE
            need += [t for t in (f"node_{res}", f"lvl_{level}", "gather_btn", "march_btn") if t not in have]
        for st in ([] if (n == "hunt" or (level and n == "gather")) else flows.get_flow(n, resource)):
            u = st.get("ui")
            if u and not st.get("optional") and "fixed" not in st and u not in have:
                need.append(u)
        for key in ("detect", "confirm"):
            if flows.ARMY_LIMIT[key] not in have:
                need.append(flows.ARMY_LIMIT[key])
        out[n] = sorted(set(need))
    return out
