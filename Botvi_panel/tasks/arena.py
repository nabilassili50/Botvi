"""ميدان الأبطال: جمع مكافآت الترتيب ثم تحدّي الخصم الأول حتى تنتهي محاولات اليوم. لا يشتري محاولات أبداً."""
import os, time
from shizuku import frame, tapx, screencap, nap
from tasks.saga import has_x, CLOSE_X

TEAL = lambda r, g, b: r < 70 and 90 < g < 150 and 120 < b < 190
GOLD = lambda r, g, b: 150 < r < 255 and 90 < g < 190 and b < 90 and r > g + 40
RED = lambda r, g, b: r > 150 and g < 70 and b < 70

ARENA_XY, HEX_XY = (810, 350), (808, 455)         # مبنى الميدان في المدينة، الزر السداسي ذو السيفين
RANK_XY, COLLECT_XY = (1007, 490), (640, 600)     # صندوق الرتبة، زر "جمع"
CHALLENGE = [(237, 465), (237, 590), (237, 715)]  # أزرار "تحدي" الثلاثة
DEPLOY_XY = (1078, 628)                           # زر "نشر"

def arena(f): return f.count((145, 430, 328, 500), TEAL) > 1500 and f.count((145, 680, 328, 750), TEAL) > 1500 and f.count((890, 685, 1130, 765), GOLD) > 2500
def reward_popup(f): return f.count((520, 550, 760, 640), GOLD) > 3500 and f.count((145, 430, 328, 500), TEAL) < 100
def vs_popup(f): return f.count((955, 578, 1203, 676), GOLD) > 2000 and f.count((145, 430, 328, 500), TEAL) < 500
def no_attempts(f): return f.count((1000, 600, 1050, 650), RED) > 30 and f.count((875, 590, 935, 650), RED) > 150
def alert(f): return f.count((845, 425, 895, 475), GOLD) > 60

def snap(name):
    try: open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "debug_%s.png" % name), "wb").write(screencap())
    except Exception: pass

def wait_arena(log, secs=60):
    t = time.time()
    while time.time() - t < secs:
        f = frame()
        if arena(f): return f
        if reward_popup(f): tapx(*COLLECT_XY, f.s)
        elif time.time() - t > 12: tapx(640, 760, f.s)      # تجاوز شاشة النتيجة (غير معروفة بعد)
        nap(3)
    return None

def run(log, cfg):
    f = frame()
    if f.w < f.h: return log("الشاشة عمودية؛ يلزم الوضع الأفقي")
    if not arena(f):
        for _ in range(4):                       # أغلق أي شاشة مفتوحة للعودة للمدينة
            f = frame()
            if not has_x(f): break
            tapx(*CLOSE_X, f.s); nap(1.2)
        tapx(*ARENA_XY, f.s); nap(1.2); tapx(*HEX_XY, f.s); nap(2); f = frame()
        if not arena(f): snap("arena_open"); return log("الميدان: لم تُفتح الشاشة (حُفظت debug_arena_open.png)")
    s = f.s
    if alert(f):                                  # مكافآت الترتيب
        tapx(*RANK_XY, s); nap(1.5); f = frame()
        if reward_popup(f): tapx(*COLLECT_XY, s); nap(1.5); log("الميدان: جُمعت مكافآت الترتيب")
        f = wait_arena(log, 10) or frame()
    done = 0
    for _ in range(6):
        if not arena(f): f = wait_arena(log) 
        if f is None: snap("arena_lost"); return log("الميدان: ضاعت الشاشة (حُفظت debug_arena_lost.png)")
        if no_attempts(f): log("الميدان: انتهت محاولات اليوم"); break
        tapx(*CHALLENGE[int(cfg.get("arena_pick", 0))], s); nap(1.8); f = frame()
        if not vs_popup(f): snap("arena_vs"); return log("الميدان: لم تظهر نافذة النشر (حُفظت debug_arena_vs.png)")
        tapx(*DEPLOY_XY, s); log("الميدان: بدأت معركة"); done += 1
        nap(8); f = wait_arena(log, 80)
    log("الميدان: %d معركة" % done)
    for _ in range(3):
        f = frame()
        if not has_x(f): break
        tapx(*CLOSE_X, f.s); nap(1.2)
