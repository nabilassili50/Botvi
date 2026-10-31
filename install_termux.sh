#!/data/data/com.termux/files/usr/bin/bash
# Install the bot's requirements on Termux
set -e
pkg update -y
pkg install -y python python-numpy opencv-python git unzip
termux-setup-storage 2>/dev/null || true
termux-wake-lock 2>/dev/null || true
echo
echo "Done. Next: set up Shizuku and run  bash setup_rish.sh  (see README)."
