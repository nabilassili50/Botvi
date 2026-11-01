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

RESOURCES = ("ore", "wood", "food", "stone", "gold")


def get_flow(task, resource=None):
    """خطوات المهمة. للجمع: يبدّل تبويب المورد إلى tab_<resource> (القالب templates/_tab_<resource>/)."""
    flow = TASKS[task]["flow"]
    if task != "gather" or not resource or resource == "ore":
        return flow
    return [dict(st, ui=f"tab_{resource}") if st.get("ui") == "tab_ore" else st for st in flow]


TASKS = {
    "gather": {"flow": GATHER, "max_key": "GATHER_MAX_MARCHES"},
    "hunt": {"flow": HUNT, "max_key": "HUNT_MAX_MARCHES"},
}
