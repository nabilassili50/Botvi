#!/data/data/com.termux/files/usr/bin/bash
# تشغيل/إيقاف البوت بأمر واحد (Termux + Shizuku).
#   bash bot.sh hunt              صيد حتى تنتهي الطاقة (تكرار تلقائي)
#   bash bot.sh hunt 3            صيد بعد القفز لحلقة المستوى 3
#   bash bot.sh gather stone 4    جمع حجر من منطقة المستوى 4 (المورد: stone|food|wood|ore|gold)
#   bash bot.sh gather            جمع بالبحث القديم (المورد الافتراضي)
#   bash bot.sh all [مورد مستوى]  القلعة أولاً ثم الصيد ثم الجمع (مثال: bash bot.sh all stone 4)
#   bash bot.sh set KEY=VALUE     تغيير إعداد (مثال: bash bot.sh set ZONE_SWIPES=6 HUNT_WAIT=30)
#   bash bot.sh debug on|off      حفظ صور بما يراه البوت في runs/debug
#   bash bot.sh panel             لوحة تحكم في المتصفح: http://localhost:8080
#   bash bot.sh stop              إيقاف
#   bash bot.sh status | log      الحالة | متابعة السجل
#   bash bot.sh shortcuts         اختصارات على الشاشة الرئيسية (تحتاج تطبيق Termux:Widget)
cd "$(dirname "$0")" || exit 1
mkdir -p runs
export RISH_APPLICATION_ID=com.termux
export LORDS_BACKEND=rish
PIDF=runs/bot.pid
LOGF=runs/out.log

running() { [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null; }

stop_bot() {
  if running; then kill "$(cat "$PIDF")" 2>/dev/null; sleep 1; fi
  pkill -f "python bot.py" 2>/dev/null
  rm -f "$PIDF"
  termux-wake-unlock 2>/dev/null
}

start_bot() {
  if ! rish -c id 2>/dev/null | grep -q "uid=2000"; then
    echo "Shizuku لا يعمل: افتح تطبيق Shizuku واضغط Start ثم أعد الأمر."
    exit 1
  fi
  stop_bot
  termux-wake-lock 2>/dev/null
  nohup python bot.py "$@" >> "$LOGF" 2>&1 &
  echo $! > "$PIDF"
  echo "بدأ (PID $(cat "$PIDF")). المتابعة: bash bot.sh log   الإيقاف: bash bot.sh stop"
}

case "$1" in
  hunt)
    shift
    if [ -n "$1" ]; then start_bot --task hunt --level "$1" --loop; else start_bot --task hunt --loop; fi ;;
  gather)
    shift
    if [ -n "$2" ]; then start_bot --task gather --resource "$1" --level "$2" --loop
    elif [ -n "$1" ]; then start_bot --task gather --resource "$1" --loop
    else start_bot --task gather --loop; fi ;;
  all)
    shift
    if [ -n "$2" ]; then start_bot --task all --resource "$1" --level "$2" --loop
    elif [ -n "$1" ]; then start_bot --task all --resource "$1" --loop
    else start_bot --task all --loop; fi ;;
  set) shift; python bot.py --set "$@" ;;
  debug)
    if [ "$2" = "off" ]; then python bot.py --set DEBUG=false; else python bot.py --set DEBUG=true; fi ;;
  panel) exec python panel.py "${@:2}" ;;
  stop) stop_bot; echo "تم الإيقاف." ;;
  status)
    if running; then echo "يعمل (PID $(cat "$PIDF"))"; else echo "متوقف"; fi
    tail -n 5 runs/bot.log 2>/dev/null
    [ -f runs/stats.json ] && cat runs/stats.json ;;
  log) tail -n 30 -f runs/bot.log ;;
  shortcuts)
    mkdir -p ~/.shortcuts
    DIR="$(pwd)"
    for t in hunt stop; do
      printf '#!/data/data/com.termux/files/usr/bin/bash\nbash %s/bot.sh %s\n' "$DIR" "$t" > ~/.shortcuts/bot-$t.sh
      chmod +x ~/.shortcuts/bot-$t.sh
    done
    echo "تم. أضف أداة Termux:Widget إلى الشاشة الرئيسية لتظهر bot-hunt و bot-stop." ;;
  *) sed -n '2,15p' "$0" ;;
esac
