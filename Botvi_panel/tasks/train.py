"""تدريب القوات في الثكنة: يختار النوع والدرجة من اللوحة ثم يضغط \"درب\" بالكمية القصوى. لا يضغط إنهاء الآن ولا زيادة السرعة ولا الإلغاء."""
import os, time
from shizuku import frame, tapx, screencap, nap
from tasks.saga import has_x, CLOSE_X

RIBBON = lambda r, g, b: r > 170 and 40 < g < 90 and 30 < b < 80
GOLD = lambda r, g, b: 150 < r < 255 and 90 < g < 190 and b < 90 and r > g + 40
BLUE = lambda r, g, b: r < 60 and 90 < g < 150 and 150 < b < 220

BUILD_XY, HEX_XY = (545, 230), (478, 300)          # مبنى الثكنة في المدينة، ثم الزر السداسي (تدريب)
TYPES = {"infantry": 998, "archer": 760, "cavalry": 520, "siege": 280}   # أعمدة البطاقات من اليمين: مشاة، رماة، فرسان، محاصِرون
CARD_Y, PITCH = 400, 285                            # وسط صف البطاقات، والمسافة بين درجة وأخرى
TRAIN_XY = (170, 675)                               # زر "درب" داخل شاشة التدريب

def barracks(f): return has_x(f) and f.count((430, 118, 850, 152), RIBBON) > 1500 and f.count((95, 630, 270, 735), GOLD) > 2500
def train_idle(f): return has_x(f) and f.count((430, 118, 850, 152), RIBBON) < 100 and f.count((40, 630, 300, 720), GOLD) > 3000
def training(f): return has_x(f) and f.count((40, 630, 300, 720), BLUE) > 3000

def snap(name):
    try: open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "debug_%s.png" % name), "wb").write(screencap())
    except Exception: pass

def drag(s, up, ms=1600):
    """سحب بطيء (بلا قذف) لقائمة البطاقات: up=True يرفع القائمة بمقدار درجة واحدة، وإلا ينزلها إلى الأعلى."""
    from shizuku import swipe
    if up: swipe(600 * s, 600 * s, 600 * s, (600 - PITCH) * s, ms)
    else: swipe(600 * s, 260 * s, 600 * s, 700 * s, 700)

def run(log, cfg):
    f = frame()
    if f.w < f.h: return log("الشاشة عمودية؛ يلزم الوضع الأفقي")
    typ = cfg.get("train_type", "infantry"); tier = int(cfg.get("train_tier", 4)); first = int(cfg.get("train_first_tier", 1))
    if typ not in TYPES: return log("التدريب: نوع غير معروف " + str(typ))
    if not barracks(f):
        if training(f) or train_idle(f): tapx(*CLOSE_X, f.s); nap(1.5); f = frame()
    if not barracks(f):
        for _ in range(4):
            f = frame()
            if not has_x(f): break
            tapx(*CLOSE_X, f.s); nap(1.2)
        b = cfg.get("train_build") or BUILD_XY; h = cfg.get("train_hex") or HEX_XY
        tapx(*b, f.s); nap(1.2); tapx(*h, f.s); nap(3); f = frame()
        if not barracks(f): snap("train_open"); return log("التدريب: لم تُفتح الثكنة (حُفظت debug_train_open.png)")
    s = f.s
    for _ in range(3): drag(s, False); nap(0.6)               # إلى أعلى القائمة
    k = max(0, tier - first)
    for _ in range(k): drag(s, True); nap(0.8)
    nap(0.8)
    tapx(TYPES[typ], CARD_Y, s); nap(2); f = frame()
    if training(f): log("التدريب: هناك تدريب جارٍ لهذا النوع"); snap("train_busy")
    elif train_idle(f):
        tapx(*TRAIN_XY, s); nap(2); f = frame()
        log("التدريب: بدأ تدريب %s درجة %d" % (typ, tier) if training(f) else "التدريب: ضغطت درب ولم أتأكد من البدء (حُفظت debug_train_check.png)")
        if not training(f): snap("train_check")
    else: snap("train_card"); log("التدريب: لم تفتح بطاقة القوات (مقفلة أو درجة خاطئة) (حُفظت debug_train_card.png)")
    for _ in range(4):
        f = frame()
        if not has_x(f): break
        tapx(*CLOSE_X, f.s); nap(1.2)
