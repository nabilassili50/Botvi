"""ورشة العمل ← إمدادات التشكيل: استلام \"هدية التشكيل\" المجانية فقط. لا يضغط أي زر \"شراء\" أبداً."""
import os, time
from shizuku import frame, tapx, screencap, nap
from tasks.saga import has_x, CLOSE_X

RIBBON = lambda r, g, b: r > 170 and 40 < g < 90 and 30 < b < 80
GOLD = lambda r, g, b: 150 < r < 255 and 90 < g < 190 and b < 90 and r > g + 40
PURP = lambda r, g, b: r > 150 and g < 90 and b > 150
OFFER = lambda r, g, b: r < 80 and 120 < g < 190 and b > 190
AWN = lambda r, g, b: r > 200 and 100 < g < 175 and b < 120

BUILD_XY, HEX_XY = (325, 430), (253, 525)        # مبنى الورشة في المدينة ثم الزر السداسي ذو السندان (workshop_build / workshop_hex)
CARD_XY = (270, 400)                             # بطاقة \"إمدادات التشكيل\" داخل الورشة
FREE_XY, OK_XY = (292, 360), (637, 592)          # زر \"مجاني\" ثم \"حسنا\"

def workshop(f): return has_x(f) and f.count((430, 118, 850, 152), RIBBON) > 1500 and f.count((95, 630, 270, 735), GOLD) > 2500 and f.count((175, 310, 365, 370), AWN) > 150
def supply(f): return has_x(f) and f.count((400, 85, 880, 130), RIBBON) > 2500 and f.count((145, 145, 370, 205), OFFER) > 800
def free_btn(f): return supply(f) and f.count((180, 310, 405, 405), PURP) > 1500
def gift_popup(f): return f.count((515, 545, 760, 637), GOLD) > 3000

def snap(name):
    try: open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "debug_%s.png" % name), "wb").write(screencap())
    except Exception: pass

def run(log, cfg):
    f = frame()
    if f.w < f.h: return log("الشاشة عمودية؛ يلزم الوضع الأفقي")
    if not (supply(f) or workshop(f)):
        for _ in range(4):
            f = frame()
            if not has_x(f): break
            tapx(*CLOSE_X, f.s); nap(1.2)
        b = cfg.get("workshop_build") or BUILD_XY; h = cfg.get("workshop_hex") or HEX_XY
        tapx(*b, f.s); nap(1.2); tapx(*h, f.s); nap(3); f = frame()
    if workshop(f): tapx(*CARD_XY, f.s); nap(2.2); f = frame()
    if not supply(f): snap("workshop_open"); return log("الورشة: لم تُفتح إمدادات التشكيل (حُفظت debug_workshop_open.png)")
    s = f.s; n = 0
    for _ in range(4):
        f = frame()
        if gift_popup(f): tapx(*OK_XY, s); nap(1.5); continue
        if not free_btn(f): break
        tapx(*FREE_XY, s); n += 1; log("الورشة: استلام الهدية المجانية"); nap(2.5)
    for _ in range(3):                       # أغلق نافذة المكافأة إن بقيت
        f = frame()
        if gift_popup(f): tapx(*OK_XY, s); nap(1.5)
    if not n: log("الورشة: لا هدية مجانية الآن")
    for _ in range(4):
        f = frame()
        if not has_x(f): break
        tapx(*CLOSE_X, f.s); nap(1.2)
