"""الملحمة البطولية: استلام المكافآت ثم تعيين الأبطال تلقائياً لكل موقع حر."""
import time
from shizuku import frame, tapx, nap

ORANGE = lambda r, g, b: r > 220 and 130 < g < 200 and b < 90
YELLOW = lambda r, g, b: r > 230 and g > 190 and b < 80
SITES = [(455, 300), (905, 290), (320, 560), (780, 550)]          # أماكن الضغط على المواقع الأربعة
CLAIM = [(375, 305, 525, 365), (830, 305, 980, 365), (247, 555, 397, 610), (703, 555, 853, 610)]
CLAIM_XY = [(450, 335), (905, 335), (322, 581), (778, 581)]
ASSIGN_BOX, ASSIGN_XY, AUTO_XY = (80, 665, 320, 735), (200, 700), (200, 620)
CLOSE_X = (45, 45)

def has_x(f):
    r, g, b = f.px(*CLOSE_X); return r > 230 and 150 < g < 220 and b < 100
def in_saga(f):
    r, g, b = f.px(880, 133)      # شريط "الملحمة البطولية" الأزرق
    return has_x(f) and r < 50 and b > 110 and b > g + 40
def panel_open(f): return f.count(ASSIGN_BOX, ORANGE) > 1500
def selected(f): return f.count((40, 240, 135, 280), YELLOW) > 30

_ok = []

def run(log, cfg):
    f = frame()
    if f.w < f.h: return log("الشاشة عمودية؛ يلزم الوضع الأفقي")
    if not in_saga(f):
        # الأزرار السداسية الثلاثة تحت تمثال البطل؛ نجرّبها بالترتيب حتى تُفتح الملحمة
        cands = cfg.get("saga_entry") or [[405, 410], [465, 410], [527, 410]]
        order = ([_ok[0]] if _ok else []) + [i for i in range(len(cands)) if not _ok or i != _ok[0]]
        for i in order:
            tapx(*cands[i], f.s); nap(2); f = frame()
            if in_saga(f): _ok[:] = [i]; log("الملحمة: الزر %d فتحها" % (i + 1)); break
            if has_x(f): tapx(*CLOSE_X, f.s); nap(1.2)   # أغلق ما فُتح بالخطأ
        else: return log("الملحمة: لم يفتحها أي زر؛ ارجع إلى المدينة وأرسل لقطة")
    s = f.s
    # 1) استلام المكافآت
    for _ in range(6):
        f = frame(); todo = [i for i, b in enumerate(CLAIM) if f.count(b, ORANGE) > 700]
        if not todo: break
        tapx(*CLAIM_XY[todo[0]], s); log("استلام موقع %d" % (todo[0] + 1)); nap(1.5)
        tapx(640, 760, s); nap(1); tapx(640, 760, s); nap(1)
    # 2) تعيين الأبطال لكل موقع حر
    done = 0
    for i, (x, y) in enumerate(SITES):
        f = frame()
        if not in_saga(f): log("خرجنا من شاشة الملحمة"); break
        tapx(x, y, s); nap(1.2); f = frame()
        if not panel_open(f): log("الموقع %d مشغول/مغلق" % (i + 1)); continue
        if not selected(f): tapx(*AUTO_XY, s); nap(1); f = frame()
        if not selected(f): log("موقع %d: فشل التحديد التلقائي" % (i + 1)); continue
        tapx(*ASSIGN_XY, s); nap(1.5); done += 1; log("تعيين موقع %d" % (i + 1))
    log("الملحمة: عُيّن %d موقع" % done)
    tapx(*CLOSE_X, s)
