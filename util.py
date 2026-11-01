"""أدوات مشتركة: سجل يُكتب على الشاشة وفي runs/bot.log، وإحصائيات الجولات."""
import json
import os
from datetime import datetime

import config

_MAX_LOG_BYTES = 1_000_000


def log(msg):
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(line, flush=True)
    try:
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        path = os.path.join(config.OUTPUT_DIR, "bot.log")
        if os.path.exists(path) and os.path.getsize(path) > _MAX_LOG_BYTES:
            os.replace(path, path + ".old")
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now():%Y-%m-%d} {line}\n")
    except OSError:
        pass


def record_round(results):
    """يجمع عدد الجيوش لكل مهمة في runs/stats.json ويعيد الإجمالي."""
    path = os.path.join(config.OUTPUT_DIR, "stats.json")
    try:
        with open(path, encoding="utf-8") as f:
            st = json.load(f)
    except (OSError, ValueError):
        st = {}
    st.setdefault("rounds", 0)
    st.setdefault("marches", {})
    st["rounds"] += 1
    for k, v in results.items():
        st["marches"][k] = st["marches"].get(k, 0) + v
    st["last_round"] = datetime.now().isoformat(timespec="seconds")
    try:
        os.makedirs(config.OUTPUT_DIR, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False, indent=2)
    except OSError:
        pass
    return st
