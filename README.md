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

## الصيد والجمع (hunt / gather)
الخطوات معرّفة في `flows.py` (عدّلها بدون لمس الكود). كل خطوة = زر تلقاه من قالب صورة وتضغط عليه.

### 1) قصّ أزرار الواجهة كقوالب
```
python capture_templates.py --grab shot.png --grid --no-zoom   # لقطة بشبكة إحداثيات
python capture_templates.py --image shot.png --ui search 40 300 70 70
```
يحفظ في `templates/_search/`. الأسماء المطلوبة (راجع `flows.py`):
`search, tab_ore, tab_monster, do_search, gather_btn, attack_btn, march_btn`
واختياريان: `world_map, close`. وللحد: `army_limit` (نافذة "لقد وصلت إلى حد الجيش!") و `army_limit_ok` (زر التأكيد).

### 2) التشغيل
```
python bot.py --task gather            # جمع
python bot.py --task hunt              # صيد
python bot.py --task gather,hunt --loop   # يكرر كل LOOP_PAUSE ثانية
```
- إذا ظهرت نافذة حد الجيش: يؤكد وتتوقف المهمة.
- 3 فشلات متتالية: يرجع (Back) ويوقف المهمة للجولة.
- الحدود في `config.py`: `GATHER_MAX_MARCHES`, `HUNT_MAX_MARCHES`, `STEP_TIMEOUT`, `UI_THRESHOLD`.
- إذا زرّ ما يتلقاش القالب، تنجم تزيد `"fixed": (fx, fy)` في الخطوة كنقطة احتياطية.

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

## ميزات v8
- `python bot.py --check --task gather,hunt [--resource wood]`: يعرض القوالب الناقصة لكل مهمة بدون لمس الهاتف.
- `--resource ore|wood|food|stone|gold`: مورد الجمع (يستعمل قالب `_tab_<المورد>`؛ الافتراضي `RESOURCE` في config).
- في `--loop`: يغلق النوافذ المنبثقة قبل كل جولة، ويعيد تشغيل اللعبة إن خرجت من الواجهة، وبعد `RESTART_AFTER_IDLE_ROUNDS` جولات بلا أي جيش يغلقها بالقوة ويعيد تشغيلها (`AUTO_RELAUNCH` لإيقاف هذا).
- السجل يُحفظ في `runs/bot.log` والإحصائيات التراكمية (عدد الجولات والجيوش لكل مهمة) في `runs/stats.json`.

## الجمع حسب مستوى المنطقة (v9)
```
python bot.py --task gather --resource stone --level 4          # حجر مستوى 4
python bot.py --task gather --resource food --level 3 --loop
python bot.py --check --task gather --resource stone --level 4  # القوالب الناقصة
```
الخطوات: يفتح الكرة الأرضية ثم لفافة القمح (مخطط مناطق الموارد) ← يضغط نقطة من حلقة المستوى N ← يسحب الخريطة بشكل متعرّج (`ZONE_SWIPES` سحبة) حتى يجد عقدة من المورد المطلوب بجانب شارة المستوى المطلوب ← يضغطها ← «جمع» ← «نشر». إن لم يجد يقفز لنقطة أخرى من الحلقة (يسار/أعلى/يمين/أسفل).

القوالب (التقطها من الهاتف بنفس الدقة):
- `_node_stone` / `_node_food` / `_node_wood` / `_node_ore` / `_node_gold`: شكل العقدة فقط بدون الشارة (يمكن عدة صور لكل مورد)
- `_lvl_1` … `_lvl_5`: الشارة الزرقاء الصغيرة بالرقم
- `_gather_btn` (زر «جمع») و`_march_btn` (زر «نشر») و`_army_limit` و`_army_limit_ok`
- اختياري: `_map_close` (X المخطط)، `_world_globe`، `_zone_btn`
مثال القص: `python capture_templates.py --image shot.png --ui lvl_4 810 450 45 40`

## الصيد الذكي (v10)
```
python bot.py --task hunt            # يصيد حتى تنتهي الطاقة
python bot.py --task hunt --loop     # بعد نفاد الطاقة ينتظر ENERGY_RETRY_SEC (30 دقيقة) ثم يعيد
python bot.py --task hunt --level 3  # يقفز أولاً لحلقة المستوى 3 في مخطط المناطق ثم يبحث
```
المنطق: يجد وحشاً على الشاشة ← يضغطه ← «صيد الوحش» ← إن ظهرت نافذة المعدات يضغط «إبقاء المعدات الحالية» (لا «اذهب للتغيير» أبداً) ← «صيد الوحش» في شاشة الأبطال ← ينتظر `HUNT_WAIT` ثانية ← يضرب نفس الوحش مجدداً. إذا اختفت نافذته (مات) يبحث بالسحب عن وحش آخر. عند ظهور نافذة نفاد الطاقة يضغط إلغاء فقط (لا يستعمل أي عنصر من الحقيبة) ويوقف الصيد.

القوالب: `_monster` أو `_monster_2`… (صور الوحوش؛ ضع عدة صور وبمستويات تريدها فقط)، `_hunt_btn` (زر «صيد الوحش» في نافذة الوحش)، `_hunt_go` (زر «صيد الوحش» في شاشة الأبطال)، `_equip_keep` («إبقاء المعدات الحالية»)، `_energy_empty` (نافذة نفاد الطاقة) و`_energy_cancel` (إلغاؤها)، و`_army_limit*`.
`HUNT_MAX_MARCHES = 0` يعني بلا حد؛ والمهمة القديمة (بحث بالعدسة) صارت `hunt_search`.
