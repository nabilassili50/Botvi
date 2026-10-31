# بوت لوردس موبايل

عند كل دخول جديد: يغلق النوافذ المنبثقة ← يصغّر القلعة لأقصى حد ← يحدد كل مبنى موجود ويحفظ إحداثياته.

## التشغيل على Termux (على الهاتف وحده، عبر Shizuku)

هذه الطريقة لا تحتاج حاسوباً ولا نافذة اقتران ولا شاشة منقسمة.

### 1) تثبيت المتطلبات
```
bash install_termux.sh
```

### 2) تثبيت Shizuku وتشغيله
1. ثبّت تطبيق **Shizuku** (من Google Play أو من GitHub: RikkaApps/Shizuku).
2. افتحه واختر **Start via Wireless debugging** (البدء عبر التصحيح اللاسلكي).
3. اضغط **Pairing**. ستفتح لك إعدادات المطور وسيظهر **إشعار** فيه خانة لكتابة رمز الاقتران.
   - من الإعدادات اضغط «اقتران الجهاز برمز الاقتران» ثم اسحب شريط الإشعارات واكتب الرمز المكوّن من 6 أرقام داخل إشعار Shizuku.
   - لا تحتاج أن تغادر شاشة الإعدادات، هنا الفرق عن adb.
4. ارجع إلى Shizuku واضغط **Start**. يجب أن يظهر «Shizuku is running».

### 3) ربط Termux بـ Shizuku (rish)
1. في Shizuku: **Use Shizuku in terminal apps** ← **Export files** ← اختر مجلد Downloads.
2. في Termux:
   ```
   bash setup_rish.sh
   ```
3. افتح جلسة Termux جديدة ثم جرّب:
   ```
   rish -c "id"
   ```
   يجب أن يطبع `uid=2000(shell)`. وقد يظهر طلب إذن لـ Termux داخل Shizuku، اقبله.

بعد إعادة تشغيل الهاتف تحتاج تشغيل Shizuku مرة أخرى (الخطوة 2.4).

### 4) التشغيل
```
termux-wake-lock
python bot.py --watch      # تلقائي عند كل دخول جديد للعبة
python bot.py              # مرة واحدة
```

### القوالب (مهم)
`cv2.selectROI` يحتاج واجهة رسومية وغير متاح في Termux، لذا:
- **الأسهل:** أنشئ القوالب على حاسوب بـ `python capture_templates.py`، ثم ارفعها إلى GitHub واسحبها في Termux.
- **من الهاتف فقط:**
  ```
  python capture_templates.py --grab shot.png --grid   # يحفظ shot_grid.png عليها شبكة إحداثيات
  python capture_templates.py --image shot.png --crop barracks 420 310 90 80
  ```
  افتح `shot_grid.png` من المعرض، اقرأ إحداثيات كل مبنى، ثم قصّه بـ `--crop NAME X Y W H`.

## التشغيل على الحاسوب (adb)
```
pip install -r requirements.txt
export LORDS_BACKEND=adb
python bot.py
```
ثبّت `adb` وفعّل USB debugging وتأكد من `adb devices`.

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
- عبر rish كل أمر يستغرق نحو ثانية، لذا التصغير أبطأ قليلاً من adb.
- لا ترفع إلى GitHub أي رموز أو مفاتيح؛ `.gitignore` يستثني `runs/` و`.env`.
