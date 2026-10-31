# بوت لوردس موبايل

عند كل دخول جديد: يغلق النوافذ المنبثقة ← يصغّر القلعة لأقصى حد ← يحدد كل مبنى موجود ويحفظ إحداثياته.

## التشغيل على Termux (على الهاتف نفسه)

```
git clone https://github.com/<حسابك>/lords-bot.git
cd lords-bot
bash install_termux.sh
```

### ربط adb بالهاتف نفسه (مرة واحدة، أندرويد 11+)
1. الإعدادات ← خيارات المطور ← **التصحيح اللاسلكي** ← فعّله.
2. اضغط «اقتران بالجهاز برمز الاقتران» (يظهر منفذ ورمز). افتح Termux في نافذة عائمة/منقسمة وشغّل:
   ```
   adb pair localhost:<منفذ_الاقتران>      # ثم اكتب الرمز
   adb connect localhost:<منفذ_الاتصال>    # المنفذ الظاهر في شاشة التصحيح اللاسلكي
   adb devices
   export LORDS_SERIAL=localhost:<منفذ_الاتصال>
   ```
3. القرص يتم عبر `sendevent` مباشرة، فلا حاجة لـ uiautomator2.

التصحيح اللاسلكي يتطلب اتصال Wi‑Fi، وقد يتغير منفذ الاتصال بعد إعادة التشغيل أو تغيير الشبكة.

### التشغيل
```
termux-wake-lock
python bot.py --watch      # تلقائي عند كل دخول جديد للعبة
python bot.py              # مرة واحدة
```

### القوالب (مهم)
`cv2.selectROI` يحتاج واجهة رسومية وغير متاح في Termux، لذا:
- **الأسهل:** أنشئ القوالب على الحاسوب بـ `python capture_templates.py`، ثم `git add templates && git commit && git push`، وفي Termux نفّذ `git pull`.
- **من الهاتف فقط:**
  ```
  python capture_templates.py --grab shot.png --grid   # يحفظ shot_grid.png عليها شبكة إحداثيات
  python capture_templates.py --image shot.png --crop barracks 420 310 90 80
  ```
  افتح `shot_grid.png` من المعرض، اقرأ إحداثيات كل مبنى، ثم قصّه بـ `--crop NAME X Y W H`.

## التشغيل على الحاسوب
```
pip install -r requirements.txt
```
ثبّت `adb` وفعّل USB debugging (أو شغّل المحاكي) وتأكد من `adb devices`. إن لم يعمل `sendevent` على جهازك اضبط `PINCH_BACKEND = "u2"` وثبّت `uiautomator2` ونفّذ `python -m uiautomator2 init`.

## الخطوات العامة
1. التقط قوالب المباني (انظر أعلاه). كرر لنفس المبنى بمستويات/أشكال مختلفة.
2. (اختياري) قوالب أزرار الإغلاق: `templates/_ui/close_1.png` ...
3. شغّل `python bot.py` أو `--watch`.

## المخرجات (مجلد `runs/`، غير مرفوع إلى Git)
- `latest.json`: المباني الموجودة (الاسم، المستطيل، المركز cx/cy، الدرجة) + `missing` للمباني غير الظاهرة.
- `<وقت>.png`: لقطة مرسوم عليها المباني المكتشفة للتحقق البصري.

## ضبط الدقة (`config.py`)
- لا يكتشف شيئاً ← قلّل `MATCH_THRESHOLD` (مثلاً 0.75).
- كشف خاطئ ← ارفعه أو أضف قوالب أدق.
- التصغير يتوقف مبكراً/متأخراً ← عدّل `ZOOM_DIFF_THRESHOLD`.
- القرص ضعيف ← زد `PINCH_PERCENT` (حتى 100) أو `MAX_ZOOM_ITER`.
- مناطق HUD تُهمل عبر `IGNORE_REGIONS`.

## ملاحظات
- القوالب مرتبطة بدقة الشاشة؛ التقطها من نفس الجهاز.
- لا ترفع إلى GitHub أي رموز أو مفاتيح؛ `.gitignore` يستثني `runs/` و`.env`.
