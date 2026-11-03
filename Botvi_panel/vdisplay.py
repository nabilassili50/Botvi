"""الشاشة الثانوية الافتراضية (تجريبي، v3.8): تشغيل اللعبة على شاشة "محاكاة شاشة ثانوية" (overlay) بدل الشاشة الرئيسية،
فتبقى الشاشة الرئيسية حرّة للمتصفح/اللوحة بينما يواصل البوت العمل على اللعبة.
 - الإنشاء:  settings put global overlay_display_devices WxH/DPI   (يظهر نافذة عائمة صغيرة فوق الشاشة الرئيسية)
 - التشغيل:  am start --display ID ...        - اللمس:  input -d ID tap/swipe/keyevent
 - اللقطة:   screencap -d ID إن دُعمت، وإلا قصّ منطقة النافذة العائمة من لقطة الشاشة الرئيسية.
عند أي فشل تُكتب المخرجات الخام في /sdcard/.botvi_vd_*.txt لتشخيصها. لا شيء هنا يعمل ما لم يُفعَّل خيار vdisplay."""
import re, struct, time, zlib
import shizuku
from shizuku import sh, VD

OV, FR = "overlay_display_devices", "force_resizable_activities"
_BOX = [None, 0.0]


def sh2(cmd, timeout=15, check=False):
    """ينفّذ الأمر ويدمج stderr في المخرجات (لتظهر رسائل الأخطاء)."""
    return sh(cmd + " 2>&1", timeout=timeout, check=check)


def dump(name, text):
    try: open("/sdcard/.botvi_vd_%s.txt" % name, "w").write(text)
    except Exception: pass


# ---------- إنشاء الشاشة وكشفها ----------
def find_display(out=None):
    """رقم الشاشة الثانوية (overlay) من dumpsys display، أو None."""
    if out is None: out = sh2("dumpsys display", timeout=20)
    for m in re.finditer(r'DisplayInfo\{"([^"]*)",\s*displayId\s+(\d+)', out):
        if "overlay" in m.group(1).lower() and int(m.group(2)) > 0: return int(m.group(2))
    for m in re.finditer(r"mDisplayId=(\d+)", out):
        i = int(m.group(1))
        if i > 0 and "overlay" in out[m.end():m.end() + 800].lower(): return i
    return None


def alive():
    i = find_display()
    if i is None: return False
    VD["id"] = i; return True


def sdk():
    try: return int(sh2("getprop ro.build.version.sdk").strip().split()[0])
    except Exception: return 0


def _size(S):
    size = str(S.get("vd_size") or "1280x800")
    if not re.match(r"^\d+x\d+$", size): size = "1280x800"
    try: dpi = int(S.get("vd_dpi") or 240)
    except Exception: dpi = 240
    return size, dpi


def enable(log, S):
    """ينشئ الشاشة (أو يعيد استخدام الموجودة) ويضبط VD. يرمي RuntimeError عند الفشل."""
    s = sdk()
    if s and s < 29: raise RuntimeError("الشاشة الثانوية تحتاج أندرويد 10 أو أحدث (جهازك: SDK %d)" % s)
    size, dpi = _size(S); i = find_display()
    if i is None:
        if "vd_prev_fr" not in S: S["vd_prev_fr"] = sh2("settings get global " + FR).strip() or "null"
        sh2("settings put global %s 1" % FR)                    # تسمح للعبة غير القابلة لتغيير الحجم بالعمل على شاشة ثانوية
        out = sh2("settings put global %s %s/%d" % (OV, size, dpi))
        t = time.time()
        while i is None and time.time() - t < 12: time.sleep(1); i = find_display()
        if i is None: raise RuntimeError("لم تظهر الشاشة الثانوية بعد الأمر (%s)" % (out.strip()[:120] or "بلا رسالة"))
    w, h = (int(v) for v in size.split("x"))
    VD.update(on=True, id=i, cap=None, size=(w, h), sdk=s, log=log, S=S); _BOX[0] = None; shizuku._FG[0] = 0
    log("الشاشة الثانوية: جاهزة (الشاشة رقم %d، %s)" % (i, size))
    return i


def disable(log, S):
    VD.update(on=False, cap=None); _BOX[0] = None; shizuku._FG[0] = 0
    sh2("settings delete global " + OV)
    prev = S.pop("vd_prev_fr", None)
    if prev is not None:
        sh2("settings delete global " + FR if prev in ("", "null") else "settings put global %s %s" % (FR, prev))
    log("الشاشة الثانوية: أُوقفت والعودة للشاشة الرئيسية")


# ---------- اللعبة على الشاشة الثانوية ----------
def where(pkg):
    """رقم الشاشة التي تعمل عليها اللعبة (None إن لم تُوجد)."""
    out = sh("dumpsys activity activities | grep -E 'Display #|esumed|ActivityRecord\\{'", timeout=25, check=False)
    cur = res = rec = None
    for ln in out.splitlines():
        m = re.search(r"Display #(\d+)", ln)
        if m: cur = int(m.group(1)); continue
        if pkg + "/" not in ln or cur is None: continue
        if "esumed" in ln:
            if res is None: res = cur
        elif rec is None: rec = cur
    return res if res is not None else rec


def front():
    return where(shizuku.GAME[0]) == VD["id"]


def resolve(pkg):
    out = sh2("cmd package resolve-activity --brief -a android.intent.action.MAIN -c android.intent.category.LAUNCHER %s" % pkg)
    for ln in reversed(out.strip().splitlines()):
        ln = ln.strip()
        if ln.startswith(pkg + "/") and " " not in ln: return ln
    m = re.search(re.escape(pkg) + r"/[\w.$]+", sh2("dumpsys package %s | grep -B6 -A2 android.intent.action.MAIN" % pkg))
    return m.group(0) if m else None


def _stacks(pkg):
    """(رقم الحزمة/المهمة، رقم الـ stack) للعبة من am stack list (أندرويد 10-11)."""
    out = sh2("am stack list", timeout=20); sid = None
    for ln in out.splitlines():
        m = re.search(r"(?:Stack|RootTask) id=(\d+)", ln)
        if m: sid = m.group(1)
        t = re.search(r"taskId=(\d+): %s/" % re.escape(pkg), ln)
        if t: return t.group(1), sid, out
    return None, None, out


def move_to_vd(pkg):
    """ينقل نافذة اللعبة إلى الشاشة الثانوية دون إعادة تشغيلها (am display move-stack، أندرويد 10-11)."""
    tid, sid, out = _stacks(pkg)
    if not sid: dump("move", out); return False
    r = sh2("am display move-stack %s %d" % (sid, VD["id"]), timeout=20)
    t = time.time()
    while time.time() - t < 15:
        if where(pkg) == VD["id"]: return True
        time.sleep(2)
    dump("move", "stack=%s task=%s\n%s\n%s" % (sid, tid, r, out)); return False


def zoom_first(pkg):
    """يفتح اللعبة على الشاشة الرئيسية، ينتظر المدينة، يصغّر القلعة بالقرصة، ثم ينقلها للشاشة الثانوية."""
    import tasks.guard as guard, tasks.zoom as zoom
    log, S = VD.get("log") or (lambda m: None), VD.get("S") or {}
    log("الشاشة الثانوية: أفتح اللعبة على الشاشة الرئيسية لتصغير القلعة أولاً ثم أنقلها")
    VD["on"] = False; shizuku._FG[0] = 0
    try:
        if where(pkg) != 0: shizuku.sh("monkey -p %s -c android.intent.category.LAUNCHER 1" % pkg, timeout=20, check=False)
        t = time.time(); ok = False
        while time.time() - t < 150:
            try:
                f = shizuku.frame()
                if guard.city(f): ok = True; break
            except shizuku.Stopped: raise
            except Exception: pass
            time.sleep(4)
        if ok: zoom.zoom_out(log, S)
        else: log("الزوم: لم تظهر المدينة على الشاشة الرئيسية خلال 150 ثانية")
    finally:
        VD["on"] = True; shizuku._FG[0] = 0
    if move_to_vd(pkg): log("الشاشة الثانوية: نُقلت اللعبة بعد تصغير القلعة"); guard.NEED_ZOOM[0] = False; return True
    log("الشاشة الثانوية: تعذّر نقل اللعبة (راجع /sdcard/.botvi_vd_move.txt)؛ سأفتحها مباشرة بدون تصغير"); return False


def launch(pkg):
    if VD.get("zf") and VD.get("sdk", 0) in range(29, 32) and where(pkg) != VD["id"]:
        try:
            if zoom_first(pkg): return "moved"
        except shizuku.Stopped: raise
        except Exception as e: (VD.get("log") or (lambda m: None))("خطأ في تصغير القلعة قبل النقل: %s" % e)
    comp = resolve(pkg)
    tgt = "-n " + comp if comp else "-p " + pkg                     # إن تعذّر إيجاد النشاط نطلب أي نشاط رئيسي داخل الحزمة
    cmd = "am start --display %d -a android.intent.action.MAIN -c android.intent.category.LAUNCHER %s" % (VD["id"], tgt)
    out = sh2(cmd, timeout=25)
    t = time.time(); w = None
    while time.time() - t < 10:
        w = where(pkg)
        if w is not None: break
        time.sleep(2)
    if w is not None and w != VD["id"]:                          # اللعبة تعمل على الشاشة الرئيسية: لا تنتقل بين الشاشات، لذا أعد تشغيلها
        sh2("am force-stop " + pkg); time.sleep(1.5); out = sh2(cmd, timeout=25)
    if "rror" in out or "xception" in out or not comp: dump("launch", "component=%s\n%s" % (comp, out))
    return out


def wait_city(log, wait=150):
    """ينتظر انتهاء تحميل اللعبة (ظهور المدينة أو نافذة معروفة) دون أي ضغط."""
    import tasks.guard as guard
    from tasks.saga import has_x
    t = time.time(); log("الشاشة الثانوية: أنتظر انتهاء تحميل اللعبة")
    while time.time() - t < wait:
        try:
            f = shizuku.frame()
            if guard.city(f) or has_x(f) or guard.popup_x(f): return True
        except shizuku.Stopped: raise
        except Exception: pass
        time.sleep(4)
    log("الشاشة الثانوية: لم تظهر المدينة بعد %d ثانية" % wait); return False


def bring_game(log, S, wait=40):
    """يتأكد أن اللعبة على الشاشة الثانوية ويفتحها هناك إن لزم."""
    pkg = shizuku.GAME[0]
    if where(pkg) == VD["id"]: return True
    log("الشاشة الثانوية: أفتح اللعبة على الشاشة رقم %d" % VD["id"])
    launch(pkg); t = time.time()
    while time.time() - t < wait:
        if where(pkg) == VD["id"]: return True
        time.sleep(2)
    return False


# ---------- اللقطة ----------
def _hdr(raw):
    if not raw or len(raw) < 12: return None
    w = int.from_bytes(raw[0:4], "little"); h = int.from_bytes(raw[4:8], "little")
    if not (16 <= w <= 8192 and 16 <= h <= 8192): return None
    off = len(raw) - w * h * 4
    return (w, h, off) if 8 <= off <= 64 else None


def _screencap_raw(extra, path, check):
    sh2("rm -f " + path)
    sh2("screencap %s %s" % (extra, path), timeout=25, check=check)
    try: return open(path, "rb").read()
    except OSError: return None


def parse_box(out):
    """إحداثيات نافذة OverlayDisplayWindow على الشاشة الرئيسية من dumpsys window."""
    for pat in (r"(?:^|[\s,])(?:mFrame|frame)=\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]",
                r"(?:^|[\s,])(?:mFrame|frame)=Rect\((-?\d+), (-?\d+) - (-?\d+), (-?\d+)\)",
                r"(?:^|[\s,])(?:mFrame|frame)=\((-?\d+), (-?\d+)\)\s*-\s*\((-?\d+), (-?\d+)\)"):
        m = re.search(pat, out, re.M)
        if m:
            x0, y0, x1, y1 = (int(v) for v in m.groups())
            if x1 - x0 >= 200 and y1 - y0 >= 120: return (x0, y0, x1, y1)
    return None


def window_box(force=False):
    if not force and _BOX[0] and time.time() - _BOX[1] < 8: return _BOX[0]
    out = sh2("dumpsys window windows | grep -A60 OverlayDisplayWindow", timeout=25)
    box = parse_box(out)
    if not box:
        dump("windows", out)
        raise RuntimeError("تعذّر تحديد موضع النافذة العائمة للشاشة الثانوية (المخرجات في /sdcard/.botvi_vd_windows.txt)")
    _BOX[0], _BOX[1] = box, time.time(); return box


def crop(raw, box):
    """يقصّ مستطيلاً من لقطة خام ويرجع لقطة خام جديدة بترويسة من 12 بايت."""
    W, H, off = _hdr(raw)
    x0, y0 = max(0, box[0]), max(0, box[1]); x1, y1 = min(W, box[2]), min(H, box[3])
    if x1 - x0 < 100 or y1 - y0 < 60: raise RuntimeError("النافذة العائمة خارج الشاشة أو صغيرة جداً (%s)" % (box,))
    w, h = x1 - x0, y1 - y0
    rows = [raw[off + (y * W + x0) * 4: off + (y * W + x1) * 4] for y in range(y0, y1)]
    return w.to_bytes(4, "little") + h.to_bytes(4, "little") + b"\0\0\0\0" + b"".join(rows)


def grab(tag="task", check=True):
    """لقطة خام (RGBA بترويسة) للشاشة الثانوية. tag يميّز الملف كي لا تتعارض لقطات المهام مع لقطات اللوحة."""
    path = "/sdcard/.botvi_vd_%s.raw" % tag
    if VD.get("cap") != "crop":
        for _ in range(3):                                    # فشل لحظي (أثناء التحميل مثلاً) لا يغيّر الطريقة
            raw = _screencap_raw("-d %d" % VD["id"], path, check); hd = _hdr(raw)
            if hd and (hd[0], hd[1]) == tuple(VD["size"]): VD["cap"] = "direct"; VD["fw"] = hd[0]; return raw      # لقطة مباشرة بحجم الشاشة الثانوية تماماً
            time.sleep(0.7)
        if VD.get("cap") == "direct": raise RuntimeError("فشلت اللقطة المباشرة للشاشة الثانوية (لحظياً)")      # نجحت سابقاً: لا نتحول للقصّ
        VD["cap"] = "crop"                                    # screencap -d لا يدعم الشاشات الافتراضية في هذا الجهاز
    raw = _screencap_raw("", path, check)
    if not _hdr(raw): raise RuntimeError("فشلت لقطة الشاشة الرئيسية")
    out = crop(raw, window_box()); VD["fw"] = int.from_bytes(out[0:4], "little"); return out


def to_png(raw):
    w, h, off = _hdr(raw); st = w * 4
    rows = b"".join(b"\0" + raw[off + y * st: off + (y + 1) * st] for y in range(h))
    def ck(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + ck(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + ck(b"IDAT", zlib.compress(rows, 3)) + ck(b"IEND", b""))


def png(tag="shot", check=True): return to_png(grab(tag, check))


# ---------- اختبار شامل (لا يضغط أي شيء داخل اللعبة) ----------
def test(log, S):
    R = []
    def step(name, ok, d=""):
        R.append({"s": name, "ok": bool(ok), "d": str(d)[:300]})
        log("اختبار الشاشة الثانوية — %s: %s %s" % (name, "✔" if ok else "فشل", str(d)[:200])); return ok
    try:
        s = sdk()
        if not step("نسخة أندرويد", s >= 29, "SDK %d" % s): return R
        o = sh2("input -d 0 keyevent 0")
        if not step("دعم input -d", not any(w in o for w in ("Usage", "xception", "nknown")), o.strip()[:120] or "مدعوم"): return R
        try: i = enable(log, S); step("إنشاء الشاشة", True, "الشاشة رقم %d" % i)
        except Exception as e: step("إنشاء الشاشة", False, e); return R
        ok = bring_game(log, S, 45)
        if not step("تشغيل اللعبة على الشاشة الثانوية", ok, "" if ok else "لم تظهر اللعبة هناك (افتح اللعبة يدوياً مرة ثم أعد الاختبار؛ راجع /sdcard/.botvi_vd_launch.txt)"): return R
        time.sleep(6)
        try:
            raw = grab("test", False); w, h, _ = _hdr(raw); data = to_png(raw)
            open(__import__("os").path.join(__import__("os").path.dirname(__import__("os").path.abspath(__file__)), "debug_vd_test.png"), "wb").write(data)
            step("اللقطة", True, "الطريقة: %s، الحجم %dx%d (حُفظت debug_vd_test.png)" % ("مباشرة" if VD["cap"] == "direct" else "قصّ النافذة العائمة", w, h))
            hd = _hdr(raw); off = hd[2]; lit = sum(1 for k in range(0, 400) if max(raw[off + k * ((w * h) // 400) * 4: off + k * ((w * h) // 400) * 4 + 3]) > 12)
            step("الصورة ليست سوداء", lit > 8, "%d من 400 عيّنة مضيئة" % lit)
            if VD["cap"] == "crop" and w < 900: step("دقة اللقطة", True, "النافذة صغيرة (%dpx)؛ كبّرها بإصبعين من الشاشة لتحسين دقة الكشف" % w)
        except Exception as e: step("اللقطة", False, e)
    except Exception as e: step("خطأ غير متوقع", False, e)
    finally:
        if not S.get("vdisplay") and VD["on"]:
            try: disable(log, S)
            except Exception: pass
    return R
