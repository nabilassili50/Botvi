"""مغارة الظلام: ضغط زر "استخدام مجاني" فقط. لا يضغط الاستخدام المدفوع أبداً."""
import time
from shizuku import frame, tapx, nap
from tasks.saga import has_x, CLOSE_X

BAR = lambda r, g, b: r > 150 and g < 40 and b < 40          # شريط صحة الزعيم
GLOW = lambda r, g, b: r > 240 and g > 200 and b < 120       # توهّج زر المجاني

CAVE_XY, HEX_XY, FREE_XY = (775, 470), (737, 570), (640, 680)

def cave(f): return has_x(f) and f.count((430, 100, 820, 127), BAR) > 500
def free(f): return f.count((535, 600, 750, 765), GLOW) > 100

def run(log, cfg):
    f = frame()
    if f.w < f.h: return log("الشاشة عمودية؛ يلزم الوضع الأفقي")
    s = f.s
    if not cave(f):
        for _ in range(4):
            f = frame()
            if not has_x(f): break
            tapx(*CLOSE_X, s); nap(1.2)
        tapx(*CAVE_XY, s); nap(1.2); tapx(*HEX_XY, s); nap(3); f = frame()
        if not cave(f): return log("المغارة: لم تُفتح الشاشة")
    n = 0
    for _ in range(3):
        if not free(f): break
        tapx(*FREE_XY, s); n += 1; log("المغارة: هجوم مجاني"); nap(5); f = frame()
    if not n: log("المغارة: لا هجوم مجاني متاح")
    for _ in range(3):
        f = frame()
        if not has_x(f): break
        tapx(*CLOSE_X, s); nap(1.2)
