"""برج الوحوش: دمج لفيفة الوحوش. يبدّل مجموعة المعدات إلى \"تطوير الوحوش\" إن طلبت اللعبة، ويضغط \"دمج\".
لا يضغط \"إنهاء الدمج فورا\" ولا \"زيادة سرعة\" ولا \"إلغاء\"."""
import os, time
from shizuku import frame, tapx, screencap, nap
from tasks.saga import has_x, CLOSE_X

RIBBON = lambda r, g, b: r > 170 and 40 < g < 90 and 30 < b < 80
GOLD = lambda r, g, b: 150 < r < 255 and 90 < g < 190 and b < 90 and r > g + 40
BLUE = lambda r, g, b: r < 60 and 90 < g < 150 and 150 < b < 220
WARM = lambda r, g, b: r > g + 25 and r > b + 25
SWAPBAR = lambda r, g, b: r < 50 and 80 < g < 130 and 130 < b < 200
APPLY = lambda r, g, b: 130 < r < 230 and 70 < g < 150 and b < 90

BUILD_XY, HEX_XY = (1090, 510), (1022, 595)      # مبنى البرج في المدينة ثم الزر السداسي الأول (يمكن تغييرهما: tower_build / tower_hex)
SCROLL_XY = (865, 400)                           # بطاقة \"لفيفة الوحوش\"
FUSE_XY = (295, 695)                             # زر \"دمج\"
GO_CHANGE_XY, APPLY_XY = (640, 383), (250, 228)  # \"اذهب للتغيير\" ثم \"تطبيق\" على صف الوحوش
USE_XY, CANCEL_XY = (495, 722), (780, 722)       # نافذة \"تستخدم لتلبية متطلبات المشروع\"

def _rib(f): return has_x(f) and f.count((430, 118, 850, 152), RIBBON) > 1500
def choose(f): return _rib(f) and f.count((95, 630, 270, 735), GOLD) > 2500 and f.count((560, 330, 640, 480), WARM) < 100
def fuse_idle(f): return _rib(f) and f.count((180, 660, 410, 735), GOLD) > 2500 and f.count((95, 630, 170, 735), GOLD) < 1000
def fusing(f): return _rib(f) and f.count((180, 660, 410, 735), BLUE) > 2500
def note(f): return f.count((440, 360, 840, 405), GOLD) > 2500 and f.count((430, 118, 850, 152), RIBBON) < 100
def swap(f): return has_x(f) and f.count((145, 190, 355, 265), APPLY) > 2500 and f.count((200, 125, 1000, 170), SWAPBAR) > 5000
def autouse(f): return f.count((380, 680, 610, 765), GOLD) > 3000 and f.count((430, 118, 850, 152), RIBBON) < 100

def snap(name):
    try: open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "debug_%s.png" % name), "wb").write(screencap())
    except Exception: pass

def run(log, cfg):
    f = frame()
    if f.w < f.h: return log("الشاشة عمودية؛ يلزم الوضع الأفقي")
    if not (choose(f) or fuse_idle(f) or fusing(f)):
        for _ in range(4):
            f = frame()
            if not has_x(f): break
            tapx(*CLOSE_X, f.s); nap(1.2)
        b = cfg.get("tower_build") or BUILD_XY; h = cfg.get("tower_hex") or HEX_XY
        tapx(*b, f.s); nap(1.2); tapx(*h, f.s); nap(3); f = frame()
        if not (choose(f) or fuse_idle(f) or fusing(f)): snap("tower_open"); return log("البرج: لم تُفتح الشاشة (حُفظت debug_tower_open.png)")
    s = f.s
    if choose(f): tapx(*SCROLL_XY, s); nap(2); f = frame()
    if fusing(f): log("البرج: الدمج جارٍ")
    elif not fuse_idle(f): snap("tower_fuse"); log("البرج: لم تظهر شاشة الدمج (حُفظت debug_tower_fuse.png)")
    else:
        started = False
        for _ in range(6):
            f = frame()
            if fusing(f): started = True; break
            if note(f): tapx(*GO_CHANGE_XY, s); log("البرج: تبديل مجموعة المعدات"); nap(2.5); continue
            if swap(f): tapx(*APPLY_XY, s); nap(2.5); continue
            if autouse(f):
                tapx(*(USE_XY if cfg.get("tower_items", True) else CANCEL_XY), s); log("البرج: استخدام عناصر لتغطية النقص" if cfg.get("tower_items", True) else "البرج: رُفض استخدام العناصر")
                nap(2.5); continue
            if fuse_idle(f): tapx(*FUSE_XY, s); nap(2.2); continue
            snap("tower_unknown"); log("البرج: شاشة غير متوقعة (حُفظت debug_tower_unknown.png)"); break
        if started: log("البرج: بدأ الدمج")
        elif fuse_idle(frame()): log("البرج: لم يبدأ الدمج (موارد ناقصة؟)"); snap("tower_nostart")
    for _ in range(4):
        f = frame()
        if not has_x(f): break
        tapx(*CLOSE_X, f.s); nap(1.2)
