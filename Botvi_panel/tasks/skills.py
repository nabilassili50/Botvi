"""مهارات الوحوش المساعدة (شاشة \"مهارات مساعدة\"): يضغط كل زر \"استخدام\" الفعّال (اللون الأزرق) ويتجاوز الأزرار الداكنة (قيد التبريد)، ويمرّر القائمة حتى نهايتها.
لا يشتري شيئاً؛ وأي نافذة غير متوقعة يغلقها بزر X الخاص بها. طريقة الوصول للشاشة من المدينة تُضبط بالمفتاح skills_entry في settings.json
(قائمة نقرات [[x,y],...] بمقياس 1280x800 تُنفَّذ بالترتيب)؛ وإن كانت الشاشة مفتوحة أصلاً لا حاجة لها."""
import os, time
from shizuku import frame, tapx, screencap, swipe, nap
from tasks.saga import has_x, CLOSE_X
from tasks.guard import popup_x

TITLE = lambda r, g, b: r < 45 and 120 < g < 160 and 160 < b < 200
USE = lambda r, g, b: 40 <= r <= 58 and 108 <= g <= 130 and 125 <= b <= 158     # زر \"استخدام\" الفعّال؛ الداكن (r~24) والخلفية (r~67) لا يطابقانه
BTN_X = 325

def skills(f): return has_x(f) and f.count((500, 80, 860, 120), TITLE) > 1500
def usable(f):
    """مراكز y للأزرار الفعّالة (حزمة x=385..425 خالية من النص)، بطول لا يقل عن 40 بكسل."""
    out = []; cur = None
    for y in range(205, 790, 2):
        n = sum(1 for x in range(385, 425, 4) if USE(*f.px(x, y)))
        if n >= 8: cur = cur or [y, y]; cur[1] = y
        elif cur:
            if cur[1] - cur[0] >= 40: out.append((cur[0] + cur[1]) // 2)
            cur = None
    if cur and cur[1] - cur[0] >= 40: out.append((cur[0] + cur[1]) // 2)
    return out
def sig(f): return [f.px(1085, y) for y in range(215, 780, 7)]     # عمود الأيقونات يتغير عند التمرير ولا يتأثر بالعدادات
def same(a, b): return sum(1 for p, q in zip(a, b) if sum(abs(i - j) for i, j in zip(p, q)) > 60) < len(a) * 0.12

def snap(name):
    try: open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "debug_%s.png" % name), "wb").write(screencap())
    except Exception: pass

def close_all(n=4):
    for _ in range(n):
        f = frame()
        if not has_x(f): return
        tapx(*CLOSE_X, f.s); nap(1.2)

def scroll(s, up):
    a, b = (700, 700), (700, 330)
    if not up: a, b = b, a
    swipe(int(a[0] * s), int(a[1] * s), int(b[0] * s), int(b[1] * s), 500); nap(1.2)

def run(log, cfg):
    f = frame()
    if f.w < f.h: return log("الشاشة عمودية؛ يلزم الوضع الأفقي")
    s = f.s
    if not skills(f):
        close_all(); entry = cfg.get("skills_entry") or []
        if not entry: snap("skills_open"); return log("المهارات: لم أجد طريق فتح الشاشة؛ اضبط skills_entry في settings.json (حُفظت debug_skills_open.png)")
        for x, y in entry: tapx(x, y, s); nap(1.5)
        nap(1); f = frame()
        if not skills(f): snap("skills_open"); close_all(); return log("المهارات: لم تُفتح شاشة مهارات مساعدة (حُفظت debug_skills_open.png)")
    for _ in range(8):                                  # إلى أعلى القائمة
        a = sig(frame()); scroll(s, False)
        if same(a, sig(frame())): break
    used = 0
    for _ in range(14):
        miss = set()
        for _ in range(12):
            f = frame()
            if not skills(f):
                p = popup_x(f)
                if p: tapx(p[0], p[1], s); nap(1.5); continue
                snap("skills_unknown"); log("المهارات: شاشة غير متوقعة (حُفظت debug_skills_unknown.png)"); return close_all()
            todo = [y for y in usable(f) if all(abs(y - m) > 20 for m in miss) and y < 775]
            if not todo: break
            y = todo[0]; tapx(BTN_X, y, s); nap(3)
            f2 = frame()
            if skills(f2) and any(abs(y - z) < 20 for z in usable(f2)): miss.add(y)
            else: used += 1
        a = sig(frame()); scroll(s, True)
        if same(a, sig(frame())): break
    log("المهارات: فُعّلت %d مهارة" % used)
    close_all()
