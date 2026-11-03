"""لوحة النرد (القبة الزجاجية): رمي مجاني فقط، ثم \"بدء\" لكل معركة تظهر. لا يرمي بالعملة أبداً."""
import os, time
from shizuku import frame, tapx, screencap, nap
from tasks.saga import has_x, CLOSE_X

GOLD = lambda r, g, b: 150 < r < 255 and 90 < g < 190 and b < 90 and r > g + 40
RED = lambda r, g, b: r > 130 and g < 70 and b < 70
GREEN = lambda r, g, b: g > 140 and r < 140 and b < 90          # أيقونة النبتة الخضراء = رمية مدفوعة
BROWN = lambda r, g, b: 90 < r < 190 and 50 < g < 120 and 20 < b < 80
TEAL = lambda r, g, b: r < 90 and 140 < g < 200 and 160 < b < 220  # زر 3x

BUILD_XY, HEX_XY = (895, 385), (893, 607)      # مبنى مملكة تايكون في المدينة (اسمه ظهر في اللقطة)، ثم الزر السداسي ذو العملة
BTN_XY, START_XY = (137, 720), (137, 720)      # الزر السفلي: مجاني / توقف / بدء
BTN_A, BTN_B = (40, 675, 235, 770), (40, 598, 235, 660)

def board(f): return has_x(f) and f.count((30, 410, 90, 460), TEAL) > 200
def stop_btn(f): return f.count(BTN_A, RED) > 1500
def free_roll(f): return f.count(BTN_A, GOLD) > 2000 and f.count(BTN_A, GREEN) < 30 and f.count(BTN_B, BROWN) < 300
def battle(f): return f.count(BTN_A, GOLD) > 2000 and f.count(BTN_B, BROWN) > 300
def paid_roll(f): return f.count(BTN_A, GOLD) > 2000 and f.count(BTN_A, GREEN) >= 30

def snap(name):
    try: open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "debug_%s.png" % name), "wb").write(screencap())
    except Exception: pass

def settle(secs=40):
    """انتظر حتى تعود اللوحة إلى حالة مستقرة (رمية/بدء/لا شيء)."""
    t = time.time()
    while time.time() - t < secs:
        f = frame()
        if board(f) and (free_roll(f) or battle(f) or paid_roll(f)): return f
        if not board(f) and time.time() - t > 10: tapx(640, 760, f.s)   # تجاوز شاشة نتيجة المعركة/المكافأة
        nap(2.5)
    return None

def run(log, cfg):
    f = frame()
    if f.w < f.h: return log("الشاشة عمودية؛ يلزم الوضع الأفقي")
    if not board(f):
        for _ in range(4):
            f = frame()
            if not has_x(f): break
            tapx(*CLOSE_X, f.s); nap(1.2)
        tapx(*BUILD_XY, f.s); nap(1.2); tapx(*HEX_XY, f.s); nap(3); f = frame()
        if not board(f): snap("dice_open"); return log("النرد: لم تُفتح اللوحة (حُفظت debug_dice_open.png)")
    s = f.s; rolls = 0; fights = 0
    for _ in range(25):
        f = settle()
        if f is None: snap("dice_lost"); log("النرد: ضاعت الشاشة (حُفظت debug_dice_lost.png)"); break
        if battle(f):
            tapx(*START_XY, s); fights += 1; log("النرد: بدء معركة"); nap(8); continue
        if paid_roll(f): log("النرد: انتهت الرميات المجانية"); break
        tapx(*BTN_XY, s); rolls += 1; nap(1.5)
        f = frame()
        if stop_btn(f): tapx(*BTN_XY, s)
        nap(4)
    log("النرد: %d رمية، %d معركة" % (rolls, fights))
    for _ in range(3):
        f = frame()
        if not has_x(f): break
        tapx(*CLOSE_X, f.s); nap(1.2)
