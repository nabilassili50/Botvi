import json, os, time, threading, shutil
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import shizuku
import tasks.guard as guard
import tasks.zoom as zoom
import vdisplay
D = os.path.dirname(os.path.abspath(__file__))
SF = os.path.join(D, "settings.json")
DEF = {"auto_switch": True, "auto_upgrade": True, "auto_craft": True, "cabinet": True,
       "idle_time": 300, "idle_set": "Gathering", "port": 8080,
       "saga": True, "saga_int": 30, "saga_entry": [],
       "mana": True, "mana_int": 90, "lair": True, "lair_int": 240, "heal": True, "heal_int": 120, "heal_speed": True, "arena": False, "arena_int": 180, "arena_pick": 0, "dice": True, "dice_int": 180, "border": True, "border_int": 120, "train": False, "train_int": 240, "train_type": "infantry", "train_tier": 4, "guard": True, "tower": True, "tower_int": 360, "tower_items": True, "workshop": True, "workshop_int": 240, "beast": True, "beast_int": 120, "beast_confirm": True, "lunar": True, "lunar_int": 360, "lunar_swap": True, "lunar_skip_short": False, "gifts": True, "gifts_int": 120, "gifts_clear": False, "ship": True, "ship_int": 120, "mystery": True, "mystery_int": 3, "help": True, "help_int": 2, "skills": True, "skills_int": 180, "skills_entry": [], "gather": True, "gather_int": 30, "gather_type": "stone", "gather_level": 4, "gather_count": 1, "gather_swipes": 6, "zoom": True, "zoom_check": 90, "game_only": True, "relaunch_after": 90, "vdisplay": False, "vd_zoom": True, "vd_size": "1280x800", "vd_dpi": 240, "speed": 0.75, "fast_shell": True}
S = dict(DEF)
if os.path.exists(SF): S.update(json.load(open(SF)))
shizuku.CFG = S      # تجاوز شاشة اللمس يدوياً من settings.json (touch_path ...)
ST = {"running": False, "shizuku": False, "last_beat": 0, "last_action": time.time()}
LAST = {}
VERSION = "v3.11"      # يظهر في أعلى اللوحة وفي أول السجل: غيّره مع كل نسخة جديدة
LASTSHOT = {"png": None, "t": 0}
LOGS = []; EV = []; EVID = [0]; CUR = [""]; BOOT = time.time()
CNT = {"ok": 0, "warn": 0, "err": 0, "info": 0}; STAT = {"runs": {}, "errs": {}, "lasterr": {}, "marches": 0}
def lvl_of(m):
    if any(w in m for w in ("خطأ", "فشل", "تعذّر")): return "err"
    if any(w in m for w in ("لم ", "تخطّي", "قد لا", "أُوقفت", "خرجنا", "ليست في الواجهة", "غادرت", "لسنا في", "انقطع الاتصال", "ما زال الاتصال")): return "warn"
    if any(w in m for w in ("أُرسلت", "استلام", "صُغّرت", "حُفظت الإعدادات")): return "ok"
    return "info"
def log(m):
    LOGS.append(time.strftime("%H:%M:%S ") + m); del LOGS[:-300]
    k = CUR[0] if RL.locked() else ""; lv = lvl_of(m); CNT[lv] += 1
    EVID[0] += 1; EV.append({"id": EVID[0], "t": time.strftime("%H:%M:%S"), "lv": lv, "k": k, "m": m}); del EV[:-400]
    if lv == "err" and k: STAT["errs"][k] = STAT["errs"].get(k, 0) + 1; STAT["lasterr"][k] = [time.time(), m]
    if "أُرسلت مسيرة (" in m: STAT["marches"] += 1
def save(): json.dump(S, open(SF, "w"), ensure_ascii=False, indent=1)

TASKS = [("help", "مساعدات التحالف (أولوية)", "help_int"), ("mystery", "صندوق الغموض", "mystery_int"), ("ship", "سفينة الشحن (تبادل)", "ship_int"), ("gifts", "هدايا التحالف", "gifts_int"), ("saga", "الملحمة البطولية", "saga_int"), ("mana", "تكرير المانا", "mana_int"), ("lair", "مغارة الظلام", "lair_int"), ("heal", "علاج الجنود", "heal_int"), ("arena", "ميدان الأبطال", "arena_int"), ("dice", "لوحة النرد", "dice_int"), ("border", "صناديق بوابة الحدود", "border_int"), ("train", "تدريب القوات", "train_int"), ("tower", "برج الوحوش (دمج)", "tower_int"), ("workshop", "هدية إمدادات التشكيل", "workshop_int"), ("beast", "حلبة تدريب الوحوش", "beast_int"), ("lunar", "المصنع القمري (تصنيع الأسلحة)", "lunar_int"), ("skills", "مهارات الوحوش المساعدة", "skills_int"), ("gather", "جمع الموارد (آخر المهام)", "gather_int")]
RES = {}
RL = threading.Lock()
NAMES = dict((k, n) for k, n, _ in TASKS); NAMES.update({"guard": "الحارس", "zoom": "تصغير القلعة", "": "النظام"})

PEND = set()
def run_task(key, manual=False):
    try: _run_task(key, manual)
    finally: PEND.discard(key)

def _run_task(key, manual):
    with RL:
        if shizuku.STOP.is_set(): return        # أُوقف البوت أثناء الانتظار: لا تبدأ
        if S.get("game_only", True) and not manual and not shizuku.front(True):
            LAST.pop(key, None); log("تخطّي %s: اللعبة ليست في الواجهة" % key); return
        CUR[0] = key; STAT["runs"][key] = STAT["runs"].get(key, 0) + 1
        mod = __import__("tasks." + key, fromlist=[key])
        log("بدء مهمة: " + key)
        try: guard.clear(log, S)
        except shizuku.Stopped as e: log("أُوقفت المهمة: %s (%s)" % (key, e)); return
        except Exception as e: log("خطأ في الحارس: %s" % e)
        if key != "zoom" and S.get("zoom", True) and not shizuku.STOP.is_set():
            try:
                if zoom.need(S): zoom.zoom_out(log, S, probe=not guard.NEED_ZOOM[0])
            except shizuku.Stopped as e: log("أُوقفت المهمة: %s (%s)" % (key, e)); return
            except Exception as e: log("خطأ في الزوم: %s" % e)
        try: r = mod.run(log, S)
        except shizuku.Stopped as e:
            if isinstance(e, shizuku.LeftGame): LAST.pop(key, None)       # لم تكتمل: تُعاد عند عودة اللعبة
            log("أُوقفت المهمة: %s (%s)" % (key, e)); return
        except Exception as e: r = None; log("خطأ في %s: %s" % (key, e))
        try:
            if shizuku.front(True) or not S.get("game_only", True): guard.clear(log, S)
        except shizuku.Stopped as e: log("أُوقفت المهمة: %s (%s)" % (key, e)); return
        except Exception as e: log("خطأ في الحارس: %s" % e)
        RES[key] = time.time(); ST["last_action"] = time.time(); PEND.discard(key)
        if key == "mana" and r == "limit": LAST["mana"] = time.time() + 10 * 3600

VDS = {"busy": False, "err": "", "retry": 0, "chk": 0, "report": None}
def _vd_job(fn):
    VDS["busy"] = True
    try: fn()
    except shizuku.Stopped: pass
    except Exception as e:
        VDS["err"] = str(e); VDS["retry"] = time.time() + 120; log("خطأ في الشاشة الثانوية: %s (سأعود للشاشة الرئيسية وأعيد المحاولة بعد دقيقتين)" % e)
    finally: save(); VDS["busy"] = False
def _vd_on():
    vdisplay.enable(log, S); VDS["err"] = ""
    if not vdisplay.bring_game(log, S): log("الشاشة الثانوية: لم تظهر اللعبة عليها بعد؛ سيحاول الحارس فتحها")
    else: vdisplay.wait_city(log)
def _vd_off(): vdisplay.disable(log, S)
def _vd_test():
    VDS["report"] = None; VDS["report"] = vdisplay.test(log, S)
def vd_sync():
    shizuku.VD["zf"] = bool(S.get("vd_zoom", True))
    if VDS["busy"]: return
    want, on = bool(S.get("vdisplay")), shizuku.VD["on"]; now = time.time()
    if want and not on and now >= VDS["retry"]: threading.Thread(target=_vd_job, args=(_vd_on,), daemon=True).start()
    elif want and on and now - VDS["chk"] > 20:
        VDS["chk"] = now
        if not vdisplay.alive():
            log("الشاشة الثانوية: اختفت (تُعاد إنشاؤها)"); shizuku.VD["on"] = False
    elif not want and on: threading.Thread(target=_vd_job, args=(_vd_off,), daemon=True).start()

def due(name, mins):
    if time.time() - LAST.get(name, 0) < mins * 60: return False
    LAST[name] = time.time(); return True

def game_ready():
    """لا يضغط البوت شيئاً إلا واللعبة في الواجهة. عند ضغط تشغيل أو غياب طويل يفتح اللعبة وينتظر تحميلها."""
    if not S.get("game_only", True): return True
    if shizuku.front(True): ST["away"] = 0; ST.pop("launch_now", None); return True
    now = time.time(); wait = int(S.get("relaunch_after", 90))
    if not ST.get("away"): ST["away"] = now; log("اللعبة ليست في الواجهة: البوت لا يضغط شيئاً حتى تُفتح")
    if ST.pop("launch_now", False) or (wait and now - ST["away"] > wait):
        with RL:
            CUR[0] = "guard"
            try: guard.clear(log, S)
            except shizuku.Stopped: pass
            except Exception as e: log("خطأ في فتح اللعبة: %s" % e)
        ST["away"] = 0 if shizuku.front(True) else time.time()
    return bool(shizuku.front(True))

def watch():
    if time.time() - LAST.get("guard", 0) < 60: return
    if S.get("game_only", True) and not shizuku.front(): return
    LAST["guard"] = time.time()
    if RL.acquire(False):
        CUR[0] = "guard"
        try: guard.clear(log, S)
        except shizuku.Stopped: pass
        except Exception as e: log("خطأ في الحارس: %s" % e)
        finally: RL.release()

def tick():
    shizuku.CHECK[0] = bool(S.get("game_only", True))
    try: shizuku.SPEED[0] = min(2.0, max(0.3, float(S.get("speed", 0.75))))
    except Exception: shizuku.SPEED[0] = 0.75
    want = bool(S.get("fast_shell", True))
    if want != shizuku.FAST["on"] and (want or shizuku.FAST["bad"] == 0): shizuku.FAST["on"] = want; shizuku.FAST["bad"] = 0; shizuku.reset_sessions()
    if VDS["busy"]: return
    if not game_ready(): return
    watch()
    for key, _, ik in TASKS:
        if not ST["running"]: return
        if S.get(key) and due(key, int(S.get(ik, 60))): run_task(key)
    if S["auto_switch"] and time.time() - ST["last_action"] > int(S["idle_time"]):
        log("خمول: تبديل إلى طقم " + S["idle_set"])  # TODO: نقرات تبديل المعدات
        ST["last_action"] = time.time()

def loop():
    while True:
        ST["shizuku"] = shizuku.ok(); ST["last_beat"] = time.time()
        if ST["shizuku"]:
            try: vd_sync()
            except Exception as e: log("خطأ: %s" % e)
        if ST["shizuku"] and not VDS["busy"] and time.time() - ST.get("fts", 0) > 8:
            ST["fts"] = time.time()
            try: ST["front"] = bool(shizuku.front(True))
            except Exception: pass
        if ST["shizuku"] and ST.get("front") and time.time() - LASTSHOT["t"] > 15:        # احتفظ بآخر لقطة للعبة لتعرضها اللوحة وهي في الخلفية
            try: LASTSHOT["png"] = shizuku.panel_shot(); LASTSHOT["t"] = time.time()
            except Exception: pass
        if ST["running"] and ST["shizuku"]:
            try: tick()
            except shizuku.Stopped: pass
            except Exception as e: log("خطأ: %s" % e)
        time.sleep(1.5)

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def send(self, body, ct="application/json", extra=None):
        if isinstance(body, (dict, list)): body = json.dumps(body, ensure_ascii=False)
        if isinstance(body, str): body = body.encode()
        self.send_response(200); self.send_header("Content-Type", ct)
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items(): self.send_header(k, str(v))
        self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if self.path == "/": self.send(open(os.path.join(D, "panel.html"), "rb").read(), "text/html; charset=utf-8")
        elif self.path == "/api/state":
            now = time.time(); cur = CUR[0] if RL.locked() else ""; tl = []
            for k, n, i in TASKS:
                iv = int(S.get(i, 60)); last = LAST.get(k, 0); la = STAT["lasterr"].get(k)
                tl.append({"key": k, "name": n, "on": bool(S.get(k)), "int": iv, "last": RES.get(k, 0), "next": max(0, last + iv * 60 - now) if (S.get(k) and last) else 0,
                           "st": "run" if cur == k else ("off" if not S.get(k) else "wait"), "runs": STAT["runs"].get(k, 0), "errs": STAT["errs"].get(k, 0),
                           "lasterr": la[1] if la else "", "errat": la[0] if la else 0})
            self.send({"version": VERSION, "st": ST, "settings": S, "logs": LOGS[-300:], "tasks": tl, "events": EV[-300:], "names": NAMES, "current": cur,
                       "vd": {"want": bool(S.get("vdisplay")), "on": shizuku.VD["on"], "id": shizuku.VD["id"], "cap": shizuku.VD["cap"], "busy": VDS["busy"], "err": VDS["err"], "report": VDS["report"]},
                       "stat": {"cnt": CNT, "marches": STAT["marches"], "runs": sum(STAT["runs"].values()), "boot": BOOT}, "now": now})
        elif self.path.startswith("/api/screen"):
            try:
                live = (not S.get("game_only", True)) or bool(ST.get("front"))
                if live:
                    LASTSHOT["png"] = shizuku.panel_shot(); LASTSHOT["t"] = time.time()
                png = LASTSHOT["png"]
                self.send(png or b"", "image/png", {"X-Shot-Live": int(live), "X-Shot-Age": int(time.time() - LASTSHOT["t"]) if png else -1})
            except Exception as e: self.send(b"", "image/png", {"X-Shot-Live": 0, "X-Shot-Age": -1})
        else: self.send({"error": 404})
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0)); d = json.loads(self.rfile.read(n) or b"{}")
        if self.path == "/api/settings": S.update(d); save(); log("حُفظت الإعدادات")
        elif self.path == "/api/run":
            ST["running"] = bool(d.get("on")); guard.NEED_ZOOM[0] = guard.NEED_ZOOM[0] or ST["running"]; ST["launch_now"] = ST["running"]; ST["away"] = 0
            if ST["running"]: ST["since"] = time.time()
            (shizuku.STOP.clear if ST["running"] else shizuku.STOP.set)(); log("تشغيل" if ST["running"] else "إيقاف")
        elif self.path == "/api/runnow":
            if d["key"] in PEND: log("المهمة قيد الانتظار أصلاً: " + d["key"])
            else: PEND.add(d["key"]); shizuku.STOP.clear(); threading.Thread(target=run_task, args=(d["key"], True), daemon=True).start()
        elif self.path == "/api/vd":
            a = d.get("action")
            if a in ("on", "off"):
                S["vdisplay"] = a == "on"; VDS["retry"] = 0; save(); log("الشاشة الثانوية (تجريبي): " + ("تفعيل" if a == "on" else "إيقاف"))
            elif a == "test" and not VDS["busy"]: threading.Thread(target=_vd_job, args=(_vd_test,), daemon=True).start()
        elif self.path == "/api/clearlog": LOGS.clear(); log("حُذف السجل")
        elif self.path == "/api/tap": shizuku.tap(d["x"], d["y"], False); log("نقر %s,%s" % (d["x"], d["y"]))
        self.send({"ok": True})

if __name__ == "__main__":
    shizuku.GAME[0] = S.get("game_pkg") or guard.PKG; shizuku.CHECK[0] = bool(S.get("game_only", True))
    threading.Thread(target=loop, daemon=True).start()
    log("اللوحة %s تعمل على المنفذ %d" % (VERSION, S["port"]))
    ThreadingHTTPServer(("0.0.0.0", int(S["port"])), H).serve_forever()
