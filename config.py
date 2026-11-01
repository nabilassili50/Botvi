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

# مناطق تُهمل (كسور من الشاشة: x1, y1, x2, y2) - أزرار الواجهة والشريط العلوي/السفلي
IGNORE_REGIONS = [
    (0.0, 0.0, 1.0, 0.10),
    (0.0, 0.88, 1.0, 1.0),
]

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
NODE_THRESHOLD = 0.80              # حد تطابق قوالب العقد وشارات المستوى
NODE_BADGE_DIST = 170              # أقصى مسافة (بكسل) بين العقدة وشارة مستواها

# ---- الصيد الذكي (hunt) ----
HUNT_WAIT = 20                     # ثوانٍ بعد كل هجمة قبل ضرب نفس الوحش مرة أخرى (مدة المسير والمعركة)
ENERGY_RETRY_SEC = 1800            # عند نفاد الطاقة: لا يعيد المحاولة قبل هذه المدة (لا يستعمل أي عنصر من الحقيبة)
MONSTER_NEAR_PX = 220              # أقصى إزاحة (بكسل) لاعتبار الوحش هو نفسه بعد تحرّك الخريطة قليلاً
