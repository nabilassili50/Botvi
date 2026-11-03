import os, re, json, subprocess, threading, time
STOP = threading.Event()          # عند ضغط "إيقاف": أي أمر جديد يرمي استثناء فتتوقف المهمة الجارية فوراً
class Stopped(Exception): pass
class LeftGame(Stopped): pass     # غادر المستخدم اللعبة (مثلاً فتح المتصفح): تتوقف المهمة فوراً دون أي ضغط
os.environ.setdefault("RISH_APPLICATION_ID", "com.termux")
os.environ["PATH"] = os.environ.get("PATH", "") + ":" + os.path.expanduser("~/bin")      # rish يوضع في ~/bin: لا حاجة لـ export
FAST = {"on": True, "bad": 0}      # جلسة rish دائمة بدل عملية جديدة لكل أمر (أسرع بكثير)؛ تُعطَّل تلقائياً إن فشلت
SPEED = [1.0]                      # معامل سرعة الانتظارات: 1 = كما كان، 0.6 = أسرع (يضبطه settings.json: speed)
def nap(t):
    """بديل time.sleep للمهام: يضرب المدة بمعامل السرعة (مع حد أدنى صغير) ويتوقف فوراً عند الإيقاف"""
    t = max(0.15, t * SPEED[0]) if t > 0.2 else t
    end = time.time() + t
    while True:
        if STOP.is_set(): raise Stopped("stopped")
        r = end - time.time()
        if r <= 0: return
        time.sleep(min(r, 0.25))

class _Sess:
    """جلسة rish واحدة تبقى مفتوحة وتنفّذ الأوامر عبر stdin مع علامة نهاية"""
    def __init__(self):
        self.p = subprocess.Popen(["rish"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
        self.fd = self.p.stdout.fileno(); self.n = 0; self.buf = b""
        try: self.run("echo ready", 25)                      # تسخين: يبتلع أي رسالة ترحيب قبل أول أمر حقيقي
        except Exception: self.close(); raise
    def alive(self): return self.p.poll() is None
    def run(self, cmd, timeout):
        import select
        self.n += 1; mk = ("__BV_END_%d_%d__" % (os.getpid(), self.n)).encode()
        line = ("{ %s\n} < /dev/null 2>/dev/null; echo; echo %s\n" % (cmd, mk.decode())).encode()
        self.p.stdin.write(line); self.p.stdin.flush()
        out = self.buf; self.buf = b""; end = time.time() + timeout
        while mk not in out:
            r = end - time.time()
            if r <= 0 or not self.alive(): raise subprocess.TimeoutExpired("rish", timeout)
            if select.select([self.fd], [], [], min(r, 1.0))[0]:
                ch = os.read(self.fd, 65536)
                if not ch: raise subprocess.TimeoutExpired("rish", timeout)
                out += ch
        out, rest = out.split(mk, 1); self.buf = rest.lstrip(b"\n") if rest.strip() == b"" else rest
        return out[:-1] if out.endswith(b"\n") else out          # أزل السطر الفارغ الذي أضفناه قبل العلامة
    def close(self):
        try: self.p.kill()
        except Exception: pass

_POOL = []; _PL = threading.Lock(); _SESS_MAX = 3
def _get():
    with _PL:
        while _POOL:
            s = _POOL.pop()
            if s.alive(): return s
        return None
def _put(s):
    with _PL:
        if s.alive() and len(_POOL) < _SESS_MAX: _POOL.append(s); return
    s.close()
def reset_sessions():
    with _PL:
        for s in _POOL: s.close()
        _POOL.clear()

def _sh_fast(cmd, timeout):
    s = _get() or _Sess()
    try:
        out = s.run(cmd, timeout)
    except Exception:
        s.close(); raise
    _put(s); return out

def _sh_slow(cmd, binary, timeout):
    r = subprocess.run(["rish", "-c", cmd], capture_output=True, timeout=timeout)
    return r.stdout if binary else r.stdout.decode(errors="ignore")

def sh(cmd, binary=False, timeout=15, check=True):
    if check and STOP.is_set(): raise Stopped("stopped")
    if binary or not FAST["on"] or "\n" in cmd: return _sh_slow(cmd, binary, timeout)
    try:
        out = _sh_fast(cmd, timeout); FAST["bad"] = 0
        return out.decode(errors="ignore")
    except Exception:
        FAST["bad"] += 1                                        # فشلت الجلسة الدائمة: جرّب الطريقة القديمة، وعطّل السريعة بعد 3 إخفاقات متتالية
        if FAST["bad"] >= 3: FAST["on"] = False
        return _sh_slow(cmd, binary, timeout)
GAME = ["com.igg.android.lordsmobile"]; CHECK = [True]; _FG = [0.0, True]
VD = {"on": False, "id": 0, "cap": None, "size": (1280, 800), "fw": 1280}     # الشاشة الثانوية التجريبية (انظر vdisplay.py)
def _vd():
    import vdisplay; return vdisplay
def _k():
    """نسبة تحويل إحداثيات اللقطة (قد تكون مقصوصة وأصغر) إلى بكسلات الشاشة الثانوية الحقيقية"""
    return VD["size"][0] / float(VD["fw"] or VD["size"][0]) if VD["on"] else 1.0
def _d(): return ("-d %d " % VD["id"]) if VD["on"] else ""
def front(force=False):
    """هل اللعبة في الواجهة الآن؟ (مخزَّنة 1.5 ثانية لتخفيف dumpsys)"""
    if not force and time.time() - _FG[0] < 1.5: return _FG[1]
    if VD["on"]:
        try: v = _vd().front()
        except Exception: v = _FG[1]
        _FG[0] = time.time(); _FG[1] = v; return v
    out = sh("dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'", timeout=10, check=False)
    if out.strip(): v = GAME[0] in out
    else:
        o2 = sh("dumpsys activity activities | grep -E 'mResumedActivity|topResumedActivity'", timeout=10, check=False)
        v = (GAME[0] in o2) if o2.strip() else True          # تعذّرت القراءة: نفترض أننا داخل اللعبة
    _FG[0] = time.time(); _FG[1] = v; return v
def gate():
    if CHECK[0] and not front(): raise LeftGame("غادرت اللعبة")
def tap(x, y, g=True):
    if g: gate()
    k = _k(); sh(f"input {_d()}tap {int(x * k)} {int(y * k)}")
def swipe(x1, y1, x2, y2, ms=300): gate(); k = _k(); sh(f"input {_d()}swipe {int(x1 * k)} {int(y1 * k)} {int(x2 * k)} {int(y2 * k)} {ms}")
def key(code): gate(); sh(f"input {_d()}keyevent {code}")
SHOT = "/sdcard/.botvi_shot"      # الكتابة إلى ملف تتجنب إفساد البيانات الثنائية عبر rish
def screencap(check=True):
    if VD["on"]: return _vd().png("task", check)
    sh("screencap -p %s.png" % SHOT, timeout=25, check=check)
    return open(SHOT + ".png", "rb").read()
def panel_shot():
    """لقطة للوحة فقط (ملف مستقل كي لا تتعارض مع لقطات المهام)"""
    if VD["on"]: return _vd().png("panel", False)
    sh("screencap -p /sdcard/.botvi_panel.png", timeout=25, check=False)
    return open("/sdcard/.botvi_panel.png", "rb").read()
def ok():
    try: return sh("id", check=False).startswith("uid=")
    except Exception: return False

class Frame:
    """لقطة خام RGBA بدون مكتبات: الإحداثيات بمقياس 1280x800."""
    def __init__(self, raw):
        self.w = int.from_bytes(raw[0:4], "little"); self.h = int.from_bytes(raw[4:8], "little")
        self.off = len(raw) - self.w * self.h * 4; self.raw = raw; self.s = self.w / 1280.0
    def px(self, x, y):
        i = self.off + (int(y * self.s) * self.w + int(x * self.s)) * 4
        return self.raw[i], self.raw[i + 1], self.raw[i + 2]
    def count(self, box, fn, step=2):
        n = 0
        for x in range(box[0], box[2], step):
            for y in range(box[1], box[3], step):
                if fn(*self.px(x, y)): n += 1
        return n
def frame():
    if VD["on"]: return Frame(_vd().grab("task", True))
    sh("screencap %s.raw" % SHOT, timeout=25)
    return Frame(open(SHOT + ".raw", "rb").read())
def tapx(x, y, s=1.0): tap(x * s, y * s)

def back(): key(4)
def focus():
    if VD["on"]: return ("VD: " + GAME[0]) if front(True) else "VD: other"
    try: return sh("dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'", timeout=10)
    except Exception: return ""
def launch(pkg):
    if VD["on"]: return _vd().launch(pkg)
    sh("monkey -p %s -c android.intent.category.LAUNCHER 1" % pkg, timeout=20)


# ---------- لمس متعدد (قرصة زوم) عبر sendevent ----------
_TS = {}
CFG = {}          # تضبطه اللوحة (settings.json): touch_path / touch_max_x / touch_max_y / touch_slot لتجاوز الكشف يدوياً
_BASE = os.path.dirname(os.path.abspath(__file__))
_CACHE = os.path.join(_BASE, "touch_dev.json")
_DIAG = os.path.join(_BASE, "debug_getevent.txt")
_ABS_RE = re.compile(r"(ABS_[A-Z0-9_]+|\b00[0-9A-Fa-f]{2}\b)\s*:\s*value\s+-?\d+(?:\s*,\s*min\s+-?\d+)?\s*,\s*max\s+(-?\d+)", re.I)
_CODES = {"0000": "ABS_X", "0001": "ABS_Y", "002F": "ABS_MT_SLOT", "0030": "ABS_MT_TOUCH_MAJOR", "0035": "ABS_MT_POSITION_X",
          "0036": "ABS_MT_POSITION_Y", "0039": "ABS_MT_TRACKING_ID", "003A": "ABS_MT_PRESSURE"}
_KEYS = {"ABS_MT_SLOT": "slotmax", "ABS_MT_TRACKING_ID": "tmax", "ABS_MT_POSITION_X": "mx", "ABS_MT_POSITION_Y": "my",
         "ABS_MT_TOUCH_MAJOR": "maj", "ABS_MT_PRESSURE": "prs"}

def _parse_block(txt):
    """يقرأ محاور ABS من نص جهاز واحد؛ يتحمّل الصيغتين (-lp بالأسماء و-p بالأرقام) والنص المقصوص أو المتداخل."""
    d = {}
    for m in _ABS_RE.finditer(txt):
        name = m.group(1).upper(); name = _CODES.get(name[-4:], name) if not name.startswith("ABS_") else name
        k = _KEYS.get(name)
        if k:
            try: d[k] = int(m.group(2))
            except ValueError: pass
    if "slotmax" in d: d["slot"] = True
    if "tmax" in d: d["tid"] = True
    return d

def _parse_ev(out):
    """يفصل مخرجات getevent إلى أجهزة ويرجع التي فيها مدى X وY للمس المتعدد."""
    devs = []; parts = re.split(r"add device \d+:", out)
    for i, blk in enumerate(parts):
        if i == 0 and len(parts) > 1: continue                      # ما قبل أول جهاز: ذيل مقطوع، يُهمل
        d = _parse_block(blk)
        if "mx" in d and "my" in d:
            m = re.search(r"(/dev/input/\S+)", blk); n = re.search(r'name:\s*"([^"]*)"', blk)
            d["path"] = m.group(1) if m else None; d["name"] = n.group(1) if n else ""; d.setdefault("slot", False); devs.append(d)
    return devs

def _slot_from_sys(path):
    """هل الجهاز يعرّف ABS_MT_SLOT (0x2f)؟ من /sys (قناع بتّات)؛ None إن تعذّر."""
    try:
        ev = path.rsplit("/", 1)[1]
        out = sh("cat /sys/class/input/%s/device/capabilities/abs 2>/dev/null" % ev, timeout=8, check=False).split()
        if not out: return None
        ws = [int(w, 16) for w in out]; size = len(out[-1]) * 4 if len(out) > 1 else max(32, len(out[0]) * 4)
        n = 0
        for w in ws: n = (n << size) | w
        return bool(n >> 0x2f & 1)
    except Exception: return None

def _from_dumpsys(out):
    devs = []
    for blk in re.split(r"\n\s*Device -?\d+:", "\n" + out)[1:]:
        p = re.search(r"Path:\s*(/dev/input/\S+)", blk); r = blk.split("Raw Touch Axes:", 1)
        if not p or len(r) < 2: continue
        seg = r[1][:700]; x = re.search(r"\bX:\s*min=-?\d+,\s*max=(\d+)", seg); y = re.search(r"\bY:\s*min=-?\d+,\s*max=(\d+)", seg)
        if not (x and y): continue
        d = {"path": p.group(1), "mx": int(x.group(1)), "my": int(y.group(1)), "name": "dumpsys"}
        pr = re.search(r"Pressure:\s*min=-?\d+,\s*max=(\d+)", seg); mj = re.search(r"TouchMajor:\s*min=-?\d+,\s*max=(\d+)", seg)
        if pr: d["prs"] = int(pr.group(1))
        if mj: d["maj"] = int(mj.group(1))
        d["slot"] = bool(re.search(r"\bSlot:\s*min=", seg)) or bool(_slot_from_sys(d["path"])); devs.append(d)
    return devs

def _pick(devs):
    devs.sort(key=lambda d: (not d.get("slot"), not re.search(r"ts|touch|gsl|goodix|ft5|silead|synaptics|atmel", d.get("name", ""), re.I), -(d["mx"] * d["my"])))
    return devs[0]

def _detect(diag):
    """يبحث عن شاشة اللمس بعدة طرق متتالية، ويسجّل كل مخرجاتها في diag."""
    # 1) كل جهاز على حدة (مخرجات صغيرة لا تتداخل مع رسائل stderr ولا تُقصّ)
    ls = sh("ls /dev/input 2>&1", timeout=10, check=False); diag.append("## ls /dev/input\n" + ls)
    paths = ["/dev/input/" + e for e in re.findall(r"\bevent\d+\b", ls)]; found = []
    for pth in paths:
        for opt in ("-lp", "-p"):
            out = sh("getevent %s %s 2>&1" % (opt, pth), timeout=10, check=False)
            ds = _parse_ev(out) if "add device" in out else ([dict(d, path=pth) for d in [_parse_block(out)] if "mx" in d and "my" in d])
            diag.append("## getevent %s %s -> %d جهاز\n%s" % (opt, pth, len(ds), out[:1500]))
            if ds:
                for d in ds: d["path"] = d.get("path") or pth
                found += ds; break
    if found: return _pick(found)
    # 2) getevent كامل
    for opt in ("-lp", "-p"):
        out = sh("getevent %s 2>/dev/null" % opt, timeout=15, check=False); ds = _parse_ev(out)
        diag.append("## getevent %s (كامل) -> %d جهاز\n%s" % (opt, len(ds), out[:3000]))
        if ds: return _pick([d for d in ds if d.get("path")] or ds)
    # 3) dumpsys input
    out = sh("dumpsys input 2>&1", timeout=20, check=False); ds = _from_dumpsys(out)
    diag.append("## dumpsys input -> %d جهاز\n%s" % (len(ds), out[:4000]))
    if ds: return _pick(ds)
    # 4) آخر ملاذ: اسم الجهاز من /proc ومداه = دقة الشاشة
    prc = sh("cat /proc/bus/input/devices 2>&1", timeout=10, check=False); diag.append("## /proc/bus/input/devices\n" + prc[:3000])
    for blk in prc.split("\n\n"):
        n = re.search(r'Name="([^"]*)"', blk); h = re.search(r"Handlers=.*?\b(event\d+)\b", blk)
        if n and h and re.search(r"ts\b|touch|gsl|goodix|ft5|silead|synaptics|atmel", n.group(1), re.I):
            sz = re.search(r"(\d+)x(\d+)", sh("wm size 2>&1", timeout=8, check=False))
            if sz:
                w, hh = int(sz.group(1)), int(sz.group(2)); pth = "/dev/input/" + h.group(1); sl = _slot_from_sys(pth)
                diag.append("## تخمين: %s %s مدى %dx%d slot=%s" % (n.group(1), pth, w - 1, hh - 1, sl))
                return {"path": pth, "mx": w - 1, "my": hh - 1, "slot": bool(sl), "name": n.group(1), "assumed": True}
    return None

def forget_touch():
    _TS.clear()
    try: os.remove(_CACHE)
    except OSError: pass

def touch_dev():
    """شاشة اللمس ومداها: (1) تجاوز يدوي من settings.json (2) ذاكرة مؤقتة touch_dev.json (3) كشف تلقائي متعدد الطرق."""
    if _TS: return _TS
    if CFG.get("touch_path") and CFG.get("touch_max_x") and CFG.get("touch_max_y"):
        _TS.update({"path": CFG["touch_path"], "mx": int(CFG["touch_max_x"]), "my": int(CFG["touch_max_y"]), "slot": bool(CFG.get("touch_slot", False)),
                    "prs": int(CFG.get("touch_prs", 0)), "maj": int(CFG.get("touch_maj", 0)), "manual": True}); return _TS
    try:
        c = json.load(open(_CACHE))
        if c.get("path") and c.get("mx") and c.get("my"): _TS.update(c); return _TS
    except Exception: pass
    diag = []; d = None
    try: d = _detect(diag)
    except Stopped: raise
    except Exception as e: diag.append("استثناء: %r" % e)
    if not d:
        try: open(_DIAG, "w").write("\n\n".join(diag))
        except Exception: pass
        raise RuntimeError("لم أجد شاشة اللمس (التفاصيل الكاملة في debug_getevent.txt؛ أو اضبط touch_path وtouch_max_x وtouch_max_y وtouch_slot في settings.json)")
    _TS.update(d)
    try: json.dump(d, open(_CACHE, "w"))
    except Exception: pass
    return _TS

def _rotation():
    try:
        out = sh("dumpsys input | grep -m1 SurfaceOrientation", timeout=10, check=False)
        return int(out.split(":")[1].strip()[0])
    except Exception: return 1

def _raw(x, y, W, H):
    d = touch_dev(); mx, my = d["mx"], d["my"]; fx, fy = x / float(W), y / float(H)
    if (mx > my) == (W > H): rx, ry = fx, fy                       # شاشة اللمس بنفس اتجاه العرض (تابلت/محاكي)
    elif _rotation() == 3: rx, ry = fy, 1 - fx
    else: rx, ry = 1 - fy, fx
    return int(max(0, min(1, rx)) * mx), int(max(0, min(1, ry)) * my)

def _contact_vals(d):
    prs = max(1, min(d["prs"], 60)) if d.get("prs") else 0      # الضغط: إن بقي 0 يعدّه أندرويد "تحويم" فلا تصل اللمسة للعبة
    maj = max(1, min(d["maj"], 30)) if d.get("maj") else 0
    return prs, maj

def pinch_modes():
    """طرق الحقن بالترتيب: الأولى الأرجح، والثانية أبطأ وأشمل (تُجرَّب تلقائياً إن لم تؤثر الأولى)."""
    return ["B", "B+"] if touch_dev().get("slot") else ["A", "A+"]

def pinch_cmds(a0, b0, a1, b1, W, H, mode="B"):
    """بروتوكول B (ABS_MT_SLOT). a0,b0 = بداية الإصبعين؛ a1,b1 = نهايتهما (بكسل حقيقي). يرجع أوامر sendevent وsleep."""
    d = touch_dev(); ev = d["path"]; c = []; full = mode.endswith("+")
    steps, dt = (22, "0.03") if full else (12, "0.02")
    prs, maj = _contact_vals(d)
    ids = (101, 102) if (d.get("tmax") or 65535) >= 102 else (1, 2)
    def e(t, k, v): c.append("sendevent %s %d %d %d" % (ev, t, k, v))
    def contact(slot, p, tid=None):
        e(3, 47, slot)
        if tid is not None:
            e(3, 57, tid)
            if full: e(3, 55, 0)                                   # TOOL_TYPE = إصبع
        e(3, 53, p[0]); e(3, 54, p[1])
        if maj: e(3, 48, maj)
        if prs: e(3, 58, prs)
    A0, B0, A1, B1 = [_raw(p[0], p[1], W, H) for p in (a0, b0, a1, b1)]
    contact(0, A0, ids[0]); contact(1, B0, ids[1]); e(1, 330, 1)
    if full: e(1, 333, 1)
    e(0, 0, 0); c.append("sleep 0.10")                            # ثبّت الإصبعين لحظة قبل الحركة
    for i in range(1, steps + 1):
        t = i / float(steps)
        contact(0, (int(A0[0] + (A1[0] - A0[0]) * t), int(A0[1] + (A1[1] - A0[1]) * t)))
        contact(1, (int(B0[0] + (B1[0] - B0[0]) * t), int(B0[1] + (B1[1] - B0[1]) * t))); e(0, 0, 0)
        c.append("sleep " + dt)
    c.append("sleep 0.08")
    e(3, 47, 0); e(3, 57, -1); e(3, 47, 1); e(3, 57, -1); e(1, 330, 0)
    if full: e(1, 333, 0)
    e(0, 0, 0)
    return c

def pinch_cmds_a(a0, b0, a1, b1, W, H, mode="A"):
    """بروتوكول A (بدون ABS_MT_SLOT): كل إصبع يُرسل مع SYN_MT_REPORT ثم SYN_REPORT في كل إطار."""
    d = touch_dev(); ev = d["path"]; c = []; full = mode.endswith("+")
    steps, dt = (22, "0.03") if full else (12, "0.02")
    prs, maj = _contact_vals(d)
    def e(t, k, v): c.append("sendevent %s %d %d %d" % (ev, t, k, v))
    def finger(p, i):
        e(3, 53, p[0]); e(3, 54, p[1])
        if maj: e(3, 48, maj)
        if prs: e(3, 58, prs)
        if d.get("tid"): e(3, 57, i)
        e(0, 2, 0)
    A0, B0, A1, B1 = [_raw(p[0], p[1], W, H) for p in (a0, b0, a1, b1)]
    e(1, 330, 1); finger(A0, 0); finger(B0, 1); e(0, 0, 0); c.append("sleep 0.10")
    for i in range(1, steps + 1):
        t = i / float(steps)
        finger((int(A0[0] + (A1[0] - A0[0]) * t), int(A0[1] + (A1[1] - A0[1]) * t)), 0)
        finger((int(B0[0] + (B1[0] - B0[0]) * t), int(B0[1] + (B1[1] - B0[1]) * t)), 1); e(0, 0, 0)
        c.append("sleep " + dt)
    c.append("sleep 0.08")
    e(0, 2, 0); e(1, 330, 0); e(0, 0, 0)
    return c

PINCH_SH = "/sdcard/.botvi_pinch.sh"
def pinch(a0, b0, a1, b1, W, H, mode=None):
    gate()
    if VD["on"]: raise RuntimeError("القرصة بإصبعين غير مدعومة على الشاشة الثانوية")
    mode = mode or pinch_modes()[0]
    cmds = (pinch_cmds if mode[0] == "B" else pinch_cmds_a)(a0, b0, a1, b1, W, H, mode)
    try:                                                      # سكربت واحد بدل سطر طويل عبر rish
        open(PINCH_SH, "w").write("\n".join(cmds) + "\n")
        out = sh("sh %s 2>&1" % PINCH_SH, timeout=60)
    except (OSError, subprocess.SubprocessError):
        out = sh(";".join(cmds) + " 2>&1", timeout=60)
    if out.strip():                                           # sendevent لا يطبع شيئاً عند النجاح: أي مخرجات = خطأ (صلاحية/جهاز خاطئ)
        forget_touch(); raise RuntimeError("sendevent رفض الأمر: " + out.strip().replace("\n", " | ")[:160])
