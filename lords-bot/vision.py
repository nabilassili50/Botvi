import os

import cv2
import numpy as np

import config


def to_gray(img):
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def frame_diff(a, b):
    """متوسط الفرق المطلق بين لقطتين بعد تصغيرهما وتنعيمهما."""
    def prep(x):
        g = to_gray(x)
        g = cv2.resize(g, (160, int(160 * g.shape[0] / g.shape[1])))
        return cv2.GaussianBlur(g, (5, 5), 0)
    return float(np.mean(cv2.absdiff(prep(a), prep(b))))


def load_templates(root=None):
    """يعيد (buildings, ui): كل منهما dict اسم -> قائمة صور رمادية."""
    root = root or config.TEMPLATES_DIR
    buildings, ui = {}, {}
    if not os.path.isdir(root):
        return buildings, ui
    for name in sorted(os.listdir(root)):
        folder = os.path.join(root, name)
        if not os.path.isdir(folder):
            continue
        imgs = []
        for f in sorted(os.listdir(folder)):
            if f.lower().endswith((".png", ".jpg", ".jpeg")):
                im = cv2.imread(os.path.join(folder, f), cv2.IMREAD_GRAYSCALE)
                if im is not None:
                    imgs.append(im)
        if imgs:
            (ui if name.startswith("_") else buildings)[name] = imgs
    return buildings, ui


def _iou(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    union = aw * ah + bw * bh - inter
    return inter / union if union else 0.0


def _ignored(cx, cy, shape):
    h, w = shape[:2]
    for x1, y1, x2, y2 in config.IGNORE_REGIONS:
        if x1 * w <= cx <= x2 * w and y1 * h <= cy <= y2 * h:
            return True
    return False


def match_one(gray, templates, scales, threshold):
    """كل تطابقات مجموعة قوالب لمبنى واحد: قائمة (x, y, w, h, score)."""
    hits = []
    for tpl in templates:
        for s in scales:
            t = cv2.resize(tpl, None, fx=s, fy=s,
                           interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)
            th, tw = t.shape
            if th < 12 or tw < 12 or th > gray.shape[0] or tw > gray.shape[1]:
                continue
            res = cv2.matchTemplate(gray, t, cv2.TM_CCOEFF_NORMED)
            ys, xs = np.where(res >= threshold)
            if len(xs) > 400:  # أقوى 400 نقطة فقط
                top = np.argsort(res[ys, xs])[-400:]
                ys, xs = ys[top], xs[top]
            for x, y in zip(xs, ys):
                hits.append((int(x), int(y), tw, th, float(res[y, x])))
    return hits


def detect_buildings(img, buildings, scales=None, threshold=None):
    scales = scales or config.SCALES
    threshold = threshold or config.MATCH_THRESHOLD
    gray = to_gray(img)
    candidates = []
    for name, tpls in buildings.items():
        for (x, y, w, h, sc) in match_one(gray, tpls, scales, threshold):
            candidates.append((name, x, y, w, h, sc))

    candidates.sort(key=lambda c: c[5], reverse=True)
    kept = []
    for c in candidates:
        cx, cy = c[1] + c[3] / 2, c[2] + c[4] / 2
        if _ignored(cx, cy, img.shape):
            continue
        if any(_iou(c[1:5], k[1:5]) > config.NMS_IOU for k in kept):
            continue
        kept.append(c)

    return [
        {"name": n, "x": x, "y": y, "w": w, "h": h,
         "cx": x + w // 2, "cy": y + h // 2, "score": round(sc, 3)}
        for (n, x, y, w, h, sc) in kept
    ]


def find_ui(img, ui_templates, prefix, threshold=None):
    """أفضل تطابق لعنصر واجهة (مثل زر إغلاق) اسمه يبدأ بـ prefix. يعيد (cx, cy) أو None."""
    threshold = threshold or config.CLOSE_POPUP_THRESHOLD
    gray = to_gray(img)
    best = None
    for name, tpls in ui_templates.items():
        if not name.lstrip("_").startswith(prefix):
            continue
        for (x, y, w, h, sc) in match_one(gray, tpls, [0.9, 1.0, 1.1], threshold):
            if best is None or sc > best[2]:
                best = (x + w // 2, y + h // 2, sc)
    return (best[0], best[1]) if best else None


def annotate(img, found):
    out = img.copy()
    for b in found:
        cv2.rectangle(out, (b["x"], b["y"]), (b["x"] + b["w"], b["y"] + b["h"]), (0, 255, 0), 2)
        cv2.putText(out, f'{b["name"]} {b["score"]}', (b["x"], max(12, b["y"] - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1, cv2.LINE_AA)
    return out
