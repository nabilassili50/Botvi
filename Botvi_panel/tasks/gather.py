"""جمع الموارد (تعمل بعد باقي المهام): يفتح مخطط مناطق الموارد، ينتقل إلى نطاق المستوى المحدد، يبحث عن مورد
بالمستوى والنوع المطلوبين (شارة الرقم الزرقاء + أيقونة النافذة)، يضغط \"جمع\" ثم \"الدرجة الأدنى\" ثم \"نشر\".
الإعدادات من اللوحة: gather_type (stone/wood/ore/food/gold/any) و gather_level (1-5) و gather_count (عدد المسيرات).
لا يستعمل الجواهر ولا أي تسريع، ويعود إلى المدينة في النهاية."""
import os, time
from shizuku import frame, tapx, back, screencap, swipe, nap
from tasks.saga import has_x, CLOSE_X
import tasks.guard as guard

# ---------- إحداثيات (مقياس 1280x800) ----------
MAP_BTN = (1195, 745)            # زر التبديل بين المدينة والخريطة (أسفل اليمين)
TELESCOPE_XY = (1245, 583)       # المنظار أسفل اليمين: يفتح نظرة عامة على المملكة (الأساسي)
OVERVIEW_XY = (437, 95)          # بديل: أيقونة اللفافة بجانب الإحداثيات
OV_TOGGLE = (1092, 720)          # زر لفافة القمح داخل النظرة العامة: يبدّل إلى \"مخطط مناطق الموارد\"
DIALOG_X = (385, 130)            # زر إغلاق نافذة المورد (معين أحمر أعلى يسار النافذة)
GATHER_XY = (640, 437)           # زر \"جمع\" في نافذة المورد
LOW_XY = (197, 495)              # زر \"الدرجة الأدنى\" في شاشة المسيرة
DEPLOY_XY = (243, 635)           # زر \"نشر\"
CC = (640, 400)                  # مركز المخطط
MID = {4: 115, 3: 191, 2: 267, 1: 340}        # نصف قطر وسط كل حلقة (المستوى 1 الأبعد، 5 المركز)
L5_POINTS = [(635, 455), (640, 350), (600, 400), (680, 400)]      # المستوى 5: حول القلعة
NODE_OFFSETS = [(-26, 0), (-14, -14), (-40, 10)]                  # موضع المورد بالنسبة لزاوية الشارة
EXCL = [(80, 235, 150, 300), (1040, 640, 1135, 690), (1120, 690, 1280, 800)]   # عناصر واجهة زرقاء تُتجاهل

# ---------- ألوان ----------
FACE = lambda r, g, b: abs(r - 43) < 11 and abs(g - 124) < 14 and abs(b - 172) < 16     # وجه شارة المستوى
WHITE = lambda r, g, b: r > 175 and g > 175 and b > 175
TEAL = lambda r, g, b: r < 75 and 110 < g < 175 and b > 140 and b > r + 80               # زر \"جمع\"
ORANGE = lambda r, g, b: r > 190 and 120 < g < 205 and b < 95                            # زر \"نشر\" (أغمق قبل تحديد الجنود)
NONBLUE = lambda r, g, b: not (r < 80 and 115 < g < 175 and b > 165)                     # أيقونة داخل زر \"الدرجة الأدنى\"
GRAY = lambda r, g, b: abs(r - g) < 14 and abs(g - b) < 18 and 70 < r < 200
BROWN = lambda r, g, b: 90 < r < 185 and 50 < g < 125 and b < 85 and r > g + 25
YEL = lambda r, g, b: r > 200 and g > 150 and b < 110
TL = lambda r, g, b: g > r + 25 and b > r + 25 and g > 120 and abs(g - b) < 30           # فيروزي: بلورات الحديد

# ---------- قوالب الأرقام (مأخوذة من لقطاتك؛ الرقم 5 مرسوم يدوياً) ----------
T = {
    1: ["..##..", ".###..", "...#..", "...#..", "...#..", "...#..", "...#..", "...#..", "..##..", "######"],
    2: [".####.", ".####.", "....##", "....##", "....#.", "...#..", "..#...", ".#....", "##....", "######"],
    3: ["..###.", "..###.", "....#.", "....#.", "..###.", "..####", ".....#", ".....#", "....#.", "####.."],
    4: ["...##.", "..###.", ".#.##.", ".#.##.", "#..##.", "#..##.", "######", "...##.", "...##.", "...#.."],
    5: [".#####", ".####.", ".#....", ".###..", ".####.", "....##", ".....#", ".....#", ".#..##", ".####."],
}
TYPES = {"stone": "حجر", "wood": "خشب", "ore": "حديد", "food": "قمح", "gold": "ذهب", "any": "أي نوع"}
DEBUG = [True]    # حفظ لقطة عند كل خطوة (debug_gather_step_*.png) لتسهيل التصحيح
NOMARCH = [0]    # عدد مرات عدم ظهور شاشة المسيرة المتتالية (غالباً الطوابير ممتلئة)
POS = {}          # آخر نقطة نجحت لكل مستوى (يُبدأ منها في التشغيل التالي)


def snap(name):
    try: open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "debug_%s.png" % name), "wb").write(screencap())
    except Exception: pass


def dbg(name):
    if DEBUG[0]: snap("gather_step_" + name)


def avg(f, box, st=8):
    n = r = g = b = 0
    for x in range(box[0], box[2], st):
        for y in range(box[1], box[3], st):
            p = f.px(x, y); r += p[0]; g += p[1]; b += p[2]; n += 1
    return r // n, g // n, b // n


# ---------- حالات الشاشة ----------
def is_map(f): r, g, b = avg(f, (1140, 720, 1255, 775)); return b > r + 12            # زر القلعة الرمادي المزرق
def is_city(f): r, g, b = avg(f, (1140, 720, 1255, 775)); return r > b + 30           # زر لفافة الخريطة البني
def chart_open(f): r, g, b = avg(f, (600, 340, 680, 380)); return has_x(f) and g > r + 25 and g > 110
def overview_open(f): r, g, b = avg(f, (600, 340, 680, 380)); return has_x(f) and r > g + 10 and r > 150
def dialog_open(f): return f.count((440, 415, 840, 460), TEAL, 3) > 1200
def march_open(f): return has_x(f) and f.count((131, 570, 357, 700), ORANGE) > 2500
def low_icon(f): return f.count((245, 478, 292, 514), NONBLUE) > 150                  # الأيقونة تظهر قبل التحديد فقط


def moved(a, b):
    n = d = 0
    for x in range(140, 1180, 60):
        for y in range(150, 640, 50):
            p, q = a.px(x, y), b.px(x, y); n += 1
            if abs(p[0] - q[0]) + abs(p[1] - q[1]) + abs(p[2] - q[2]) > 90: d += 1
    return d * 100 >= n * 35


# ---------- قراءة شارات المستوى ----------
def find_badges(f, region=(120, 128, 1215, 692)):
    C = 6; cells = {}; x0, y0, x1, y1 = region
    for y in range(y0, y1, 2):
        for x in range(x0, x1, 2):
            if FACE(*f.px(x, y)):
                k = (x // C, y // C); cells[k] = cells.get(k, 0) + 1
    cells = {k: v for k, v in cells.items() if v >= 2}
    seen = set(); out = []
    for k in list(cells):
        if k in seen: continue
        st = [k]; seen.add(k); pts = []
        while st:
            a = st.pop(); pts.append(a)
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    n = (a[0] + dx, a[1] + dy)
                    if n in cells and n not in seen: seen.add(n); st.append(n)
        xs = [p[0] * C for p in pts]; ys = [p[1] * C for p in pts]
        bx0, bx1, by0, by1 = min(xs), max(xs) + C, min(ys), max(ys) + C
        w, h = bx1 - bx0, by1 - by0; cnt = sum(cells[p] for p in pts)
        if 24 <= w <= 50 and 18 <= h <= 36 and cnt >= 45:
            cx, cy = (bx0 + bx1) // 2, (by0 + by1) // 2
            if any(a <= cx <= c and b <= cy <= d for a, b, c, d in EXCL): continue
            out.append((bx0, by0, bx1, by1))
    return out


def grid(f, b, GW=6, GH=10):
    cx, cy = (b[0] + b[2]) // 2, (b[1] + b[3]) // 2
    left = set((x, y) for y in range(cy - 12, cy + 13) for x in range(cx - 8, cx + 9) if WHITE(*f.px(x, y)))
    pts = []
    while left:                                         # أكبر مكوّن أبيض = الرقم (يتجاهل بقع الخلفية)
        st = [left.pop()]; comp = list(st)
        while st:
            a, c = st.pop()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    n = (a + dx, c + dy)
                    if n in left: left.discard(n); st.append(n); comp.append(n)
        if len(comp) > len(pts): pts = comp
    if len(pts) < 15: return None
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    x0, x1, y0, y1 = min(xs), max(xs) + 1, min(ys), max(ys) + 1; w, h = x1 - x0, y1 - y0
    if h < 10 or h > 24 or w < 5: return None
    S = set(pts); g = []
    for gy in range(GH):
        row = ""
        for gx in range(GW):
            xa, xb = x0 + w * gx / GW, x0 + w * (gx + 1) / GW
            ya, yb = y0 + h * gy / GH, y0 + h * (gy + 1) / GH
            t = n = 0
            for yy in range(int(ya), max(int(yb), int(ya) + 1)):
                for xx in range(int(xa), max(int(xb), int(xa) + 1)):
                    t += 1; n += ((xx, yy) in S)
            row += "#" if n / max(t, 1) >= 0.4 else "."
        g.append(row)
    return g


def level_of(f, b):
    g = grid(f, b)
    if not g: return None
    best = sorted((sum(1 for ra, rb in zip(g, t) for ca, cb in zip(ra, rb) if ca != cb), d) for d, t in T.items())
    return best[0][1] if best[0][0] <= 16 and best[1][0] - best[0][0] >= 2 else None


def icon_sig(f):
    box = (705, 242, 745, 272)
    return {"stone": f.count(box, GRAY), "wood": f.count(box, BROWN), "yel": f.count(box, YEL), "ore": f.count(box, TL)}


def type_ok(sig, want):
    ore = sig["ore"] >= 15                              # بلورات فيروزية = حديد
    if want == "any": return True
    if want == "ore": return ore
    if ore: return False
    if want in ("food", "gold"): return sig["yel"] >= 25 and sig["stone"] < 40
    if want == "wood": return sig["wood"] >= 25 and sig["yel"] < 25 and sig["stone"] < 40
    return sig["stone"] >= 30


# ---------- التنقل ----------
def close_all(f=None, n=4):
    for _ in range(n):
        f = frame()
        if dialog_open(f): tapx(*DIALOG_X, f.s); nap(1.2); continue
        p = guard.popup_x(f) if not has_x(f) else None
        if p: tapx(p[0], p[1], f.s); nap(1.2); continue
        if not has_x(f): break
        tapx(*CLOSE_X, f.s); nap(1.2)


def ensure_map(log):
    close_all()
    f = frame()
    if is_map(f): return True
    if is_city(f):
        tapx(*MAP_BTN, f.s); nap(3.5); f = frame()
        if is_map(f): return True
    snap("gather_map"); log("الجمع: لم أصل إلى الخريطة (حُفظت debug_gather_map.png)"); return False


def open_chart(log):
    for xy in (TELESCOPE_XY, OVERVIEW_XY):
        f = frame(); tapx(xy[0], xy[1], f.s); nap(1.6); f = frame()
        if overview_open(f): tapx(*OV_TOGGLE, f.s); nap(1.3); f = frame()
        if chart_open(f): dbg("chart"); return True
        close_all()
    snap("gather_chart"); log("الجمع: لم يُفتح مخطط الموارد (حُفظت debug_gather_chart.png)"); return False


def chart_points(level):
    if level >= 5: return list(L5_POINTS)
    r = MID[level]
    return [(CC[0] + dx * r, CC[1] + dy * r) for dx, dy in ((0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1))]


def goto(pt, log):
    before = frame()
    for attempt in (1, 2):
        if not chart_open(frame()) and not open_chart(log): return False
        f = frame(); tapx(pt[0], pt[1], f.s); nap(1.3)
        f = frame()
        if has_x(f):
            if attempt == 2: tapx(pt[0], pt[1], f.s); nap(1.3); f = frame()      # نقرة ثانية على المؤشر للتأكيد
            if has_x(f): tapx(*CLOSE_X, f.s); nap(2.5)
        else: nap(2)
        g = frame()
        if is_map(g) and not has_x(g) and (attempt == 2 or moved(before, g)): dbg("arrived"); return True
    return False


# ---------- المورد والمسيرة ----------
def wait_ready(timeout=5):
    """بعد \"الدرجة الأدنى\" يظهر مؤشر تحميل ويصير زر نشر أفتح لوناً؛ ننتظر ذلك."""
    t = time.time(); f = frame()
    while time.time() - t < timeout:
        f = frame()
        if f.px(180, 600)[0] >= 238: return f
        nap(0.6)
    return f


def march(log):
    f = frame(); s = f.s
    if low_icon(f):
        for _ in range(2):
            tapx(*LOW_XY, s); nap(1.5); f = frame()
            if not low_icon(f): break
        if low_icon(f): snap("gather_low"); log("الجمع: لم يُحدَّد الجنود (حُفظت debug_gather_low.png)"); close_all(); return "skip"
    f = wait_ready(); dbg("ready")
    for k in range(3):
        tapx(*DEPLOY_XY, s); nap(2.5); f = frame()
        if not march_open(f): return "ok"
        nap(1.5)
    snap("gather_deploy"); log("الجمع: لم تُرسَل المسيرة (لا طابور حر/جنود؟) (حُفظت debug_gather_deploy.png)"); close_all(); return "full"


def try_node(log, b, want):
    f = None
    for dx, dy in NODE_OFFSETS:
        f = frame(); tapx(b[0] + dx, b[1] + dy, f.s); nap(1.3); f = frame()
        if dialog_open(f): break
        close_all(); f = None
    if f is None: return "skip"
    dbg("dialog"); sig = icon_sig(f)
    if not type_ok(sig, want):
        log("الجمع: مورد من نوع آخر %s فتخطيته" % sig); close_all(); return "skip"
    tapx(*GATHER_XY, f.s); nap(2.2); f = frame()
    dbg("march")
    if not march_open(f):
        NOMARCH[0] += 1; snap("gather_nomarch"); log("الجمع: لم تظهر شاشة المسيرة (حُفظت debug_gather_nomarch.png)"); close_all()
        if NOMARCH[0] >= 2: log("الجمع: فشل متكرر؛ غالباً لا طابور حر، أتوقف الآن"); return "full"
        return "skip"
    NOMARCH[0] = 0
    return march(log)


# اتجاهات سحب الخريطة للبحث عن الموارد (اتجاه الإصبع): حلزون حول نقطة الوصول
SEQ = [(-1, 0), (0, -1), (1, 0), (1, 0), (0, 1), (0, 1), (-1, 0), (-1, 0), (0, -1), (0, -1)]


def drag(d, s):
    hx, hy = 250 * d[0], 150 * d[1]
    swipe(int((640 - hx) * s), int((400 - hy) * s), int((640 + hx) * s), int((400 + hy) * s), 450)
    nap(1.3)


def work_view(log, level, want, left, swipes):
    done = 0; tried = set(); sw = 0; nodes = 0
    while nodes < 12:
        f = frame()
        if has_x(f) or not is_map(f): break
        c = [b for b in find_badges(f) if level_of(f, b) == level and (b[0] // 40, b[1] // 40) not in tried]
        if not c:
            if sw >= swipes: break
            drag(SEQ[sw % len(SEQ)], f.s); sw += 1; tried.clear(); continue     # لا مورد بالمستوى: اسحب الخريطة وابحث
        c.sort(key=lambda b: abs((b[0] + b[2]) / 2 - 640) + abs((b[1] + b[3]) / 2 - 400))
        b = c[0]; tried.add((b[0] // 40, b[1] // 40)); nodes += 1
        r = try_node(log, b, want)
        if r == "ok": done += 1; log("الجمع: أُرسلت مسيرة (مستوى %d)" % level)
        if r == "full" or done >= left: return done, r == "full"
    if sw: log("الجمع: سُحبت الخريطة %d مرة بحثاً عن مورد" % sw)
    return done, False


def run(log, cfg):
    f = frame()
    if f.w < f.h: return log("الشاشة عمودية؛ يلزم الوضع الأفقي")
    DEBUG[0] = bool(cfg.get("gather_debug", True)); want = cfg.get("gather_type", "stone"); level = max(1, min(5, int(cfg.get("gather_level", 4)))); count = max(1, min(8, int(cfg.get("gather_count", 1))))
    if want not in TYPES: return log("الجمع: نوع غير معروف " + str(want))
    NOMARCH[0] = 0
    if not ensure_map(log): return
    pts = chart_points(level); start = POS.get(level, 0) % len(pts); done = 0
    for k in range(len(pts)):
        i = (start + k) % len(pts)
        if not goto(pts[i], log): continue
        n, full = work_view(log, level, want, count - done, max(0, int(cfg.get("gather_swipes", 6))))
        if n: POS[level] = i
        done += n
        if done >= count or full: break
    log("الجمع: أُرسلت %d مسيرة من %d (%s مستوى %d)" % (done, count, TYPES[want], level))
    close_all()
    f = frame()
    if is_map(f): tapx(*MAP_BTN, f.s); nap(3)          # العودة إلى المدينة لباقي المهام
