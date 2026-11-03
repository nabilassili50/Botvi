"""علاج الجنود في المستشفى: اختيار الكل ← معالجة ← (اختياري) استخدام التسريع التلقائي. لا يستخدم الجواهر أبداً."""
import time
from shizuku import frame, tapx, nap
from tasks.saga import has_x, CLOSE_X

GOLD = lambda r, g, b: 150 < r < 255 and 90 < g < 190 and b < 90 and r > g + 40
KNOB = lambda r, g, b: 120 < r < 200 and 95 < g < 170 and 40 < b < 110 and r > b + 55
REDC = lambda r, g, b: r > 170 and g < 70 and b < 70
BLUE = lambda r, g, b: r < 60 and 90 < g < 150 and b > 170
RIBBON = lambda r, g, b: r > 150 and g < 90 and b < 90

HOSP_XY, HEX_XY = (655, 435), (585, 512)       # المستشفى في المدينة، أول زر سداسي (علاج)
SELALL_XY, HEAL_XY = (1115, 703), (650, 700)
FF_XY, AUTO_XY, USE_XY = (683, 410), (346, 420), (493, 732)

def hospital(f): return f.count((500, 120, 780, 165), RIBBON) > 1500 and f.count((530, 665, 765, 740), GOLD) > 2000 and f.count((95, 630, 270, 740), GOLD) > 3000
def wounded(f): return f.count((760, 195, 795, 230), REDC) > 10          # توجد صفوف جنود مصابين
def selected(f): return f.count((600, 240, 645, 275), KNOB) > 8          # المؤشرات في أقصى اليسار
def speed_screen(f): return f.count((250, 378, 445, 465), GOLD) > 2500
def use_popup(f): return f.count((380, 690, 610, 775), GOLD) > 3000 and f.count((250, 378, 445, 465), GOLD) < 500
def ff_icon(f): return f.count((655, 385, 712, 436), BLUE) > 100

def run(log, cfg):
    f = frame()
    if f.w < f.h: return log("الشاشة عمودية؛ يلزم الوضع الأفقي")
    s = f.s
    if not hospital(f):
        for _ in range(4):
            f = frame()
            if not has_x(f): break
            tapx(*CLOSE_X, s); nap(1.2)
        tapx(*HOSP_XY, s); nap(1.2); tapx(*HEX_XY, s); nap(2); f = frame()
        if not hospital(f): return log("العلاج: لم تُفتح شاشة المستشفى")
    if not wounded(f): log("العلاج: لا جنود مصابون"); tapx(*CLOSE_X, s); return
    if not selected(f):
        tapx(*SELALL_XY, s); nap(1); f = frame()
        if not selected(f): return log("العلاج: فشل اختيار الكل")
    tapx(*HEAL_XY, s); nap(2); f = frame()
    if use_popup(f): tapx(*USE_XY, s); nap(2); f = frame()     # نافذة استخدام الموارد إن ظهرت
    log("العلاج: بدأ علاج الجنود")
    if cfg.get("heal_speed", True):
        if not ff_icon(f): log("العلاج: زر التسريع غير ظاهر"); return
        tapx(*FF_XY, s); nap(1.5); f = frame()
        if not speed_screen(f): return log("العلاج: لم تُفتح شاشة التسريع")
        tapx(*AUTO_XY, s); nap(1.5); f = frame()
        if use_popup(f): tapx(*USE_XY, s); nap(2.5)
        f = frame()
        log("العلاج: تم التسريع" if hospital(f) and not wounded(f) else "العلاج: تحقّق من اكتمال التسريع")
    for _ in range(3):
        f = frame()
        if not has_x(f): break
        tapx(*CLOSE_X, s); nap(1.2)
