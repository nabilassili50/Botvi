"""التقاط قوالب المباني من لقطة القلعة بعد التصغير الأقصى.

وضع الواجهة الرسومية (حاسوب):
    python capture_templates.py                 # يصغّر ثم تحدد المباني بالفأرة
    python capture_templates.py --no-zoom
    python capture_templates.py --image shot.png

وضع الطرفية فقط (Termux):
    python capture_templates.py --grab shot.png --grid     # يصغّر ويحفظ shot.png + shot_grid.png (شبكة إحداثيات)
    python capture_templates.py --image shot.png --crop barracks 420 310 90 80
        # يقص المستطيل (x y w h) ويحفظه في templates/barracks/

نصيحة: أنشئ القوالب على الحاسوب ثم ارفعها إلى GitHub واسحبها في Termux.
"""
import argparse
import os

import cv2

import config
from bot import zoom_out_max
from device import Device


def save_crop(img, name, x, y, w, h, ui=False):
    crop = img[y:y + h, x:x + w]
    if crop.size == 0:
        raise SystemExit("المستطيل خارج الصورة")
    folder = os.path.join(config.TEMPLATES_DIR, ("_" if ui else "") + name)
    os.makedirs(folder, exist_ok=True)
    n = len([f for f in os.listdir(folder) if f.endswith(".png")]) + 1
    path = os.path.join(folder, f"{name}_{n}.png")
    cv2.imwrite(path, crop)
    print("حُفظ:", path)


def draw_grid(img, step=100):
    out = img.copy()
    h, w = out.shape[:2]
    for x in range(0, w, step):
        cv2.line(out, (x, 0), (x, h), (0, 255, 255), 1)
        cv2.putText(out, str(x), (x + 2, 14), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)
    for y in range(0, h, step):
        cv2.line(out, (0, y), (w, y), (0, 255, 255), 1)
        cv2.putText(out, str(y), (2, y - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 1)
    return out


def interactive(img):
    h, w = img.shape[:2]
    view_scale = min(1.0, 900 / h)
    view = cv2.resize(img, None, fx=view_scale, fy=view_scale)
    while True:
        r = cv2.selectROI("اختر مبنى (Enter=تأكيد, Esc=إنهاء)", view, showCrosshair=False)
        if r == (0, 0, 0, 0):
            break
        x, y, rw, rh = [int(v / view_scale) for v in r]
        name = input("اسم المبنى (فارغ=إنهاء): ").strip().replace(" ", "_")
        if not name:
            break
        save_crop(img, name, x, y, rw, rh)
    cv2.destroyAllWindows()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-zoom", action="store_true")
    ap.add_argument("--image", help="استخدم صورة جاهزة بدل الجهاز")
    ap.add_argument("--grab", metavar="FILE", help="التقط (بعد التصغير) واحفظ ثم اخرج")
    ap.add_argument("--grid", action="store_true", help="احفظ نسخة عليها شبكة إحداثيات")
    ap.add_argument("--crop", nargs=5, metavar=("NAME", "X", "Y", "W", "H"))
    ap.add_argument("--ui", nargs=5, metavar=("NAME", "X", "Y", "W", "H"),
                    help="قص زر واجهة وحفظه في templates/_NAME (للصيد والجمع)")
    ap.add_argument("--serial")
    args = ap.parse_args()

    if args.image:
        img = cv2.imread(args.image)
        if img is None:
            raise SystemExit(f"تعذر فتح {args.image}")
    else:
        dev = Device(args.serial)
        img = dev.screenshot() if args.no_zoom else zoom_out_max(dev)

    if args.grab:
        cv2.imwrite(args.grab, img)
        print("حُفظ:", args.grab)
        if args.grid:
            gp = os.path.splitext(args.grab)[0] + "_grid.png"
            cv2.imwrite(gp, draw_grid(img))
            print("حُفظ:", gp)
        return

    if args.ui:
        name, x, y, w, h = args.ui
        save_crop(img, name.replace(" ", "_"), int(x), int(y), int(w), int(h), ui=True)
        return

    if args.crop:
        name, x, y, w, h = args.crop
        save_crop(img, name.replace(" ", "_"), int(x), int(y), int(w), int(h))
        return

    try:
        interactive(img)
    except cv2.error:
        raise SystemExit("لا توجد واجهة رسومية هنا. استخدم --grab ثم --crop (انظر أعلى الملف).")


if __name__ == "__main__":
    main()
