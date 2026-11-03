"""بوابة الحدود: فتح صناديق الحدود المجانية فقط (النبيل والشجاع). لا يستعمل المفاتيح ولا الجواهر ولا يضغط الصفقة اليومية."""
import os, time
from shizuku import frame, tapx, screencap, nap
from tasks.saga import has_x, CLOSE_X

OPEN = lambda r, g, b: r < 75 and 100 < g < 140 and 115 < b < 165      # زر "فتح" الأزرق المخضر
RIBBON = lambda r, g, b: r > 170 and 40 < g < 90 and 30 < b < 80       # شريط عنوان "صندوق الحدود"
GOLD = lambda r, g, b: 150 < r < 255 and 90 < g < 190 and b < 90 and r > g + 40

BUILD_XY, HEX_XY = (770, 350), (785, 575)        # مبنى البوابة في المدينة ثم الزر السداسي (يمكن تغييرهما في settings.json: border_build / border_hex)
CHEST_BTN = (850, 705)                           # زر "صندوق الحدود" داخل شاشة البوابة
NOBLE, BRAVE = (550, 515, 735, 590), (860, 515, 1048, 590)
NOBLE_XY, BRAVE_XY = (640, 553), (953, 553)
SAFE_XY = (1225, 420)                            # خارج اللوحة: يغلق نافذة المكافأة ولا يضغط شيئاً في الشاشة

def chests(f): return has_x(f) and f.count((400, 95, 880, 135), RIBBON) > 1500
def gate(f): return has_x(f) and f.count((150, 355, 380, 445), GOLD) > 2500 and f.count((400, 95, 880, 135), RIBBON) < 100

def snap(name):
    try: open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "debug_%s.png" % name), "wb").write(screencap())
    except Exception: pass

def back_to_chests(secs=12):
    t = time.time()
    while time.time() - t < secs:
        f = frame()
        if chests(f): return f
        tapx(*SAFE_XY, f.s); nap(1.5)
    return None

def run(log, cfg):
    f = frame()
    if f.w < f.h: return log("الشاشة عمودية؛ يلزم الوضع الأفقي")
    if not chests(f):
        if not gate(f):
            for _ in range(4):
                f = frame()
                if not has_x(f): break
                tapx(*CLOSE_X, f.s); nap(1.2)
            b = cfg.get("border_build") or BUILD_XY; h = cfg.get("border_hex") or HEX_XY
            tapx(*b, f.s); nap(1.2); tapx(*h, f.s); nap(3); f = frame()
            if not gate(f) and not chests(f): snap("border_open"); return log("الحدود: لم تُفتح البوابة (حُفظت debug_border_open.png)")
        if not chests(f):
            tapx(*CHEST_BTN, f.s); nap(2); f = frame()
            if not chests(f): snap("border_chests"); return log("الحدود: لم تُفتح شاشة الصناديق (حُفظت debug_border_chests.png)")
    s = f.s; n = 0
    for _ in range(8):
        f = back_to_chests()
        if f is None: snap("border_lost"); log("الحدود: ضاعت الشاشة (حُفظت debug_border_lost.png)"); break
        if f.count(NOBLE, OPEN) > 1500: tapx(*NOBLE_XY, s); who = "النبيل"
        elif f.count(BRAVE, OPEN) > 1500: tapx(*BRAVE_XY, s); who = "الشجاع"
        else: break
        n += 1; log("الحدود: فتح صندوق " + who); nap(3)
    log("الحدود: فُتح %d صندوق" % n)
    for _ in range(4):
        f = frame()
        if not has_x(f): break
        tapx(*CLOSE_X, f.s); nap(1.2)
