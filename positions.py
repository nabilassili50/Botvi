"""نقاط محفوظة (بدون قوالب): positions.json  {اسم: [fx, fy]} كنسب من الشاشة (0-1).

يُستعمل كاحتياط عندما لا يوجد قالب للمبنى/الزر أو لا يُرى على الشاشة.
صالح فقط عندما تكون القلعة مصغّرة للحد الأقصى وفي نفس موضعها (كما بعد zoom_out_max).
"""
import json
import os

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "positions.json")


def load():
    try:
        with open(PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    out = {}
    for k, v in data.items():
        try:
            fx, fy = float(v[0]), float(v[1])
        except (TypeError, ValueError, IndexError):
            continue
        if 0 <= fx <= 1 and 0 <= fy <= 1:
            out[k.lstrip("_")] = (fx, fy)
    return out


def _write(data):
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump({k: [round(v[0], 4), round(v[1], 4)] for k, v in sorted(data.items())},
                  f, ensure_ascii=False, indent=2)


def save(name, fx, fy):
    data = load()
    data[name.strip().lstrip("_")] = (min(1.0, max(0.0, fx)), min(1.0, max(0.0, fy)))
    _write(data)


def delete(name):
    data = load()
    data.pop(name.strip().lstrip("_"), None)
    _write(data)
