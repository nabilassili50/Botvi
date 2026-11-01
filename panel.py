"""لوحة تحكم بالبوت (متصفح الهاتف). بدون أي مكتبات إضافية.

    python panel.py                  # ثم افتح في المتصفح:  http://localhost:8080
    python panel.py --port 9000
    python panel.py --host 0.0.0.0 --token سر   # للوصول من جهاز آخر في نفس الشبكة: http://IP:8080/?t=سر

تشغّل البوت وتوقفه كعملية خلفية (نفس ملفات bot.sh: runs/bot.pid و runs/out.log)،
فيمكنك المزج بين اللوحة وأوامر bot.sh بلا تعارض.
"""
import argparse
import glob
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
if "com.termux" in os.environ.get("PREFIX", "") or os.path.isdir("/data/data/com.termux"):
    os.environ.setdefault("LORDS_BACKEND", "rish")
    os.environ.setdefault("RISH_APPLICATION_ID", "com.termux")

import config  # noqa: E402
import positions  # noqa: E402

RUNS = config.OUTPUT_DIR
PIDF = os.path.join(RUNS, "bot.pid")
OUTF = os.path.join(RUNS, "out.log")
LOGF = os.path.join(RUNS, "bot.log")
STATF = os.path.join(RUNS, "stats.json")
PANELF = os.path.join(RUNS, "panel.json")
SETF = os.path.join(ROOT, "settings.json")
os.makedirs(RUNS, exist_ok=True)

TOKEN = ""
_lock = threading.Lock()
_dev = None
_started_at = None


# ---------------- أدوات ----------------
def read_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def tail(path, n=80):
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 40000))
            data = f.read().decode("utf-8", errors="ignore")
        return data.splitlines()[-n:]
    except OSError:
        return []


def bot_pid():
    try:
        pid = int(open(PIDF).read().strip())
        os.kill(pid, 0)
        # تأكد أنها عملية البوت فعلاً (قد يعاد استعمال الرقم)
        try:
            cmd = open(f"/proc/{pid}/cmdline", "rb").read().decode(errors="ignore")
            if "bot.py" not in cmd:
                return None
        except OSError:
            pass
        return pid
    except (OSError, ValueError):
        return None


def proc_state(pid):
    try:
        return open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()[0]
    except (OSError, IndexError):
        return "?"


def signal_bot(sig):
    pid = bot_pid()
    if not pid:
        raise ValueError("البوت غير شغّال")
    try:
        os.killpg(os.getpgid(pid), sig)
    except OSError:
        os.kill(pid, sig)


def clear_logs():
    for f in (LOGF, LOGF + ".old", OUTF):
        try:
            open(f, "w").close()
        except OSError:
            pass


def proc_start_time(pid):
    try:
        return os.stat(f"/proc/{pid}").st_mtime
    except OSError:
        return None


def get_dev():
    global _dev
    if _dev is None:
        from device import Device
        _dev = Device(None)
    return _dev


# ---------------- الإعدادات ----------------
SKIP = {"SERIAL", "PACKAGE", "BACKEND", "TEMPLATES_DIR", "OUTPUT_DIR", "DEBUG"}
GROUPS = [
    ("الصيد", ["HUNT_WAIT", "HUNT_RETRIES", "HUNT_RETRY_WAIT", "HUNT_MAX_MARCHES", "ENERGY_RETRY_SEC", "MONSTER_NEAR_PX"]),
    ("الجمع", ["GATHER_MAX_MARCHES", "ZONE_SWIPES", "SWIPE_FRAC", "SWIPE_MS", "ZONE_SETTLE", "NODE_THRESHOLD", "NODE_BADGE_DIST", "RESOURCE"]),
    ("الجولات والقلعة", ["LOOP_PAUSE", "CASTLE_EVERY_SEC", "MAX_FAILS", "STEP_TIMEOUT", "UI_THRESHOLD",
                         "AUTO_RELAUNCH", "RESTART_AFTER_IDLE_ROUNDS", "LOAD_WAIT"]),
]


def setting_comments():
    out = {}
    try:
        for line in open(os.path.join(ROOT, "config.py"), encoding="utf-8"):
            m = re.match(r"^([A-Z][A-Z0-9_]*)\s*=\s*[^#]*#\s*(.+)$", line.rstrip())
            if m:
                out[m.group(1)] = m.group(2).strip()
    except OSError:
        pass
    return out


def settings_schema():
    over = read_json(SETF, {})
    desc = setting_comments()
    items = {}
    for k in dir(config):
        if not k.isupper() or k in SKIP:
            continue
        v = getattr(config, k)
        if isinstance(v, (bool, int, float, str)):
            items[k] = {"key": k, "value": over.get(k, v), "type": "bool" if isinstance(v, bool) else
                        "int" if isinstance(v, int) else "float" if isinstance(v, float) else "str",
                        "desc": desc.get(k, ""), "changed": k in over}
    used, groups = set(), []
    for name, keys in GROUPS:
        g = [items[k] for k in keys if k in items]
        used.update(k for k in keys if k in items)
        groups.append({"name": name, "items": g})
    rest = [v for k, v in items.items() if k not in used]
    if rest:
        groups.append({"name": "أخرى", "items": rest})
    return groups


def save_setting(key, raw):
    if (key in SKIP and key != "DEBUG") or not hasattr(config, key):
        raise ValueError(f"إعداد مجهول: {key}")
    cur = getattr(config, key)
    over = read_json(SETF, {})
    if raw is None:                      # إعادة للافتراضي
        over.pop(key, None)
    else:
        if isinstance(cur, bool):
            val = raw if isinstance(raw, bool) else str(raw).lower() in ("1", "true", "yes", "on")
        elif isinstance(cur, int):
            val = int(float(raw))
        elif isinstance(cur, float):
            val = float(raw)
        else:
            val = str(raw)
        over[key] = val
    write_json(SETF, over)


# ---------------- تشغيل/إيقاف البوت ----------------
def start_bot(opts):
    rec = read_json(os.path.join(ROOT, "recorded_flows.json"), {}) or {}
    tasks = [t for t in opts.get("tasks", []) if t in ("castle", "hunt", "gather", "saga", "arena", "hunt_search") or t in rec]
    if not tasks:
        raise ValueError("اختر مهمة واحدة على الأقل")
    cmd = [sys.executable, "bot.py", "--task", ",".join(tasks)]
    res = opts.get("resource")
    if res and "gather" in tasks:
        if res not in ("ore", "wood", "food", "stone", "gold"):
            raise ValueError("مورد غير صالح")
        cmd += ["--resource", res]
    lvl = int(opts.get("level") or 0)
    if lvl:
        if lvl not in range(1, 6):
            raise ValueError("المستوى بين 1 و5")
        cmd += ["--level", str(lvl)]
    if opts.get("loop", True):
        cmd.append("--loop")
    if opts.get("no_launch"):
        cmd.append("--no-launch")
    with _lock:
        stop_bot()
        out = open(OUTF, "ab")
        p = subprocess.Popen(cmd, cwd=ROOT, stdout=out, stderr=subprocess.STDOUT,
                             stdin=subprocess.DEVNULL, start_new_session=True)
        with open(PIDF, "w") as f:
            f.write(str(p.pid))
        write_json(PANELF, {k: opts.get(k) for k in ("tasks", "resource", "level", "loop", "no_launch")})
        subprocess.run(["termux-wake-lock"], capture_output=True) if _has("termux-wake-lock") else None
    return " ".join(cmd[1:])


def _has(cmd):
    from shutil import which
    return which(cmd) is not None


def stop_bot():
    pid = bot_pid()
    if pid:
        try:
            os.killpg(os.getpgid(pid), signal.SIGCONT)
        except OSError:
            pass
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except OSError:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
        for _ in range(20):
            if not bot_pid():
                break
            time.sleep(0.1)
        if bot_pid():
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
    try:
        os.remove(PIDF)
    except OSError:
        pass
    if _has("termux-wake-unlock"):
        subprocess.run(["termux-wake-unlock"], capture_output=True)


# ---------------- الحالة ----------------
def status():
    pid = bot_pid()
    st = read_json(STATF, {})
    info = {
        "running": bool(pid),
        "paused": bool(pid) and proc_state(pid) == "T",
        "pid": pid,
        "uptime": int(time.time() - proc_start_time(pid)) if pid and proc_start_time(pid) else None,
        "log": tail(LOGF, 60) or tail(OUTF, 30),
        "stats": st,
        "last": read_json(PANELF, {"tasks": ["hunt"], "resource": "stone", "level": 4, "loop": True}),
        "debug": bool(read_json(SETF, {}).get("DEBUG", config.DEBUG)),
        "backend": config.BACKEND,
        "debug_shots": len(glob.glob(os.path.join(RUNS, "debug", "*.jpg"))),
    }
    if not pid:
        info["crash"] = [l for l in tail(OUTF, 8) if "Traceback" in l or "Error" in l or "error" in l][-3:]
    return info


def run_check(opts):
    tasks = ",".join(opts.get("tasks") or ["castle", "hunt", "gather"])
    cmd = [sys.executable, "bot.py", "--check", "--task", tasks]
    if opts.get("resource"):
        cmd += ["--resource", opts["resource"]]
    if opts.get("level"):
        cmd += ["--level", str(int(opts["level"]))]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, timeout=60)
    return (r.stdout + r.stderr).decode(errors="ignore")


def screenshot_jpeg(width=900):
    import cv2
    img = get_dev().screenshot()
    h, w = img.shape[:2]
    if w > width:
        img = cv2.resize(img, (width, int(h * width / w)))
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 65])
    return buf.tobytes()


RAWF = os.path.join(RUNS, "castle_raw.png")
LATESTJ = os.path.join(RUNS, "latest.json")
LATESTP = os.path.join(RUNS, "latest.png")
NAME_RE = re.compile(r"^[\w\u0600-\u06FF][\w\u0600-\u06FF \-]{0,40}$")


def template_counts():
    root = os.path.join(ROOT, config.TEMPLATES_DIR)
    out = {}
    if os.path.isdir(root):
        for n in sorted(os.listdir(root)):
            d = os.path.join(root, n)
            if os.path.isdir(d):
                out[n] = len([f for f in os.listdir(d) if f.lower().endswith((".png", ".jpg", ".jpeg"))])
    return out


def castle_action(mode):
    if bot_pid():
        raise ValueError("أوقف البوت أولاً")
    if mode == "grab":
        import cv2
        cv2.imwrite(RAWF, get_dev().screenshot())
        return "التُقطت الشاشة الحالية"
    flag = {"detect": "--detect", "zoom": "--zoom"}[mode]
    r = subprocess.run([sys.executable, "bot.py", flag], cwd=ROOT, capture_output=True, timeout=300)
    out = (r.stdout + r.stderr).decode(errors="ignore").strip().splitlines()
    if r.returncode != 0:
        raise ValueError("\n".join(out[-4:]) or "فشل")
    return out[-1] if out else "تم"


def redetect(threshold=None):
    import cv2
    from vision import annotate, detect_buildings, load_templates
    if not os.path.exists(RAWF):
        raise ValueError("لا توجد لقطة للقلعة بعد")
    img = cv2.imread(RAWF)
    b, _ = load_templates(os.path.join(ROOT, config.TEMPLATES_DIR))
    found = detect_buildings(img, b, threshold=float(threshold) if threshold else None)
    h, w = img.shape[:2]
    res = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"), "resolution": [w, h], "buildings": found,
           "missing": sorted(set(b) - {f["name"] for f in found})}
    write_json(LATESTJ, res)
    cv2.imwrite(LATESTP, annotate(img, found))
    return res


def save_template(name, x1, y1, x2, y2, ui=False):
    import cv2
    if not NAME_RE.match(name or ""):
        raise ValueError("اسم غير صالح (حروف وأرقام ومسافة وشرطة فقط)")
    img = cv2.imread(RAWF)
    if img is None:
        raise ValueError("لا توجد لقطة للقلعة")
    h, w = img.shape[:2]
    xa, xb = sorted((int(x1 * w), int(x2 * w)))
    ya, yb = sorted((int(y1 * h), int(y2 * h)))
    xa, ya, xb, yb = max(0, xa), max(0, ya), min(w, xb), min(h, yb)
    if xb - xa < 16 or yb - ya < 16:
        raise ValueError("المستطيل صغير جداً (16 بكسل على الأقل)")
    name = name.strip().lstrip("_")
    d = os.path.join(ROOT, config.TEMPLATES_DIR, ("_" if ui else "") + name)
    os.makedirs(d, exist_ok=True)
    n = len([f for f in os.listdir(d) if f.endswith(".png")]) + 1
    cv2.imwrite(os.path.join(d, f"{name}_{n}.png"), img[ya:yb, xa:xb])
    return n


def save_position(name, x1, y1, x2, y2):
    if not NAME_RE.match(name or ""):
        raise ValueError("اسم غير صالح (حروف وأرقام ومسافة وشرطة فقط)")
    positions.save(name.strip().lstrip("_").replace(" ", "_"), (x1 + x2) / 2, (y1 + y2) / 2)


def delete_template(name):
    import shutil
    if not NAME_RE.match(name or ""):
        raise ValueError("اسم غير صالح")
    shutil.rmtree(os.path.join(ROOT, config.TEMPLATES_DIR, name), ignore_errors=True)


def game_size(d):
    w, h = d.size()
    return (h, w) if w < h else (w, h)      # اللعبة أفقية حتى لو كانت الشاشة عمودية (نفس منطق tasks.py)


def device_action(a):
    d = get_dev()
    if a["do"] == "tap":
        w, h = game_size(d)
        d.tap(int(float(a["fx"]) * w), int(float(a["fy"]) * h))
    elif a["do"] == "back":
        d.back()
    elif a["do"] == "launch":
        d.launch()
    elif a["do"] == "kill":
        d.stop()
    elif a["do"] == "swipe":
        w, h = game_size(d)
        d.swipe(*[int(float(a[k]) * s) for k, s in (("x1", w), ("y1", h), ("x2", w), ("y2", h))])
    else:
        raise ValueError("إجراء مجهول")


# ---------------- HTTP ----------------
class H(BaseHTTPRequestHandler):
    server_version = "BotPanel"

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _auth(self, write=False):
        host = (self.headers.get("Host") or "").split(":")[0]
        if not TOKEN and host not in ("localhost", "127.0.0.1", "[::1]"):
            self._send(403, {"error": "host"})          # حماية من DNS rebinding
            return False
        if TOKEN and self.headers.get("X-Token") != TOKEN and parse_qs(urlparse(self.path).query).get("t", [""])[0] != TOKEN:
            self._send(401, {"error": "token"})
            return False
        if write and self.headers.get("X-Panel") != "1":
            self._send(403, {"error": "csrf"})
            return False
        return True

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            if TOKEN and parse_qs(u.query).get("t", [""])[0] != TOKEN:
                return self._send(401, "token required", "text/plain")
            return self._send(200, PAGE.replace("__TOKEN__", TOKEN), "text/html; charset=utf-8")
        if not self._auth():
            return
        try:
            if u.path == "/api/status":
                self._send(200, status())
            elif u.path == "/api/settings":
                self._send(200, settings_schema())
            elif u.path == "/api/shot":
                self._send(200, screenshot_jpeg(), "image/jpeg")
            elif u.path == "/api/buildings":
                self._send(200, {"result": read_json(LATESTJ, None), "templates": template_counts(), "positions": positions.load(),
                                 "has_raw": os.path.exists(RAWF), "threshold": config.MATCH_THRESHOLD,
                                 "raw_t": int(os.path.getmtime(RAWF)) if os.path.exists(RAWF) else 0})
            elif u.path == "/api/castle_img":
                f = LATESTP if parse_qs(u.query).get("k", ["raw"])[0] == "ann" and os.path.exists(LATESTP) else RAWF
                with open(f, "rb") as fh:
                    self._send(200, fh.read(), "image/png")
            elif u.path == "/api/debug_list":
                d = os.path.join(RUNS, "debug")
                names = sorted(os.listdir(d), reverse=True)[:40] if os.path.isdir(d) else []
                self._send(200, {"names": names})
            elif u.path == "/api/debug_img":
                n = os.path.basename(parse_qs(u.query).get("n", [""])[0])
                with open(os.path.join(RUNS, "debug", n), "rb") as f:
                    self._send(200, f.read(), "image/jpeg")
            elif u.path == "/api/fulllog":
                self._send(200, {"lines": tail(LOGF, 600) or tail(OUTF, 300)})
            else:
                self._send(404, {"error": "not found"})
        except Exception as e:  # noqa: BLE001
            self._send(500, {"error": str(e)})

    def do_POST(self):
        if not self._auth(write=True):
            return
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
            p = urlparse(self.path).path
            if p == "/api/start":
                self._send(200, {"ok": True, "cmd": start_bot(body)})
            elif p == "/api/stop":
                with _lock:
                    stop_bot()
                self._send(200, {"ok": True})
            elif p == "/api/castle":
                self._send(200, {"msg": castle_action(body["mode"])})
            elif p == "/api/redetect":
                self._send(200, redetect(body.get("threshold")))
            elif p == "/api/template":
                n = save_template(body["name"], body["x1"], body["y1"], body["x2"], body["y2"], bool(body.get("ui")))
                self._send(200, {"ok": True, "count": n})
            elif p == "/api/position":
                save_position(body["name"], body["x1"], body["y1"], body["x2"], body["y2"])
                self._send(200, {"ok": True})
            elif p == "/api/position_delete":
                positions.delete(body["name"])
                self._send(200, {"ok": True})
            elif p == "/api/template_delete":
                delete_template(body["name"])
                self._send(200, {"ok": True})
            elif p == "/api/pause":
                signal_bot(signal.SIGSTOP)
                self._send(200, {"ok": True})
            elif p == "/api/resume":
                signal_bot(signal.SIGCONT)
                self._send(200, {"ok": True})
            elif p == "/api/clear_log":
                clear_logs()
                self._send(200, {"ok": True})
            elif p == "/api/setting":
                save_setting(body["key"], body.get("value"))
                self._send(200, {"ok": True})
            elif p == "/api/debug":
                save_setting("DEBUG", bool(body.get("on")))
                self._send(200, {"ok": True})
            elif p == "/api/clear_debug":
                for f in glob.glob(os.path.join(RUNS, "debug", "*.jpg")):
                    os.remove(f)
                self._send(200, {"ok": True})
            elif p == "/api/reset_stats":
                write_json(STATF, {})
                self._send(200, {"ok": True})
            elif p == "/api/check":
                self._send(200, {"text": run_check(body)})
            elif p == "/api/device":
                device_action(body)
                self._send(200, {"ok": True})
            else:
                self._send(404, {"error": "not found"})
        except Exception as e:  # noqa: BLE001
            self._send(400, {"error": str(e)})


PAGE = r"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta id="vp" name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>لوحة تحكم البوت</title>
<style>
:root{--bg:#0f1419;--card:#1a2230;--card2:#222c3d;--tx:#e8edf5;--mut:#8a97ab;--ac:#4f9cff;--ok:#38c172;--bad:#ef5350;--warn:#f5a524;--bd:#2c3850}
[hidden]{display:none!important}
*{box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body.desk{max-width:1240px;font-size:14px}
.wrap{display:block}
body.desk .wrap{display:grid;grid-template-columns:330px minmax(0,1fr) 400px;gap:12px;align-items:start}
body.desk #log{height:calc(100vh - 150px);min-height:420px}
body.desk .card{margin-bottom:12px}
.col{min-width:0}
.bgrid{display:block}
body.desk .bgrid{display:grid;grid-template-columns:minmax(0,1fr) 380px;gap:12px;align-items:start}
#bview .card{margin-bottom:12px}
body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.5 system-ui,"Segoe UI",Tahoma,sans-serif;padding:12px 14px 80px;max-width:720px;margin-inline:auto}
h1{font-size:18px;margin:4px 0 12px;display:flex;align-items:center;gap:8px}
.card{background:var(--card);border:1px solid var(--bd);border-radius:14px;padding:14px;margin-bottom:12px}
.card h2{font-size:14px;color:var(--mut);margin:0 0 10px;font-weight:600}
.row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.dot{width:12px;height:12px;border-radius:50%;background:var(--bad);flex:none}
.dot.on{background:var(--ok);box-shadow:0 0 0 4px #38c17233;animation:p 1.6s infinite}
@keyframes p{50%{box-shadow:0 0 0 8px #38c17200}}
.big{font-size:20px;font-weight:700}
.sub{color:var(--mut);font-size:13px}
button{font:inherit;color:var(--tx);background:var(--card2);border:1px solid var(--bd);border-radius:10px;padding:10px 14px;cursor:pointer;min-height:44px}
button:active{transform:scale(.97)}
button.primary{background:var(--ok);border-color:var(--ok);color:#04210f;font-weight:700}
button.danger{background:var(--bad);border-color:var(--bad);color:#fff;font-weight:700}
button.sm{padding:6px 10px;min-height:34px;font-size:13px}
button:disabled{opacity:.45}
.chip{padding:9px 14px;border-radius:999px;background:var(--card2);border:1px solid var(--bd);cursor:pointer;user-select:none}
.chip.sel{background:var(--ac);border-color:var(--ac);color:#031629;font-weight:700}
select,input[type=number],input[type=text]{font:inherit;color:var(--tx);background:var(--card2);border:1px solid var(--bd);border-radius:10px;padding:9px 10px;min-height:42px}
label.t{display:flex;align-items:center;gap:8px;cursor:pointer}
input[type=checkbox]{width:20px;height:20px;accent-color:var(--ac)}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.field{display:flex;flex-direction:column;gap:4px}
.field span{font-size:12px;color:var(--mut)}
#log{background:#0a0e13;border-radius:10px;padding:10px;height:260px;overflow:auto;font:12px/1.55 ui-monospace,Menlo,Consolas,monospace;direction:ltr;text-align:left;white-space:pre-wrap;word-break:break-word}
#log .e{color:var(--bad)}#log .w{color:var(--warn)}#log .g{color:var(--ok)}
.stat{display:flex;gap:10px;flex-wrap:wrap}
.stat div{flex:1;min-width:90px;background:var(--card2);border-radius:10px;padding:8px 10px}
.stat b{display:block;font-size:20px}
.set{border-top:1px solid var(--bd);padding:10px 0}
.set:first-child{border-top:0}
.set .k{font:12px ui-monospace,monospace;color:var(--ac);direction:ltr;text-align:right}
.set .d{font-size:12px;color:var(--mut);margin:2px 0 6px}
.set .ctl{display:flex;gap:8px;align-items:center}
.set input[type=number],.set input[type=text]{flex:1;min-width:0}
.mod{color:var(--warn)}
details>summary{cursor:pointer;font-weight:600;padding:6px 0;list-style:none}
details>summary::before{content:"◂ ";color:var(--mut)}details[open]>summary::before{content:"▾ "}
#shotwrap{position:relative;direction:ltr}
#shot{width:100%;border-radius:10px;display:block;background:#000;cursor:crosshair}
#toast{position:fixed;bottom:16px;left:50%;transform:translateX(-50%);background:#000c;color:#fff;padding:10px 18px;border-radius:999px;opacity:0;transition:.25s;pointer-events:none;max-width:90%;text-align:center;z-index:9}
#toast.show{opacity:1}
pre.out{background:#0a0e13;border-radius:10px;padding:10px;font:12px/1.5 ui-monospace,monospace;direction:rtl;white-space:pre-wrap;margin:8px 0 0}
</style>
</head>
<body>
<h1 style="justify-content:space-between"><span>🤖 لوحة تحكم البوت</span><button class="sm" id="layoutBtn" onclick="toggleLayout()">🖥 عرض الحاسوب</button></h1>
<div class="row" style="margin-bottom:12px"><span class="chip sel" id="tabC" onclick="tab('c')">🎛 التحكم</span><span class="chip" id="tabB" onclick="tab('b')">🏰 المباني</span></div>
<div class="wrap" id="mainView"><div class="col" id="colA">

<div class="card" id="statusCard">
  <div class="row" style="justify-content:space-between">
    <div class="row"><span class="dot" id="dot"></span>
      <div><div class="big" id="stTxt">…</div><div class="sub" id="stSub"></div></div></div>
  </div>
  <div class="row" style="margin-top:12px">
    <button class="primary" id="startBtn" onclick="start()" style="flex:1">▶ تشغيل</button>
    <button id="pauseBtn" onclick="pauseResume()" style="flex:1">⏸ تعليق</button>
    <button class="danger" id="stopBtn" onclick="stop()" style="flex:1">⏹ إيقاف</button>
  </div>
  <div id="crash" class="sub" style="color:var(--bad);margin-top:8px;direction:ltr;text-align:left"></div>
</div>

<div class="card">
  <h2>تشغيل</h2>
  <div class="row" id="tasks" style="margin-bottom:12px">
    <span class="chip" data-t="castle">🏰 القلعة</span>
    <span class="chip" data-t="hunt">🗡 الصيد</span>
    <span class="chip" data-t="gather">⛏ الجمع</span>
    <span class="chip" data-t="saga">📜 الملحمة</span>
    <span class="chip" data-t="arena">⚔️ ميدان الأبطال</span>
    <span class="chip" id="allChip" style="border-style:dashed">⚡ الكل</span>
  </div>
  <div class="grid" style="margin-bottom:12px">
    <div class="field"><span>مورد الجمع</span>
      <select id="res"><option value="stone">حجر</option><option value="food">طعام</option><option value="wood">خشب</option><option value="ore">خام</option><option value="gold">ذهب</option></select></div>
    <div class="field"><span>مستوى المنطقة</span>
      <select id="lvl"><option value="0">بدون (بحث عادي)</option><option>1</option><option>2</option><option>3</option><option>4</option><option>5</option></select></div>
  </div>
  <div class="row" style="margin-bottom:14px;gap:18px">
    <label class="t"><input type="checkbox" id="loop" checked> تكرار مستمر</label>
    <label class="t"><input type="checkbox" id="nolaunch"> اللعبة مفتوحة (لا تشغّلها)</label>
  </div>
  <div class="row" style="margin-top:10px">
    <button class="sm" onclick="check()">🔍 فحص القوالب الناقصة</button>
  </div>
  <pre class="out" id="checkOut" hidden></pre>
</div>

</div><div class="col" id="colB"><div class="card">
  <div class="row" style="justify-content:space-between;margin-bottom:8px">
    <h2 style="margin:0">السجل المباشر</h2>
    <div class="row"><label class="t sub"><input type="checkbox" id="follow" checked> متابعة</label>
    <button class="sm" onclick="copyLog()">📋 نسخ</button><button class="sm" onclick="clearLog()">🗑 مسح</button></div>
  </div>
  <div id="log"></div>
</div>

</div><div class="col" id="colC"><div class="card">
  <div class="row" style="justify-content:space-between;margin-bottom:8px">
    <h2 style="margin:0">الإحصائيات</h2>
    <button class="sm" onclick="resetStats()">تصفير</button>
  </div>
  <div class="stat" id="stats"></div>
</div>

<div class="card">
  <h2>الشاشة والتحكم اليدوي</h2>
  <div class="row" style="margin-bottom:10px">
    <button class="sm" onclick="shot()">📸 التقاط</button>
    <label class="t sub"><input type="checkbox" id="auto"> تحديث تلقائي (3ث)</label>
    <button class="sm" onclick="dev({do:'back'})">↩ رجوع</button>
    <button class="sm" onclick="dev({do:'launch'})">🎮 شغّل اللعبة</button>
    <button class="sm" onclick="if(confirm('إغلاق اللعبة بالقوة؟'))dev({do:'kill'})">✖ أغلق اللعبة</button>
  </div>
  <div id="shotwrap"><img id="shot" alt="" hidden></div>
  <div class="sub" style="margin-top:6px">اضغط على الصورة لتنفيذ ضغطة في نفس المكان على الهاتف. يعمل أيضاً أثناء تشغيل البوت، لكن تجنّب ذلك حتى لا تتعارض مع خطواته.</div>
  <div class="row" style="margin-top:10px">
    <label class="t"><input type="checkbox" id="debug" onchange="setDebug(this.checked)"> وضع التشخيص (يحفظ صوراً بما يراه البوت)</label>
  </div>
  <div class="sub" id="dbgInfo"></div>
</div>

<div class="card">
  <div class="row" style="justify-content:space-between;margin-bottom:6px">
    <h2 style="margin:0">ما رآه البوت (التشخيص)</h2>
    <button class="sm" onclick="loadDbg()">↻ تحديث</button>
  </div>
  <div class="sub" style="margin-bottom:8px">فعّل «وضع التشخيص» ثم شغّل البوت. الدائرة <b style="color:#0ff">الصفراء</b> وحش مكتشف، <b style="color:#0c0">الخضراء</b> عقدة، <b style="color:#48f">الزرقاء</b> شارة مستوى، <b style="color:#f44">الحمراء</b> ما اختاره. الاسم <code>monster-none</code> يعني أنه لم يجد شيئاً.</div>
  <div id="dbgList" class="row" style="gap:6px"></div>
  <img id="dbgBig" alt="" hidden style="width:100%;border-radius:10px;margin-top:8px;direction:ltr">
</div>

<div class="card">
  <h2>الإعدادات <span class="sub">(تُطبَّق عند التشغيل التالي)</span></h2>
  <div id="settings"></div>
</div>

</div></div>

<div id="bview" hidden>
  <div class="card">
    <h2>١) تصغير القلعة والتقاط شاشتها</h2>
    <div class="row">
      <button class="primary" onclick="castle('detect')">🔍 صغّر القلعة واكتشف المباني</button>
      <button onclick="castle('zoom')">🔎 تصغير فقط</button>
      <button onclick="castle('grab')">📸 التقط الشاشة الحالية</button>
    </div>
    <div class="sub" style="margin-top:8px">افتح اللعبة على القلعة أولاً (داخل المدينة). التصغير يستغرق نحو دقيقة. إن صغّرت يدوياً فاستعمل «التقط الشاشة الحالية». يتطلب إيقاف البوت.</div>
    <div id="castleMsg" class="sub" style="margin-top:6px;color:var(--warn)"></div>
  </div>

  <div class="bgrid">
  <div class="card">
    <div class="row" style="justify-content:space-between;margin-bottom:8px">
      <h2 style="margin:0">٢) حدّد كل مبنى بالسحب عليه ثم سمّه</h2>
      <div class="row">
        <span class="chip sel" id="vRaw" onclick="bview('raw')">الخام (للقص)</span>
        <span class="chip" id="vAnn" onclick="bview('ann')">المكتشف</span>
      </div>
    </div>
    <div id="cwrap" style="position:relative;direction:ltr;touch-action:none;user-select:none">
      <img id="cimg" alt="" style="width:100%;display:block;border-radius:10px;background:#000" hidden draggable="false">
      <div id="sel" style="position:absolute;border:2px solid #ff0;background:#ff02;display:none;pointer-events:none"></div>
    </div>
    <div class="sub" id="cempty">لا توجد لقطة بعد. اضغط أحد الأزرار أعلاه.</div>
    <div class="row" id="saveRow" style="margin-top:10px" hidden>
      <input type="text" id="tname" list="tnames" placeholder="اسم المبنى (مثل: barracks)" style="flex:1;min-width:160px">
      <datalist id="tnames"></datalist>
      <label class="t sub"><input type="checkbox" id="tui"> قالب واجهة (زر/نافذة، وليس مبنى)</label>
      <label class="t sub"><input type="checkbox" id="tpt"> نقطة فقط (بدون قالب)</label>
      <button class="primary" onclick="saveTpl()">💾 احفظ كقالب</button>
    </div>
    <div class="sub" style="margin-top:8px">اقصّ جسم المبنى فقط، وتجنّب علامة «!» الحمراء وشارة المستوى لأنها تتغير. يمكنك حفظ أكثر من قالب لنفس الاسم لاختلاف الشكل.</div>
  </div>

  <div>
    <div class="card">
      <h2>٣) الكشف</h2>
      <div class="row" style="margin-bottom:8px">
        <label class="sub">حد التطابق <input type="number" id="thr" step="0.01" min="0.3" max="1" style="width:90px"></label>
        <button class="primary sm" onclick="redetect()">♻ اكشف على هذه اللقطة</button>
      </div>
      <div class="sub" id="detInfo"></div>
      <div id="found" style="margin-top:8px"></div>
    </div>
    <div class="card">
      <h2>القوالب المحفوظة</h2>
      <div id="tpls"></div>
    </div>
  </div>
  </div>
</div>
<div id="toast"></div>

<script>
const TOKEN="__TOKEN__";
const $=s=>document.querySelector(s);
const H={"Content-Type":"application/json","X-Panel":"1"};if(TOKEN)H["X-Token"]=TOKEN;
async function api(path,body){
  const r=await fetch(path,body===undefined?{headers:H}:{method:"POST",headers:H,body:JSON.stringify(body)});
  if(!r.ok){let m=r.status;try{m=(await r.json()).error||m}catch(e){}throw new Error(m)}
  return r;
}
async function j(path,body){return (await api(path,body)).json()}
function toast(m){const t=$("#toast");t.textContent=m;t.classList.add("show");clearTimeout(t._h);t._h=setTimeout(()=>t.classList.remove("show"),2400)}
function fmt(s){if(s==null)return"";const h=Math.floor(s/3600),m=Math.floor(s%3600/60);return (h?h+" س ":"")+m+" د "+(s%60)+" ث"}
const NAMES={castle:"القلعة",hunt:"الصيد",gather:"الجمع",saga:"الملحمة",arena:"ميدان الأبطال"};

let sel=new Set(),inited=false,paused=false;
function paintChips(){document.querySelectorAll("#tasks .chip[data-t]").forEach(c=>c.classList.toggle("sel",sel.has(c.dataset.t)));
  $("#allChip").classList.toggle("sel",["castle","hunt","gather"].every(t=>sel.has(t)))}
document.querySelectorAll("#tasks .chip[data-t]").forEach(c=>c.onclick=()=>{const t=c.dataset.t;sel.has(t)?sel.delete(t):sel.add(t);paintChips()});
$("#allChip").onclick=()=>{const all=["castle","hunt","gather"];if(all.every(t=>sel.has(t)))all.forEach(t=>sel.delete(t));else all.forEach(t=>sel.add(t));paintChips()};

async function start(){
  if(!sel.size)return toast("اختر مهمة واحدة على الأقل");
  const order=["castle","hunt","gather","saga","arena"].filter(t=>sel.has(t));
  try{await j("/api/start",{tasks:order,resource:$("#res").value,level:+$("#lvl").value,loop:$("#loop").checked,no_launch:$("#nolaunch").checked});
    toast("بدأ التشغيل");refresh()}catch(e){toast("خطأ: "+e.message)}
}
async function stop(){try{await j("/api/stop",{});toast("تم الإيقاف");refresh()}catch(e){toast("خطأ: "+e.message)}}
async function check(){const o=$("#checkOut");o.hidden=false;o.textContent="…";
  try{const order=sel.size?[...sel]:["castle","hunt","gather","saga","arena"];
    o.textContent=(await j("/api/check",{tasks:order,resource:$("#res").value,level:+$("#lvl").value})).text||"لا شيء"}catch(e){o.textContent=e.message}}
async function pauseResume(){try{await j(paused?"/api/resume":"/api/pause",{});toast(paused?"استؤنف":"عُلّق");refresh()}catch(e){toast("خطأ: "+e.message)}}
async function clearLog(){if(!confirm("مسح السجل؟"))return;try{await j("/api/clear_log",{});toast("تم مسح السجل");refresh()}catch(e){toast(e.message)}}
async function copyLog(){
  let t="";try{t=(await j("/api/fulllog")).lines.join("\n")}catch(e){return toast("تعذّر جلب السجل")}
  if(!t)return toast("السجل فارغ");
  try{await navigator.clipboard.writeText(t)}catch(e){const a=document.createElement("textarea");a.value=t;document.body.appendChild(a);a.select();document.execCommand("copy");a.remove()}
  toast("تم نسخ السجل ("+t.split("\n").length+" سطر)");
}
function applyLayout(d){document.body.classList.toggle("desk",d);
  $("#vp").setAttribute("content",d?"width=1240":"width=device-width,initial-scale=1,viewport-fit=cover");
  $("#layoutBtn").textContent=d?"📱 عرض الهاتف":"🖥 عرض الحاسوب"}
function toggleLayout(){const d=!document.body.classList.contains("desk");try{localStorage.setItem("desk",d?"1":"0")}catch(e){}applyLayout(d)}
let _d=true;try{_d=localStorage.getItem("desk")!=="0"}catch(e){}applyLayout(_d);
async function resetStats(){if(confirm("تصفير الإحصائيات؟")){await j("/api/reset_stats",{});refresh()}}
async function setDebug(on){try{await j("/api/debug",{on});toast(on?"التشخيص مفعّل":"التشخيص متوقف")}catch(e){toast(e.message)}}
async function dev(a){try{await j("/api/device",a);toast("تم");if(a.do=="tap")setTimeout(shot,900)}catch(e){toast("خطأ: "+e.message)}}

async function shot(){
  try{const b=await (await api("/api/shot")).blob();const i=$("#shot");i.src=URL.createObjectURL(b);i.hidden=false}catch(e){toast("تعذّر الالتقاط: "+e.message)}
}
$("#shot").onclick=e=>{const r=e.target.getBoundingClientRect();dev({do:"tap",fx:(e.clientX-r.left)/r.width,fy:(e.clientY-r.top)/r.height})};
setInterval(()=>{if($("#auto").checked&&!document.hidden)shot()},3000);

function colorLog(lines){
  return lines.map(l=>{const c=/error|failed|Traceback|خطأ/i.test(l)?"e":/warn|تنبيه|missing|ناقص/i.test(l)?"w":/round:|detected|مات|تم/i.test(l)?"g":"";
    return `<div class="${c}">${l.replace(/[&<>]/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[m]))}</div>`}).join("")
}
async function refresh(){
  try{
    const s=await j("/api/status");
    $("#dot").classList.toggle("on",s.running);
    $("#stTxt").textContent=s.running?"يعمل":"متوقف";
    $("#stSub").textContent=s.running?`PID ${s.pid} · منذ ${fmt(s.uptime)}`:`الاتصال: ${s.backend}`;
    paused=s.paused;
    $("#dot").style.background=s.paused?"var(--warn)":"";
    if(s.paused)$("#stTxt").textContent="معلّق";
    $("#stopBtn").disabled=!s.running;$("#pauseBtn").disabled=!s.running;
    $("#pauseBtn").textContent=s.paused?"▶ استئناف":"⏸ تعليق";
    $("#startBtn").textContent=s.running?"↻ إعادة تشغيل":"▶ تشغيل";
    $("#crash").textContent=(s.crash||[]).join("\n");
    if(!inited){inited=true;sel=new Set(s.last.tasks||["hunt"]);paintChips();
      if(s.last.resource)$("#res").value=s.last.resource;$("#lvl").value=String(s.last.level||0);
      $("#loop").checked=s.last.loop!==false;$("#nolaunch").checked=!!s.last.no_launch;$("#debug").checked=s.debug}
    const lg=$("#log"),stick=$("#follow").checked;
    lg.innerHTML=colorLog(s.log);if(stick)lg.scrollTop=lg.scrollHeight;
    const m=(s.stats&&s.stats.marches)||{};
    $("#stats").innerHTML=`<div><b>${(s.stats&&s.stats.rounds)||0}</b><span class=sub>جولات</span></div>`+
      Object.keys(m).map(k=>`<div><b>${m[k]}</b><span class=sub>${NAMES[k]||k}</span></div>`).join("");
    $("#dbgInfo").innerHTML=s.debug_shots?`صور التشخيص المحفوظة: ${s.debug_shots} <a href="#" onclick="clearDbg();return false">حذفها</a>`:"";
  }catch(e){$("#stTxt").textContent="لا اتصال باللوحة";$("#dot").classList.remove("on")}
}
function tab(t){const b=t=="b";$("#mainView").hidden=b;$("#bview").hidden=!b;
  $("#tabB").classList.toggle("sel",b);$("#tabC").classList.toggle("sel",!b);if(b)loadB()}
let bmode="raw",rawT=0,rect=null;
function bview(m){bmode=m;$("#vRaw").classList.toggle("sel",m=="raw");$("#vAnn").classList.toggle("sel",m=="ann");showImg()}
function showImg(){const i=$("#cimg");if(!rawT){i.hidden=true;$("#cempty").hidden=false;return}
  $("#cempty").hidden=true;i.hidden=false;i.src="/api/castle_img?k="+bmode+"&v="+Date.now()+(TOKEN?"&t="+TOKEN:"");
  $("#sel").style.display="none";rect=null;$("#saveRow").hidden=true}
async function loadB(){
  try{const d=await j("/api/buildings");rawT=d.has_raw?d.raw_t:0;
    if(!$("#thr").value)$("#thr").value=d.threshold;
    const ent=Object.entries(d.templates),row=([n,c])=>`<div class="row" style="justify-content:space-between;border-top:1px solid var(--bd);padding:6px 0"><span>${n.replace(/^_/,"")} <span class="sub">(${c})</span></span><button class="sm" onclick="delTpl('${n}')">حذف</button></div>`;
    const bl=ent.filter(([n])=>!n.startsWith("_")),ul=ent.filter(([n])=>n.startsWith("_"));
    $("#tpls").innerHTML=(bl.length?`<div class="sub">المباني</div>`+bl.map(row).join(""):'<span class="sub">لا توجد قوالب مبانٍ بعد</span>')+(ul.length?`<div class="sub" style="margin-top:10px">الواجهة (أزرار ونوافذ)</div>`+ul.map(row).join(""):"")+(Object.keys(d.positions||{}).length?`<div class="sub" style="margin-top:10px">نقاط محفوظة (بدون قالب)</div>`+Object.entries(d.positions).map(([n,p])=>`<div class="row" style="justify-content:space-between;border-top:1px solid var(--bd);padding:6px 0"><span>${n} <span class="sub">(${p[0].toFixed(2)}, ${p[1].toFixed(2)})</span></span><button class="sm" onclick="delPos('${n}')">حذف</button></div>`).join(""):"");
    $("#tnames").innerHTML=bl.map(([n])=>`<option value="${n}">`).join("");
    const r=d.result;
    if(r){const f=r.buildings||[];
      $("#detInfo").innerHTML=`${f.length} مبنى مكتشف · ${r.timestamp.replace("T"," ")}`+(r.missing.length?`<br><span style="color:var(--warn)">لم تظهر: ${r.missing.join("، ")}</span>`:"");
      $("#found").innerHTML=f.map(b=>`<div class="row" style="justify-content:space-between;border-top:1px solid var(--bd);padding:5px 0"><b>${b.name}</b><span class="sub">(${b.cx}, ${b.cy}) · ${b.score}</span></div>`).join("")}
    else{$("#detInfo").textContent="لم يُجرَ كشف بعد";$("#found").innerHTML=""}
    showImg()}catch(e){toast(e.message)}}
async function castle(mode){const m=$("#castleMsg");m.textContent=mode=="grab"?"…":"جارٍ العمل، انتظر نحو دقيقة…";
  try{const r=await j("/api/castle",{mode});m.textContent="";toast(r.msg);bmode=mode=="detect"?"ann":"raw";bview(bmode);loadB()}catch(e){m.textContent="خطأ: "+e.message}}
async function redetect(){try{const r=await j("/api/redetect",{threshold:+$("#thr").value||null});toast(r.buildings.length+" مبنى");bmode="ann";bview("ann");loadB()}catch(e){toast(e.message)}}
async function saveTpl(){const n=$("#tname").value.trim();if(!n||!rect)return toast("حدّد المبنى واكتب اسمه");
  if($("#tpt").checked){try{await j("/api/position",{name:n,...rect});toast("حُفظت نقطة "+n);$("#sel").style.display="none";rect=null;$("#saveRow").hidden=true;loadB()}catch(e){toast(e.message)}return}
  try{const r=await j("/api/template",{name:n,...rect,ui:$("#tui").checked});toast(`حُفظ ${n} (القالب ${r.count})`);$("#sel").style.display="none";rect=null;$("#saveRow").hidden=true;loadB()}catch(e){toast(e.message)}}
async function delPos(n){if(confirm("حذف نقطة "+n+"؟")){await j("/api/position_delete",{name:n});loadB()}}
async function delTpl(n){if(confirm("حذف كل قوالب "+n+"؟")){await j("/api/template_delete",{name:n});loadB()}}
(function(){const w=$("#cwrap");let st=null;
  const pt=e=>{const r=$("#cimg").getBoundingClientRect();return[Math.min(1,Math.max(0,(e.clientX-r.left)/r.width)),Math.min(1,Math.max(0,(e.clientY-r.top)/r.height))]};
  w.addEventListener("pointerdown",e=>{if(bmode!="raw"||$("#cimg").hidden)return;w.setPointerCapture(e.pointerId);st=pt(e)});
  w.addEventListener("pointermove",e=>{if(!st)return;const c=pt(e),s=$("#sel");
    const x1=Math.min(st[0],c[0]),y1=Math.min(st[1],c[1]),x2=Math.max(st[0],c[0]),y2=Math.max(st[1],c[1]);
    Object.assign(s.style,{display:"block",left:x1*100+"%",top:y1*100+"%",width:(x2-x1)*100+"%",height:(y2-y1)*100+"%"});rect={x1,y1,x2,y2}});
  w.addEventListener("pointerup",()=>{if(st&&rect)$("#saveRow").hidden=false;st=null})})();
async function loadDbg(){
  try{const n=(await j("/api/debug_list")).names;
    $("#dbgList").innerHTML=n.length?n.map(x=>`<button class="sm" onclick="showDbg('${x}')">${x.replace(".jpg","")}</button>`).join(""):'<span class="sub">لا توجد صور بعد</span>';
    if(n.length)showDbg(n[0])}catch(e){toast(e.message)}}
async function showDbg(n){try{const b=await (await api("/api/debug_img?n="+encodeURIComponent(n))).blob();const i=$("#dbgBig");i.src=URL.createObjectURL(b);i.hidden=false}catch(e){toast(e.message)}}
async function clearDbg(){await j("/api/clear_debug",{});refresh();loadDbg()}
setInterval(()=>{if(!document.hidden)refresh()},2000);refresh();

async function loadSettings(){
  const g=await j("/api/settings");
  $("#settings").innerHTML=g.map(gr=>`<details ${gr.name=="الصيد"?"open":""}><summary>${gr.name}</summary>`+gr.items.map(it=>{
    const id="s_"+it.key;
    const inp=it.type=="bool"?`<input type="checkbox" id="${id}" ${it.value?"checked":""}>`:
      `<input ${it.type=="str"?'type="text"':'type="number" step="any"'} id="${id}" value="${it.value}">`;
    return `<div class="set"><div class="k ${it.changed?"mod":""}">${it.key}${it.changed?" ●":""}</div><div class="d">${it.desc||""}</div>
      <div class="ctl">${inp}<button class="sm" onclick="saveSet('${it.key}','${it.type}')">حفظ</button>
      ${it.changed?`<button class="sm" onclick="resetSet('${it.key}')">افتراضي</button>`:""}</div></div>`}).join("")+`</details>`).join("");
}
async function saveSet(k,t){const e=$("#s_"+k);const v=t=="bool"?e.checked:e.value;
  try{await j("/api/setting",{key:k,value:v});toast("حُفظ: "+k);loadSettings()}catch(x){toast("خطأ: "+x.message)}}
async function resetSet(k){await j("/api/setting",{key:k,value:null});toast("رجع للافتراضي");loadSettings()}
loadSettings();loadDbg();
</script>
</body>
</html>
"""


def main():
    global TOKEN
    ap = argparse.ArgumentParser(description="لوحة تحكم البوت")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--token", default="", help="مطلوب عند استعمال --host غير المحلي")
    a = ap.parse_args()
    if a.host not in ("127.0.0.1", "localhost") and not a.token:
        raise SystemExit("--host خارجي يتطلب --token لحماية اللوحة")
    TOKEN = a.token
    srv = ThreadingHTTPServer((a.host, a.port), H)
    q = f"/?t={TOKEN}" if TOKEN else ""
    print(f"اللوحة تعمل: http://{'localhost' if a.host == '127.0.0.1' else a.host}:{a.port}{q}\nCtrl+C للإيقاف", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
