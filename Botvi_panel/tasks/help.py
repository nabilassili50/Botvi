"""مساعدات التحالف: إن كنت في المدينة أو الخريطة وظهرت شارة حمراء على زر المصافحة (يسار الشاشة) يضغطه ثم يضغط زر \"مساعدة الكل\" إن فُتحت قائمة.
لا يستهلك أي مورد. إن لم تكن في المدينة/الخريطة يتجاوز بصمت (الحارس يعيدك إليها قبل المهمة)."""
import os, time
from shizuku import frame, tapx, screencap, nap
from tasks.saga import has_x, CLOSE_X
from tasks.guard import city

RED = lambda r, g, b: r > 190 and g < 80 and b < 80
BTN = lambda r, g, b: r > 200 and 120 < g < 215 and b < 100                  # الزر البرتقالي/الذهبي الكبير
HELP_XY, BADGE = (35, 612), (48, 570, 84, 602)                              # زر المصافحة وشارته (help_xy في settings.json)
AREA = (200, 520, 1100, 790)                                               # أين يُتوقع زر \"مساعدة الكل\"

def badge(f): return f.count(BADGE, RED, 1) > 100

def snap(name):
    try: open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "debug_%s.png" % name), "wb").write(screencap())
    except Exception: pass

def blob(f):
    n = sx = sy = 0
    for x in range(AREA[0], AREA[2], 4):
        for y in range(AREA[1], AREA[3], 4):
            if BTN(*f.px(x, y)): n += 1; sx += x; sy += y
    return (sx // n, sy // n) if n > 120 else None

def run(log, cfg):
    f = frame()
    if f.w < f.h or not city(f) or not badge(f): return
    s = f.s; xy = cfg.get("help_xy") or HELP_XY
    tapx(*xy, s); nap(2); f = frame()
    if has_x(f):                                   # فُتحت قائمة المساعدات
        b = blob(f)
        if not b: snap("help_panel"); log("المساعدات: فُتحت القائمة ولم أجد زر مساعدة الكل (حُفظت debug_help_panel.png)")
        else:
            tapx(b[0], b[1], s); nap(1.5); log("المساعدات: مساعدة الكل")
        for _ in range(3):
            f = frame()
            if not has_x(f): break
            tapx(*CLOSE_X, f.s); nap(1.2)
    else:
        log("المساعدات: ضُغط زر المصافحة" + ("" if not badge(frame()) else " (الشارة ما زالت ظاهرة؛ تحقّق)"))
