"""حلبة التدريب (الوحوش): استلام النتائج ثم بدء تدريب جديد بالتحديد التلقائي الذي تقترحه اللعبة، مع تبديل مجموعة المعدات عند الطلب.
لا يضغط \"إلغاء\" (زر X) ولا أي شراء. اضبط beast_confirm=false في settings.json إن أردت أن يتوقف عند شاشة \"استعراض التدريب\" دون تأكيد."""
import os, time
from shizuku import frame, tapx, screencap, nap
from tasks.saga import has_x, CLOSE_X
from tasks.tower import note, swap, GO_CHANGE_XY, APPLY_XY
from tasks.guard import popup_x

GOLD = lambda r, g, b: 150 < r < 255 and 90 < g < 190 and b < 90 and r > g + 40
TEAL = lambda r, g, b: r < 80 and 100 < g < 150 and 120 < b < 190
PLANK = lambda r, g, b: 80 < r < 130 and 70 < g < 110 and 60 < b < 100 and abs(r - g) < 30
RIBBON = lambda r, g, b: r > 170 and 40 < g < 90 and 30 < b < 80

BUILD_XY, HEX_XY = (630, 220), (556, 293)       # مبنى حلبة التدريب في المدينة ثم الزر السداسي الأول (beast_build / beast_hex)
BTN_XY, CONFIRM_XY = (275, 296), (293, 683)     # زر \"تدريب\"/\"النتائج\"، وزر \"تأكيد\"

def arena(f): return has_x(f) and f.count((80, 175, 1200, 245), PLANK) > 10000
def results(f): return arena(f) and f.count((165, 272, 385, 320), GOLD) > 1000
def idle(f): return arena(f) and f.count((165, 272, 385, 320), TEAL) > 1500
def review(f): return has_x(f) and f.count((140, 640, 447, 727), GOLD) > 4500 and f.count((80, 175, 1200, 245), PLANK) < 500

def snap(name):
    try: open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "debug_%s.png" % name), "wb").write(screencap())
    except Exception: pass

def run(log, cfg):
    f = frame()
    if f.w < f.h: return log("الشاشة عمودية؛ يلزم الوضع الأفقي")
    if not (arena(f) or review(f)):
        for _ in range(4):
            f = frame()
            if not has_x(f): break
            tapx(*CLOSE_X, f.s); nap(1.2)
        b = cfg.get("beast_build") or BUILD_XY; h = cfg.get("beast_hex") or HEX_XY
        tapx(*b, f.s); nap(1.2); tapx(*h, f.s); nap(3); f = frame()
        if not (arena(f) or review(f)): snap("beast_open"); return log("الوحوش: لم تُفتح الحلبة (حُفظت debug_beast_open.png)")
    s = f.s; started = False; got = False
    for _ in range(10):
        f = frame()
        if note(f): tapx(*GO_CHANGE_XY, s); log("الوحوش: تبديل مجموعة المعدات"); nap(2.5); continue
        if swap(f): tapx(*APPLY_XY, s); nap(2.5); continue
        p = popup_x(f)
        if p: tapx(p[0], p[1], s); nap(1.5); continue
        if arena(f):
            if results(f): tapx(*BTN_XY, s); got = True; log("الوحوش: استلام نتائج التدريب"); nap(2.5); continue
            if idle(f): tapx(*BTN_XY, s); nap(2.5); continue
            log("الوحوش: التدريب جارٍ" if not started else "الوحوش: بدأ تدريب جديد"); break
        if review(f):
            if not cfg.get("beast_confirm", True): log("الوحوش: وصلت إلى شاشة التأكيد ولم أؤكد (beast_confirm=false)"); break
            tapx(*CONFIRM_XY, s); started = True; nap(2.5); continue
        snap("beast_unknown"); log("الوحوش: شاشة غير متوقعة (حُفظت debug_beast_unknown.png)"); break
    for _ in range(4):
        f = frame()
        if not has_x(f): break
        tapx(*CLOSE_X, f.s); nap(1.2)
