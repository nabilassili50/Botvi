#!/data/data/com.termux/files/usr/bin/bash
# Install Shizuku's `rish` into Termux.
# First, in the Shizuku app: "Use Shizuku in terminal apps" -> "Export files"
# and save them in Downloads (rish + rish_shizuku.dex).
set -e

termux-setup-storage 2>/dev/null || true

RISH=$(find ~/storage/downloads ~/storage/shared -maxdepth 3 -name rish -type f 2>/dev/null | head -1)
DEX=$(find ~/storage/downloads ~/storage/shared -maxdepth 3 -name rish_shizuku.dex -type f 2>/dev/null | head -1)

if [ -z "$RISH" ] || [ -z "$DEX" ]; then
  echo "Could not find rish and rish_shizuku.dex in Downloads."
  echo "Export them from the Shizuku app first (Use Shizuku in terminal apps -> Export files)."
  exit 1
fi

cp "$RISH" "$PREFIX/bin/rish"
cp "$DEX"  "$PREFIX/bin/rish_shizuku.dex"
chmod +x "$PREFIX/bin/rish"
chmod 400 "$PREFIX/bin/rish_shizuku.dex"

grep -q RISH_APPLICATION_ID ~/.bashrc 2>/dev/null || \
  echo 'export RISH_APPLICATION_ID=com.termux' >> ~/.bashrc
grep -q LORDS_BACKEND ~/.bashrc 2>/dev/null || \
  echo 'export LORDS_BACKEND=rish' >> ~/.bashrc

echo
echo "Done. Open a NEW Termux session (or run: source ~/.bashrc), then test:"
echo '  rish -c "id"      # should print uid=2000(shell)'
