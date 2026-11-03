"""الحارس: يغلق الإعلانات والنوافذ المنبثقة ويعيد اللعبة إلى المدينة قبل كل مهمة وبينها.
1) إن خرجت اللعبة من الواجهة (إعلان خارجي/متصفح/إشعارات) يرجع إليها أو يعيد فتحها.
2) إن ظهرت شاشة غير معروفة (نافذة عرض/إعلان داخل اللعبة) يضغط زر الرجوع حتى تظهر المدينة أو شاشة لعبة معروفة."""
import os, time
import shizuku
from shizuku import frame, back, focus, launch, screencap, tapx
from tasks.saga import has_x

PKG = "com.igg.android.lordsmobile"
NEED_ZOOM = [True]      # يُرفع عند فتح اللعبة من جديد ليُصغَّر الزوم قبل المهمة التالية
BLUE = lambda r, g, b: r < 80 and 90 < g < 150 and 130 < b < 200

def city(f):
    """شريط الأيقونات السفلي ثابت اللون في المدينة، وزر \"انتقال\" الأزرق، ولا يوجد زر الإغلاق في الزاوية."""
    if has_x(f): return False
    n = 0; r = g = b = 0
    for x in range(330, 600, 6):
        for y in range(745, 790, 6):
            p = f.px(x, y); r += p[0]; g += p[1]; b += p[2]; n += 1
    bar = abs(r // n - 119) < 14 and abs(g // n - 105) < 14 and abs(b // n - 89) < 14
    return bar or f.count((690, 648, 790, 684), BLUE) > 60

def popup_x(f):
    """زر الإغلاق البرتقالي داخل معين أحمر (يظهر في زاوية النوافذ المنبثقة، غير زر الزاوية العليا اليسرى)."""
    for y in range(40, 500, 3):
        for x in range(110, 1270, 3):
            if x < 130 and y < 120: continue
            r, g, b = f.px(x, y)
            if r > 245 and 175 < g < 205 and 50 < b < 85:
                ok = 0
                for dx, dy in ((0, -24), (0, 24), (-24, 0), (24, 0)):
                    xx, yy = x + dx, y + dy
                    if 0 <= xx < 1280 and 0 <= yy < 800:
                        a, c, d = f.px(xx, yy)
                        if a > 110 and c < 95 and d < 110 and a > c + 50: ok += 1
                if ok >= 4: return (x, y)
    return None

def snap(name):
    try: open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "debug_%s.png" % name), "wb").write(screencap())
    except Exception: pass

def in_game(pkg):
    out = focus()
    return (not out.strip()) or pkg in out          # إن تعذّرت القراءة نفترض أننا داخل اللعبة

PANEL = lambda r, g, b: r < 60 and 60 < g < 95 and 80 < b < 115      # لوحة نافذة "اتصال مقطوع" الزرقاء الداكنة
RETRY_XY = (640, 372)                                                 # زر "إعادة المحاولة"

def conn_lost(f):
    """نافذة "اتصال مقطوع... لا يوجد استجابة من الخادم": لوحة زرقاء داكنة تغطي معظم منطقتها الوسطى."""
    return f.count((420, 190, 860, 320), PANEL, 2) > 6000

def clear(log, cfg, tries=7):
    if not cfg.get("guard", True): return True
    pkg = cfg.get("game_pkg") or PKG
    n = conn = 0; quiet = 0.0
    while n < tries:
        n += 1
        if not in_game(pkg):
            log("الحارس: خرجنا من اللعبة، أعود إليها")
            launch(pkg); NEED_ZOOM[0] = True; t = time.time()
            while time.time() - t < (150 if shizuku.VD["on"] else 45):      # انتظر انتهاء التحميل دون ضغط رجوع
                time.sleep(3)
                if in_game(pkg):
                    f = frame()
                    if city(f) or has_x(f): break
            continue
        f = frame()
        if f.w < f.h: return True
        if conn_lost(f):                                      # انقطاع الاتصال: أعد المحاولة ولا تضغط رجوع أبداً (يُخرج من اللعبة)
            n -= 1; conn += 1
            if conn > 40: log("الحارس: ما زال الاتصال مقطوعاً بعد 40 محاولة؛ سأعيد المحاولة لاحقاً"); return False
            log("الحارس: انقطع الاتصال بالخادم، أضغط إعادة المحاولة (%d)" % conn)
            tapx(RETRY_XY[0], RETRY_XY[1], f.s); NEED_ZOOM[0] = True; quiet = time.time() + 75; time.sleep(6); continue
        if time.time() < quiet and not (city(f) or has_x(f)):   # بعد إعادة المحاولة: شاشة تحميل، انتظر بلا ضغط
            n -= 1; time.sleep(3); continue
        p = popup_x(f)
        if p:
            tapx(p[0], p[1], f.s); time.sleep(1.4); log("الحارس: أُغلقت نافذة منبثقة"); continue
        if city(f) or has_x(f): return True
        back(); time.sleep(1.6)
        f = frame()
        if city(f) or has_x(f): log("الحارس: أُغلقت نافذة/إعلان"); return True
    snap("guard_unknown"); log("الحارس: لم أستطع إغلاق الشاشة (حُفظت debug_guard_unknown.png)")
    return False
