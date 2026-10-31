"""إعدادات البوت - عدّل القيم هنا فقط."""

# ---- الجهاز ----
import os

# None = الجهاز الوحيد المتصل. على Termux: "localhost:PORT" (منفذ التصحيح اللاسلكي). يمكن ضبطه بالمتغير LORDS_SERIAL
SERIAL = os.environ.get("LORDS_SERIAL") or None
PACKAGE = "com.igg.android.lordsmobile"

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
# ضع صور أزرار الإغلاق في templates/_ui/close_*.png
CLOSE_POPUP_ATTEMPTS = 5
CLOSE_POPUP_THRESHOLD = 0.85

# ---- المخرجات ----
OUTPUT_DIR = "runs"
