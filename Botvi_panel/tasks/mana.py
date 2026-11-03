"""تكرير المانا: منجم المانا ← تكرير المانا ← زر "تكرير" حتى حد اليوم (5)."""
import time
from shizuku import frame, tapx, nap
from tasks.saga import has_x, CLOSE_X

GOLD = lambda r, g, b: 150 < r < 235 and 90 < g < 170 and 20 < b < 90 and r > g + 40
RED = lambda r, g, b: r > 190 and g < 110 and b < 110
RIBBON = lambda r, g, b: r > 150 and g < 90 and b < 90
HEX = lambda r, g, b: b > 110 and g > 80 and r < 60

MINE_XY, HEX_XY, BOX_XY = (580, 375), (505, 465), (412, 400)   # المنجم في المدينة، أول زر سداسي، مربع "تكرير المانا"
REFINE_XY, USE_XY = (437, 700), (493, 722)

def ribbon(f): return f.count((500, 120, 780, 165), RIBBON)
def hex_menu(f): return f.count((470, 440, 700, 500), HEX) > 800
def mine_screen(f): return ribbon(f) > 1500 and f.count((95, 630, 270, 740), GOLD) > 2000
def refine_screen(f): return ribbon(f) > 1500 and f.count((320, 665, 555, 735), GOLD) > 2500 and f.count((95, 630, 270, 740), GOLD) < 300
def popup(f): return ribbon(f) < 200 and f.count((380, 685, 610, 765), GOLD) > 2800
def limit(f): return f.count((320, 628, 560, 655), RED) > 25

def close_all(log, n=4):
    for _ in range(n):
        f = frame()
        if not has_x(f): return f
        tapx(*CLOSE_X, f.s); nap(1.2)
    return frame()

def run(log, cfg):
    f = close_all(log)
    if f.w < f.h: return log("الشاشة عمودية؛ يلزم الوضع الأفقي")
    s = f.s
    tapx(*MINE_XY, s); nap(1.2); f = frame()
    if not hex_menu(f): return log("المانا: لم تظهر أزرار المنجم (تأكد من موضع المدينة)")
    tapx(*HEX_XY, s); nap(1.8); f = frame()
    if not mine_screen(f): return log("المانا: لم تُفتح شاشة المنجم")
    tapx(*BOX_XY, s); nap(1.5); f = frame()
    if not refine_screen(f): return log("المانا: لم تُفتح شاشة التكرير")
    if limit(f): log("المانا: بلغنا حد اليوم"); close_all(log); return "limit"
    done = 0
    for _ in range(6):
        tapx(*REFINE_XY, s); nap(1.5); f = frame()
        if popup(f): tapx(*USE_XY, s); nap(1.5); f = frame()
        if refine_screen(f): done += 1
        if limit(f): break
        if not refine_screen(f): log("المانا: خرجنا من شاشة التكرير"); break
    log("المانا: %d عملية تكرير" % done)
    close_all(log)
    return "limit" if limit(f) else None
