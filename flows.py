"""تعريف خطوات الصيد والجمع. عدّل الأسماء/الإحداثيات هنا فقط، بدون لمس باقي الكود.

أنواع الخطوات (dict):
  {"ui": "اسم"}                     يلقى القالب templates/_<اسم>/ على الشاشة ويضغط مركزه
  {"ui": "اسم", "optional": True}   إذا ما ظهرش يعدّي (ما يعتبرهاش فشل)
  {"ui": "اسم", "fixed": (fx, fy)}  إذا ما لقاش القالب يضغط على نقطة ثابتة (نسبة من الشاشة 0..1)
  {"xy": (fx, fy)}                  ضغطة مباشرة على نسبة من الشاشة
  {"swipe": (fx1, fy1, fx2, fy2)}   سحب
  {"back": True}                    زر الرجوع
  {"sleep": 2}                      انتظار
  خيارات مشتركة: "wait" (ثوانٍ بعد الخطوة) ، "timeout" ، "threshold"

القوالب المطلوبة (التقطها بـ: python capture_templates.py --image shot.png --ui NAME X Y W H):
  army_limit      نص/إطار نافذة "لقد وصلت إلى حد الجيش!"
  army_limit_ok   زر التأكيد في تلك النافذة
"""

# الحارس: يتفحص بعد كل خطوة. إذا ظهرت نافذة حد الجيش يؤكد ويوقف المهمة.
ARMY_LIMIT = {"detect": "army_limit", "confirm": "army_limit_ok"}

# حارس الطاقة: نافذة نفاد الطاقة (التي تعرض استعمال عنصر من الحقيبة). نضغط إلغاء/رجوع فقط، لا نستعمل أي عنصر أبداً.
ENERGY_EMPTY = {"detect": "energy_empty", "cancel": "energy_cancel"}

# ---------- الجمع ----------
GATHER = [
    {"ui": "world_map", "optional": True, "wait": 1.5},   # زر الخروج للخريطة (إذا كان في المدينة)
    {"ui": "search", "wait": 1.0},                         # أيقونة البحث (العدسة)
    {"ui": "tab_ore", "wait": 0.8},                        # تبويب المورد (حجر/خشب/...) - بدّل الاسم حسب المورد
    {"ui": "do_search", "wait": 2.5},                      # زر "بحث" يوديك للمنجم
    {"ui": "gather_btn", "wait": 1.5},                     # زر "جمع" على المنجم
    {"ui": "march_btn", "wait": 1.5},                      # زر "مسيرة/إرسال" في شاشة اختيار القوات
    {"ui": "close", "optional": True, "wait": 0.5},
]

# ---------- الصيد ----------
HUNT = [
    {"ui": "world_map", "optional": True, "wait": 1.5},
    {"ui": "search", "wait": 1.0},
    {"ui": "tab_monster", "wait": 0.8},
    {"ui": "do_search", "wait": 2.5},
    {"ui": "attack_btn", "wait": 1.5},                     # زر "هجوم" على الوحش
    {"ui": "march_btn", "wait": 1.5},
    {"ui": "close", "optional": True, "wait": 0.5},
]

# ---------- الجمع حسب مستوى المنطقة (--level N) ----------
# فتح مخطط مناطق الموارد: أيقونة الكرة الأرضية ثم زر لفافة القمح (إحداثيات احتياطية بنسبة من الشاشة)
ZONE_OPEN = [
    {"ui": "world_globe", "fixed": (0.973, 0.619), "wait": 1.5},
    {"ui": "zone_btn", "fixed": (0.853, 0.900), "wait": 1.5},
]
# مركز المخطط ونصف قطر منتصف حلقة كل مستوى (بكسل على لقطة 1280x800)
ZONE_CENTER = (640, 400)
ZONE_RADIUS = {1: 339, 2: 267, 3: 190, 4: 113, 5: 0}
# قوالب هذه المهمة: _node_<المورد> (شكل العقدة) و _lvl_<N> (شارة المستوى الزرقاء) و gather_btn و march_btn
# اختياري: _map_close (زر X لإغلاق المخطط) و _world_globe و _zone_btn


def zone_points(level, w=1280, h=800):
    """نقاط على حلقة المستوى (يسار، أعلى، يمين، أسفل) كنسب من الشاشة. المستوى 5 = المركز."""
    cx, cy = ZONE_CENTER
    r = ZONE_RADIUS[level]
    if r == 0:
        return [(cx / w, (cy - 40) / h)]
    return [((cx - r) / w, cy / h), (cx / w, (cy - r) / h),
            ((cx + r) / w, cy / h), (cx / w, (cy + r) / h)]


# اتجاهات السحب المتعرّج للبحث داخل المنطقة
SCAN_DIRS = [(-1, 0), (-1, 0), (0, -1), (1, 0), (1, 0), (0, -1)]


RESOURCES = ("ore", "wood", "food", "stone", "gold")


def get_flow(task, resource=None):
    """خطوات المهمة. للجمع: يبدّل تبويب المورد إلى tab_<resource> (القالب templates/_tab_<resource>/)."""
    flow = TASKS[task]["flow"]
    if task != "gather" or not resource or resource == "ore":
        return flow
    return [dict(st, ui=f"tab_{resource}") if st.get("ui") == "tab_ore" else st for st in flow]


TASKS = {
    "gather": {"flow": GATHER, "max_key": "GATHER_MAX_MARCHES"},
    "hunt": {"flow": None, "max_key": "HUNT_MAX_MARCHES"},            # الصيد الذكي (في tasks.py)
    "hunt_search": {"flow": HUNT, "max_key": "HUNT_SEARCH_MAX_MARCHES"},   # القديم: بحث بالعدسة
}
