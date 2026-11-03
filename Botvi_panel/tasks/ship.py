"""سفينة الشحن: من وسط القلعة يسحب الشاشة 3 مرات نحو مكان السفينة، يفتحها، يضغط كل أزرار \"تبادل\" المتاحة (موارد مقابل موارد/تسريعات، لا جواهر)،
ثم يغلقها ويسحب 3 مرات بالاتجاه المعاكس ليعود إلى وسط القلعة كما كان. نافذة \"استخدام تلقائي\" (إن ظهرت لنقص مورد) يضغط فيها \"إلغاء\" دائماً."""
import os, time
from shizuku import frame, tapx, screencap, swipe, nap
from tasks.saga import has_x, CLOSE_X
from tasks.guard import city

RIBBON = lambda r, g, b: r > 150 and g < 90 and b < 90
WOOD = lambda r, g, b: 90 < r < 170 and 55 < g < 120 and 25 < b < 85 and r > g + 25
BTN = lambda r, g, b: 40 <= r <= 70 and 100 <= g <= 135 and 120 <= b <= 160
GOLD = lambda r, g, b: 150 < r < 255 and 90 < g < 190 and b < 90 and r > g + 40
BLUE = lambda r, g, b: r < 110 and 120 < g < 190 and b > 150
PARCH = lambda r, g, b: 190 < r < 245 and 160 < g < 215 and 100 < b < 170

DRAG, STEPS = 340, 3                                 # طول كل سحبة (بكسل بمقياس 1280) وعددها (ship_drag / ship_steps)
Y0 = 560                                             # خط السحب (عشب فارغ)
CANDS = [(760, 390), (560, 390), (420, 390)]         # مواضع السفينة المحتملة بعد السحب (ship_xy في settings.json)
SLOTS = [((812, 445, 970, 512), (890, 480)), ((240, 445, 466, 512), (355, 480)), ((240, 650, 466, 712), (355, 680)), ((812, 650, 970, 712), (890, 680))]
CANCEL_XY = (777, 695)                               # \"إلغاء\" في نافذة الاستخدام التلقائي — لا نضغط \"استخدام\" أبداً

def city_view(f): return city(f) and f.count((1135, 715, 1255, 785), PARCH) > 150      # المدينة لا الخريطة
def cargo(f): return has_x(f) and f.count((500, 120, 780, 165), RIBBON) > 1500 and f.count((90, 150, 300, 250), WOOD) > 1500
def auto_popup(f): return f.count((500, 120, 780, 165), RIBBON) < 200 and f.count((380, 655, 610, 735), GOLD) > 3000 and f.count((665, 655, 890, 735), BLUE) > 300
def sig(f): return [f.px(x, y) for x in range(300, 1000, 50) for y in range(250, 650, 50)]
def same(a, b): return sum(1 for p, q in zip(a, b) if sum(abs(i - j) for i, j in zip(p, q)) > 90) < len(a) * 0.25

def snap(name):
    try: open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "debug_%s.png" % name), "wb").write(screencap())
    except Exception: pass

def pan(s, d, n):
    for _ in range(n):
        swipe(int((640 - d / 2) * s), int(Y0 * s), int((640 + d / 2) * s), int(Y0 * s), 600); nap(1.3)

def close_all(n=3):
    for _ in range(n):
        f = frame()
        if not has_x(f): return
        tapx(*CLOSE_X, f.s); nap(1.2)

def exchange(log, s):
    n = 0
    for box, xy in SLOTS:
        f = frame()
        if auto_popup(f): tapx(*CANCEL_XY, s); nap(1.2); f = frame()
        if not cargo(f): break
        if f.count(box, BTN) < 800: continue                     # تم التبادل أو مقفل
        tapx(*xy, s); nap(2.5); f = frame()
        if auto_popup(f): tapx(*CANCEL_XY, s); log("السفينة: نقص مورد؛ أُلغي الاستخدام التلقائي"); nap(1.2); continue
        n += 1
    return n

def run(log, cfg):
    f = frame()
    if f.w < f.h: return log("الشاشة عمودية؛ يلزم الوضع الأفقي")
    if not city_view(f): return log("السفينة: لسنا في المدينة؛ تخطّي")
    s = f.s; base = sig(f); d = int(cfg.get("ship_drag") or DRAG); k = int(cfg.get("ship_steps") or STEPS)
    pan(s, d, k)
    try:
        opened = False
        cands = [tuple(c) for c in cfg.get("ship_xy")] if cfg.get("ship_xy") else CANDS
        for xy in cands:
            tapx(*xy, s); nap(2.2); f = frame()
            if cargo(f): opened = True; break
            if has_x(f): tapx(*CLOSE_X, f.s); nap(1.2)       # شاشة فُتحت بالخطأ
        if not opened: snap("ship_open"); return log("السفينة: لم تُفتح شاشة سفينة الشحن (حُفظت debug_ship_open.png)")
        n = exchange(log, s)
        log("السفينة: %d عملية تبادل" % n if n else "السفينة: لا تبادل متاح الآن")
        close_all()
    finally:
        pan(s, -d, k); f = frame()
        if not same(base, sig(f)): snap("ship_home"); log("السفينة: قد لا نكون عدنا لوسط القلعة تماماً (حُفظت debug_ship_home.png)")
