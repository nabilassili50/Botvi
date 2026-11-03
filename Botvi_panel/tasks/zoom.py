"""تصغير القلعة (زوم) إلى أقصى مستوى عند الدخول إلى اللعبة لتظهر كل المباني.
قرصة بإصبعين (pinch-in) في المدينة عبر sendevent، وتتكرر حتى لا تتغير الصورة (أقصى تصغير).
v3.9 (إعادة بناء من الأساس):
  - اللمسة تحمل الآن الضغط وحجم التماس (بدونهما كان أندرويد يعدّها تحويماً فلا تصل للعبة).
  - الحقن بسكربت واحد مع فواصل زمنية منتظمة بدل مئات أوامر متتابعة غير منتظمة.
  - انتظار استقرار الصورة بعد القرصة قبل المقارنة (لا حكم مبكر أثناء الحركة).
  - طريقتا حقن (عادية/شاملة): إن لم تؤثر الأولى تُجرَّب الثانية تلقائياً، وتُحفظ الناجحة في zoom_mode.txt.
  - عند الفشل يُكتب debug_zoom.txt (الجهاز، الطريقة، فروق الصور) مع debug_zoom.png."""
import os, time
import shizuku
from shizuku import frame, pinch, screencap
import tasks.guard as guard

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEFILE = os.path.join(BASE, "zoom_mode.txt")
RETRY_AFTER = 300                     # بعد فشل الزوم لا نكرر قبل 5 دقائق
A0, B0 = (260, 400), (1020, 400)      # الإصبعان متباعدان (مقياس 1280x800)
A1, B1 = (610, 400), (670, 400)       # ويتقاربان نحو المركز = تصغير


def diff(a, b):
    n = d = 0
    for x in range(140, 1180, 60):
        for y in range(150, 640, 50):
            p, q = a.px(x, y), b.px(x, y); n += 1
            if abs(p[0] - q[0]) + abs(p[1] - q[1]) + abs(p[2] - q[2]) > 60: d += 1
    return d / float(n)


LAST = [0.0]
BROKEN = [0.0]      # عند فشل القرصة لا نكرر المحاولة قبل هذا الوقت (يمنع تعطيل المهام وتكرار السجل)
GRASS = lambda r, g, b: g > r + 25 and g > b + 40 and g > 100
try: MODE = [open(MODEFILE).read().strip() or None]      # الطريقة التي نجحت سابقاً
except Exception: MODE = [None]


def suspect(f):
    """مؤشر لوني: حواف الشاشة خضراء أكثر من المعتاد = المدينة مقرَّبة غالباً (يستعجل الفحص فقط)."""
    return f.count((0, 300, 200, 650), GRASS) / float(((650 - 300) // 2) * (200 // 2)) > 0.68 and f.count((0, 600, 500, 720), GRASS) / float((120 // 2) * (500 // 2)) > 0.66

def need(cfg):
    """هل نفحص/نصغّر الزوم قبل المهمة؟ عند الدخول للعبة، أو كل zoom_check ثانية، أو إن بدت المدينة مقرَّبة."""
    if time.time() < BROKEN[0]: return False
    if shizuku.VD["on"] and not guard.NEED_ZOOM[0]: return False
    if guard.NEED_ZOOM[0] or time.time() - LAST[0] > int(cfg.get("zoom_check", 90)): return True
    try:
        f = frame(); return guard.city(f) and suspect(f)
    except shizuku.Stopped: raise
    except Exception: return False


def settle(a, wait=4.0):
    """ينتظر توقف حركة الصورة بعد القرصة (الزوم يكمل بالقصور) ثم يرجع الفرق عن الصورة قبل القرصة."""
    t0 = time.time(); time.sleep(0.8); prev = frame()
    while time.time() - t0 < wait:
        time.sleep(0.5); cur = frame()
        if diff(prev, cur) < 0.01: prev = cur; break
        prev = cur
    return diff(a, prev)


def _remember(mode):
    if MODE[0] == mode: return
    MODE[0] = mode
    try: open(MODEFILE, "w").write(mode)
    except Exception: pass


def _debug(trace, extra=""):
    try: open(os.path.join(BASE, "debug_zoom.png"), "wb").write(screencap())
    except Exception: pass
    try:
        d = dict(shizuku.touch_dev())
        open(os.path.join(BASE, "debug_zoom.txt"), "w").write("device=%s\ntrace=%s\n%s\n" % (d, trace, extra))
    except Exception as e:
        try: open(os.path.join(BASE, "debug_zoom.txt"), "w").write("trace=%s\nerr=%s\n" % (trace, e))
        except Exception: pass


def zoom_out(log, cfg, tries=6, probe=False):
    if shizuku.VD["on"]:
        guard.NEED_ZOOM[0] = False
        return log("الزوم: غير مدعوم على الشاشة الثانوية (القرصة تعمل على الشاشة الرئيسية فقط)")
    f = frame()
    if f.w < f.h: return log("الزوم: الشاشة عمودية؛ يلزم الوضع الأفقي")
    LAST[0] = time.time()
    t0 = time.time()
    while not guard.city(f) and time.time() - t0 < 30: time.sleep(2); f = frame()      # انتظر انتهاء تحميل اللعبة
    if not guard.city(f): return log("الزوم: لسنا في المدينة، سأعيد المحاولة لاحقاً")
    s = f.s; W, H = f.w, f.h; moved = 0; trace = []
    try: modes = list(shizuku.pinch_modes())
    except shizuku.Stopped: raise
    except Exception as e:
        guard.NEED_ZOOM[0] = False; BROKEN[0] = time.time() + RETRY_AFTER
        return log("الزوم: تعذّر قراءة شاشة اللمس: %s (سأعيد المحاولة بعد 5 دقائق)" % e)
    known = MODE[0] in modes
    if known: modes.remove(MODE[0]); modes.insert(0, MODE[0])
    mi = 0
    for i in range(tries):
        a = frame(); mode = modes[mi]
        try: pinch([v * s for v in A0], [v * s for v in B0], [v * s for v in A1], [v * s for v in B1], W, H, mode)
        except shizuku.Stopped: raise
        except Exception as e:
            guard.NEED_ZOOM[0] = False; BROKEN[0] = time.time() + RETRY_AFTER
            _debug(trace, "pinch error: %s" % e)
            return log("الزوم: فشلت القرصة: %s (سأعيد المحاولة بعد 5 دقائق)" % e)
        d = settle(a); trace.append("%s:%.3f" % (mode, d))
        if d >= 0.03:
            moved += 1; _remember(mode); known = True; continue
        if moved: break                                    # لا تغيّر بعد نجاح سابق = أقصى تصغير
        if not known and not probe and mi + 1 < len(modes): mi += 1; continue      # لم تؤثر: جرّب طريقة حقن أخرى
        break
    guard.NEED_ZOOM[0] = False; LAST[0] = time.time()
    if moved:
        log("الزوم: صُغّرت القلعة (%d قرصة، الطريقة %s)" % (moved, MODE[0]))
    elif probe: return                                     # فحص دوري: كانت مصغّرة أصلاً، لا ضجيج
    else:
        _debug(trace)
        log("الزوم: لم يتغيّر شيء بأي طريقة (%s). ربما بلغنا أقصى تصغير أو الإيماءة لم تصل (حُفظت debug_zoom.png وdebug_zoom.txt)" % " ".join(trace))


def run(log, cfg):
    zoom_out(log, cfg)
