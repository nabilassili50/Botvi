"""اختبار القرص: افتح اللعبة في المدينة خلال 15 ثانية ولا تخرج منها."""
import time

import cv2

from device import Device
from vision import frame_diff

d = Device()
print("touch:", d._touch_info()["path"])
print("open the game in the city - 15s")
time.sleep(15)
print("foreground:", d.is_foreground())
a = d.screenshot()
cv2.imwrite("t0.png", a)

d.pinch_out()                      # تكبير
time.sleep(1.5)
b = d.screenshot()
cv2.imwrite("t1_out.png", b)
print("after zoom-IN  diff =", round(frame_diff(a, b), 2))

d.pinch_in()                       # تصغير
time.sleep(1.5)
c = d.screenshot()
cv2.imwrite("t2_in.png", c)
print("after zoom-OUT diff =", round(frame_diff(b, c), 2))
