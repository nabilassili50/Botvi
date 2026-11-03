"""صندوق الغموض (الصندوق الأخضر \"جمع\" يسار المدينة): يضغطه، فإن ظهرت نافذة المكافأة يضغط \"استلام\" (ويكرر إن جاء صندوق جاهز بعده)،
وإن ظهر العدّ التنازلي يضغط \"حسنا\". لا يستهلك أي مورد. يعمل في المدينة فقط (على الخريطة لا يظهر الصندوق فيتجاوز)."""
import time
from shizuku import frame, tapx, nap
from tasks.guard import city

GOLD = lambda r, g, b: 150 < r < 255 and 90 < g < 190 and b < 90 and r > g + 40
CHEST = lambda r, g, b: 200 < r < 255 and 150 < g < 215 and b < 90
TIT = lambda r, g, b: r < 90 and 70 < g < 130 and 110 < b < 190
DARK = lambda r, g, b: r < 40 and g < 40 and b < 40

CHEST_XY, BTN_XY = (135, 610), (640, 595)           # الصندوق في المدينة (mystery_xy)، وزر \"استلام\"/\"حسنا\"

def chest(f): return city(f) and f.count((100, 570, 175, 645), CHEST) > 40
def popup(f): return f.count((520, 552, 760, 640), GOLD) > 3000 and f.count((450, 85, 830, 130), TIT) > 2500
def counting(f): return f.count((540, 410, 720, 450), DARK) > 150          # شريط العدّ التنازلي = الصندوق التالي لم يجهز

def run(log, cfg):
    f = frame()
    if f.w < f.h or not chest(f): return
    s = f.s; n = 0
    for _ in range(6):
        tapx(*(cfg.get("mystery_xy") or CHEST_XY), s); nap(1.8); f = frame()
        if not popup(f): log("الغموض: لم تظهر نافذة الصندوق"); return
        if counting(f): tapx(*BTN_XY, s); nap(1.2); log("الغموض: العدّ التنازلي جارٍ" if not n else "الغموض: استُلم %d صندوق" % n); return
        tapx(*BTN_XY, s); n += 1; nap(2); f = frame()
        if popup(f) and counting(f): tapx(*BTN_XY, s); nap(1.2)
        f = frame()
        if not chest(f): break
    log("الغموض: استُلم %d صندوق" % n)
