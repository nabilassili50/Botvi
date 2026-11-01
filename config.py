"""إعدادات البوت - عدّل القيم هنا فقط."""

# ---- الجهاز ----
import os

# None = الجهاز الوحيد المتصل. على Termux: "localhost:PORT" (منفذ التصحيح اللاسلكي). يمكن ضبطه بالمتغير LORDS_SERIAL
SERIAL = os.environ.get("LORDS_SERIAL") or None
PACKAGE = "com.igg.android.lordsmobile"

# "adb"  : PC, or Termux with a paired adb
# "rish" : Termux + Shizuku (no pairing dialog needed, phone only)
BACKEND = os.environ.get("LORDS_BACKEND", "adb")

# ---- الانتظار (ثوانٍ) ----
LOAD_WAIT = 25                     # انتظار تحميل اللعبة بعد كل دخول
WATCH_POLL = 2                     # فترة فحص هل اللعبة في الواجهة (وضع المراقبة)

# ---- التصغير ----
PINCH_BACKEND = "auto"             # "auto" | "sendevent" (Termux/بدون وكيل) | "u2" (uiautomator2)
MAX_ZOOM_ITER = 12                 # أقصى عدد محاولات قرص
PINCH_PERCENT = 80                 # نسبة طول القرص من الشاشة
PINCH_STEPS = 40                   # خطوات الإيماءة (أكبر = أبطأ وأنعم)
ZOOM_SETTLE = 1.2                  # انتظار بعد كل قرص قبل اللقطة
ZOOM_DIFF_THRESHOLD = 2.5          # فرق متوسط بين لقطتين (0-255) تحته يعتبر مستقراً
ZOOM_STABLE_COUNT = 2              # عدد المرات المتتالية المطلوبة للاستقرار

# ---- كشف المباني ----
TEMPLATES_DIR = "templates"        # templates/<اسم_المبنى>/*.png ؛ المجلدات التي تبدأ بـ _ هي عناصر واجهة
MATCH_THRESHOLD = 0.82             # حد التطابق (0-1)
SCALES = [0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.35]   # مقاييس متعددة للقالب
NMS_IOU = 0.3                      # دمج الكشوفات المتداخلة

# ---- تثبيت منظر القلعة (إزالة الإزاحة) ----
# بعد التصغير الأقصى يدفع الخريطة نحو زاوية حتى تتوقف عن التحرك، فيصير المنظر نفسه في كل دخول
# (فتصلح النقاط المحفوظة positions.json والقوالب بنفس الأماكن).
CASTLE_ALIGN = True
CASTLE_ALIGN_DIR = (-1, -1)        # اتجاه سحب الإصبع: (-1,-1)=لأعلى-يسار ؛ (1,1)=لأسفل-يمين ؛ (-1,1)=لأعلى... عدّله إن لم تستقر
ALIGN_MAX_SWIPES = 6
ALIGN_SWIPE_FRAC = 0.5             # طول السحبة كنسبة من الشاشة
# مستطيل القلعة (x1,y1,x2,y2 كنسب من الشاشة): الكشف يبحث داخله فقط. مثال: python bot.py --set CASTLE_BOX=[0.05,0.12,0.95,0.85]
CASTLE_BOX = (0.0, 0.10, 1.0, 0.88)
CASTLE_ZOOM_FIRST = True           # قبل مهام القلعة: يصغّر ويثبّت المنظر

# مناطق تُهمل (كسور من الشاشة: x1, y1, x2, y2) - أزرار الواجهة والشريط العلوي/السفلي
IGNORE_REGIONS = [
    (0.0, 0.0, 1.0, 0.10),
    (0.0, 0.88, 1.0, 1.0),
]

# ---- تنظيف الشاشة (الزحمة) عند الدخول ----
# أي قالب واجهة يبدأ اسمه بأحد هذه البادئات (templates/_close*, _popup*, _skip*, _banner*) يُضغط حتى تنظف الشاشة
CLEAN_PREFIXES = ("close", "popup", "skip", "banner")
CLEAN_ROUNDS = 8                   # أقصى عدد ضغطات تنظيف
# مناطق تُهمل في كشف المباني لأن فيها أيقونات عائمة/لافتات (x1,y1,x2,y2 كنسب). مثال: --set CLUTTER_REGIONS=[[0,0.1,0.12,0.5]]
CLUTTER_REGIONS = []

# ---- إغلاق النوافذ المنبثقة عند الدخول ----
# ضع صور أزرار الإغلاق في templates/_close/*.png
CLOSE_POPUP_ATTEMPTS = 5
CLOSE_POPUP_THRESHOLD = 0.85

# ---- المخرجات ----
OUTPUT_DIR = "runs"

# ---- المهام (الصيد والجمع) ----
# كل مهمة = سلسلة خطوات تعرّفها في flows.py. القوالب في templates/_<اسم>/
STEP_TIMEOUT = 8                   # أقصى انتظار لظهور زر (ثوانٍ) قبل اعتبار الخطوة فاشلة
STEP_POLL = 0.8                    # فترة إعادة اللقطة أثناء الانتظار
UI_THRESHOLD = 0.85                # حد تطابق أزرار الواجهة
GATHER_MAX_MARCHES = 7             # أقصى عدد جيوش للجمع
HUNT_MAX_MARCHES = 0               # 0 = يواصل الصيد حتى تنتهي الطاقة؛ أو ضع رقماً كحد أقصى للهجمات
HUNT_SEARCH_MAX_MARCHES = 7        # للمهمة القديمة hunt_search (البحث بالعدسة)
LOOP_PAUSE = 60                    # ثوانٍ بين الجولات في وضع --loop
MAX_FAILS = 3                      # عدد الفشل المتتالي قبل إيقاف المهمة وإعادة المحاولة بالجولة الجاية

# ---- الاستمرارية (وضع --loop) ----
AUTO_RELAUNCH = True               # إذا خرجت اللعبة من الواجهة/انهارت: يعيد تشغيلها (فقط بدون --no-launch)
RESTART_AFTER_IDLE_ROUNDS = 3      # بعد هذا العدد من الجولات بدون أي جيش: إغلاق اللعبة بالقوة وإعادة تشغيلها
RESOURCE = "ore"                   # مورد الجمع الافتراضي: ore | wood | food | stone | gold (يُبدَّل بـ --resource)

# ---- الجمع حسب مستوى المنطقة (--level) ----
ZONE_SWIPES = 10                   # أقصى عدد سحبات للبحث عن عقدة مطابقة قبل القفز لنقطة أخرى من المنطقة
SWIPE_FRAC = 0.40                  # طول السحبة كنسبة من الشاشة
SWIPE_MS = 500
ZONE_SETTLE = 2.0                  # انتظار بعد الضغط على المنطقة في المخطط
NODE_THRESHOLD = 0.72              # حد تطابق قوالب العقد وشارات المستوى
NODE_BADGE_DIST = 170              # أقصى مسافة (بكسل) بين العقدة وشارة مستواها

# ---- الصيد الذكي (hunt) ----
HUNT_WAIT = 20                     # ثوانٍ بعد كل هجمة قبل ضرب نفس الوحش مرة أخرى (مدة المسير والمعركة)
ENERGY_RETRY_SEC = 1800            # عند نفاد الطاقة: لا يعيد المحاولة قبل هذه المدة (لا يستعمل أي عنصر من الحقيبة)
MONSTER_NEAR_PX = 220              # أقصى إزاحة (بكسل) لاعتبار الوحش هو نفسه بعد تحرّك الخريطة قليلاً
HUNT_RETRIES = 3                   # محاولات إعادة فتح نفس الوحش قبل اعتباره مات
HUNT_RETRY_WAIT = 8                # ثوانٍ بين المحاولات (قد يكون الجيش ما زال يقاتله)

# ---- المهام المسجّلة (--record) ----
NEAR_FRAC = 0.12                   # القالب المسجّل يُقبل فقط ضمن هذه المسافة (نسبة من عرض الشاشة) من مكان ضغطتك الأصلية

# ---- ميدان الأبطال (arena) ----
ARENA_MAX_BATTLES = 5              # أقصى عدد تحديات في الجولة (الحد اليومي 5)
ARENA_ROW = "bottom"               # أي خصم يتحدى: "bottom" (الأسفل = الأضعف غالباً) | "top" | "middle"
ARENA_BATTLE_WAIT = 30             # أقصى انتظار (ثوانٍ) لانتهاء المعركة والعودة لشاشة الميدان
ARENA_REWARD_OFFSET = (30, 40)     # إزاحة الضغط (بكسل) من شارة «!» إلى أيقونة مكافأة الترتيب

# ---- مهام القلعة ----
CASTLE_MAX = 1                     # (غير مستعمل فعلياً؛ مهام القلعة تُنفَّذ مرة كل CASTLE_EVERY_SEC)
CASTLE_EVERY_SEC = 1800            # في وضع --loop: يعيد مهام القلعة كل هذه المدة (30 دقيقة)

# ---- تحكم بدون تعديل الكود ----
DEBUG = os.environ.get("LORDS_DEBUG") == "1"   # يحفظ صوراً عليها ما يراه البوت في runs/debug


def _load_overrides():
    """settings.json بجانب البوت يغيّر أي قيمة هنا: python bot.py --set ZONE_SWIPES=6"""
    import json
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return
    for k, v in data.items():
        if k in globals() and not k.startswith("_"):
            globals()[k] = v


_load_overrides()
