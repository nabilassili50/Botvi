"""المصنع القمري ← تصنيع \"الأسلحة المضيئة\": فتح شاشة التصنيع، تطبيق طقم تسريع التصنيع (التبديل السريع) ثم زر \"تصنيع\".
لا يضغط \"تصنيع الآن\" ولا أي زر يستهلك الجواهر أبداً. وإن فعّلت lunar_skip_short يتجاوز الجولة عند نقص الموارد (أرقام حمراء)."""
import os, time
from shizuku import frame, tapx, screencap, nap
from tasks.saga import has_x, CLOSE_X

RIBBON = lambda r, g, b: r > 150 and g < 90 and b < 90
GOLD = lambda r, g, b: 150 < r < 255 and 90 < g < 190 and b < 90 and r > g + 40
BLUE = lambda r, g, b: r < 80 and 90 < g < 190 and b > 150
REDTXT = lambda r, g, b: r > 170 and g < 120 and b < 120
TITLE = lambda r, g, b: r < 60 and b > 110 and b > g + 30

BUILD_XY, HEX_XY = (1005, 400), (950, 483)        # المصنع القمري في المدينة ثم الزر السداسي الأول (lunar_build / lunar_hex)
CRAFT_XY = (475, 700)                             # زر \"تصنيع\" الذهبي (يسار) — ليس \"تصنيع الآن\" الأزرق على اليمين
GO_XY, KEEP_XY = (640, 382), (640, 455)           # نافذة الملاحظة: \"اذهب للتغيير\" / \"إبقاء المعدات الحالية\"
APPLY_XY = (250, 232)                             # التبديل السريع: زر \"تطبيق\" للصف الأول (طقم تصنيع الأسلحة)

def craft_screen(f): return has_x(f) and f.count((500, 120, 780, 165), RIBBON) > 1500 and f.count((365, 670, 585, 735), GOLD) > 1500 and f.count((95, 630, 270, 735), GOLD) < 300
def info_screen(f): return has_x(f) and f.count((500, 120, 780, 165), RIBBON) > 1500 and f.count((95, 630, 270, 735), GOLD) > 2000
def prompt(f): return f.count((500, 120, 780, 165), RIBBON) < 200 and f.count((440, 362, 840, 402), GOLD) > 2000 and f.count((440, 434, 840, 476), BLUE) > 600
def swap_screen(f): return has_x(f) and f.count((120, 125, 1100, 170), TITLE) > 5000
def short(f): return f.count((290, 340, 1010, 455), REDTXT) > 6      # رقم أحمر = مورد ناقص

def snap(name):
    try: open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "debug_%s.png" % name), "wb").write(screencap())
    except Exception: pass

def close_all(n=4):
    for _ in range(n):
        f = frame()
        if not has_x(f): return
        tapx(*CLOSE_X, f.s); nap(1.2)

def run(log, cfg):
    f = frame()
    if f.w < f.h: return log("الشاشة عمودية؛ يلزم الوضع الأفقي")
    s = f.s
    if not craft_screen(f):
        close_all()
        b = cfg.get("lunar_build") or BUILD_XY; h = cfg.get("lunar_hex") or HEX_XY
        tapx(*b, s); nap(1.2); tapx(*h, s); nap(2.5); f = frame()
    if info_screen(f): snap("lunar_info"); close_all(); return log("المصنع القمري: فُتحت شاشة المعلومات بدل التصنيع (حُفظت debug_lunar_info.png)")
    if not craft_screen(f): snap("lunar_open"); close_all(); return log("المصنع القمري: لم تُفتح شاشة التصنيع أو أن التصنيع جارٍ (حُفظت debug_lunar_open.png)")
    if cfg.get("lunar_skip_short", False) and short(f): close_all(); return log("المصنع القمري: الموارد غير كافية؛ تخطّي دون استخدام جواهر")
    swap = cfg.get("lunar_swap", True); applied = False; tapped = 0
    for _ in range(7):
        f = frame()
        if prompt(f):
            if swap and not applied: tapx(*GO_XY, s); log("المصنع القمري: الذهاب لتبديل المعدات")
            else: tapx(*KEEP_XY, s)
            nap(2); continue
        if swap_screen(f):
            tapx(*APPLY_XY, s); applied = True; log("المصنع القمري: تطبيق طقم تصنيع الأسلحة"); nap(2.5); continue
        if craft_screen(f):
            if tapped >= 2: log("المصنع القمري: ضغطنا تصنيع ولم يبدأ؛ تحقّق يدوياً"); break
            tapx(*CRAFT_XY, s); tapped += 1; nap(1.8); continue
        break
    f = frame()
    if tapped and not craft_screen(f) and not prompt(f) and not swap_screen(f): log("المصنع القمري: ضُغط تصنيع (بدأ على الأرجح؛ راجع لقطة الشاشة)")
    elif not tapped: log("المصنع القمري: لم يُضغط زر التصنيع")
    close_all()
