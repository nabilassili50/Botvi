#!/data/data/com.termux/files/usr/bin/bash
# تثبيت متطلبات البوت على Termux
set -e
pkg update -y
pkg install -y python python-numpy opencv-python android-tools git
termux-wake-lock 2>/dev/null || true
echo
echo "تم. الخطوة التالية: اربط adb بالجهاز نفسه (راجع README، قسم Termux)."
