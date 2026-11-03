"""هدايا التحالف: التحالف ← \"مستوى الهدية\" ← تبويبي \"هدية التحالف\" و\"صندوق المكافآت\": يضغط زر \"فتح الكل\" (الصندوق بسهم أخضر) ثم يفتح ما تبقى صفاً صفاً مع التمرير.
لا يضغط \"مسح\"/سلة المحذوفات إلا إن فعّلت gifts_clear (يمسح الهدايا المفتوحة فقط). لا يستهلك أي مورد."""
import os, time
from shizuku import frame, tapx, screencap, swipe, nap
from tasks.saga import has_x, CLOSE_X
from tasks.guard import popup_x, city

RED = lambda r, g, b: r > 150 and g < 80 and b < 80
BROWN = lambda r, g, b: 120 < r < 190 and 70 < g < 120 and 30 < b < 80 and r > g + 40
TITLE = lambda r, g, b: r < 50 and 120 < g < 160 and 160 < b < 200
TABC = lambda r, g, b: r < 80 and 150 < g < 200 and b > 200
WHITE = lambda r, g, b: r > 170 and g > 185 and b > 185

ALLIANCE_XY, GIFT_XY = (672, 745), (345, 320)       # زر التحالف في الشريط السفلي، وزر \"مستوى الهدية\" داخل شاشة التحالف
OPEN_ALL_XY, TRASH_XY = (213, 172), (340, 172)
TABS = [("هدية التحالف", (630, 268), (480, 245, 780, 292)), ("صندوق المكافآت", (307, 268), (155, 245, 460, 292))]
ROWS = [338 + 124 * i for i in range(4)]            # مراكز صفوف القائمة عند أعلى القائمة

def gifts(f): return has_x(f) and f.count((290, 145, 395, 205), RED) > 300 and f.count((500, 80, 780, 125), TITLE) > 1000
def alliance(f): return has_x(f) and f.count((290, 145, 395, 205), RED) < 60 and f.count((245, 275, 450, 315), BROWN) > 150 and f.count((500, 80, 780, 125), TITLE) > 1000
def row_state(f, y):
    """open = زر \"فتح\" (نص أبيض على أزرق)، done = زر \"مسح\" الأحمر، none = لا صف."""
    box = (150, y - 27, 295, y + 27)
    if f.count(box, RED) > 300: return "done"
    return "open" if f.count((190, y - 15, 255, y + 15), WHITE, 1) > 25 else "none"
def sig(f): return [f.px(x, y) for x in range(330, 760, 70) for y in range(310, 770, 40)]
def same(a, b): return sum(1 for p, q in zip(a, b) if sum(abs(i - j) for i, j in zip(p, q)) > 90) < len(a) * 0.15

def snap(name):
    try: open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "debug_%s.png" % name), "wb").write(screencap())
    except Exception: pass

def close_all(n=4):
    for _ in range(n):
        f = frame()
        if not has_x(f): return
        tapx(*CLOSE_X, f.s); nap(1.2)

def settle(s):
    """أغلق نافذة المكافأة/التأكيد الطارئة وارجع لشاشة الهدايا. يعيد True إن عدنا إليها."""
    for _ in range(3):
        f = frame()
        if gifts(f): return True
        p = popup_x(f)
        if p: tapx(p[0], p[1], s)
        else: tapx(640, 760, s)
        nap(1.5)
    return gifts(frame())

def do_tab(log, s, name, xy, box, clear):
    tapx(*xy, s); nap(1.5)
    if not settle(s): return log("الهدايا: خرجنا من الشاشة")
    f = frame(); n = 0
    if f.count(box, TABC) < 300: return log("الهدايا: تعذّر فتح تبويب " + name)
    if any(row_state(f, y) == "open" for y in ROWS):
        tapx(*OPEN_ALL_XY, s); nap(2); n += 1
        if not settle(s): return log("الهدايا: خرجنا من الشاشة بعد فتح الكل")
    still = 0
    for _ in range(30):
        f = frame(); todo = [y for y in ROWS if row_state(f, y) == "open"]
        if todo:
            tapx(250, todo[0], s); nap(1.6); n += 1; still += 1
            if not settle(s): return log("الهدايا: خرجنا من الشاشة")
            if still > 60: break
            continue
        a = sig(f); swipe(int(450 * s), int(700 * s), int(450 * s), int(330 * s), 500); nap(1.3)
        if same(a, sig(frame())): break
    log("الهدايا: %s — %d عملية فتح" % (name, n))
    if clear and n: tapx(*TRASH_XY, s); nap(1.5); settle(s)

def run(log, cfg):
    f = frame()
    if f.w < f.h: return log("الشاشة عمودية؛ يلزم الوضع الأفقي")
    s = f.s
    if not gifts(f):
        if not (alliance(f) or city(f)): close_all()
        f = frame()
        if city(f): tapx(*ALLIANCE_XY, s); nap(2); f = frame()
        if alliance(f): tapx(*GIFT_XY, s); nap(2); f = frame()
        if not gifts(f): snap("gifts_open"); close_all(); return log("الهدايا: لم تُفتح شاشة هدايا التحالف (حُفظت debug_gifts_open.png)")
    for name, xy, box in TABS: do_tab(log, s, name, xy, box, cfg.get("gifts_clear", False))
    close_all()
