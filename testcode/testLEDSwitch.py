import time
import board
import digitalio
import neopixel

# 스위치를 누를 때마다 LED 색이 R -> G -> B 순서로 바뀝니다.
# 스위치: GPIO20 (물리 핀 38), 한쪽 GPIO20 / 다른 쪽 GND
# WS2812: GPIO21 (물리 핀 40)
PIXEL_PIN = board.D21
SWITCH_PIN = board.D20
PIXEL_COUNT = 1
BRIGHTNESS = 0.3
DEBOUNCE = 0.05

COLORS = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
NAMES = ["RED", "GREEN", "BLUE"]

pixels = neopixel.NeoPixel(
    PIXEL_PIN,
    PIXEL_COUNT,
    brightness=BRIGHTNESS,
    auto_write=False,
    pixel_order=neopixel.GRB,
)

# 내부 풀업 사용: 안 누름 = True(3.3V), 누름 = False(GND)
switch = digitalio.DigitalInOut(SWITCH_PIN)
switch.direction = digitalio.Direction.INPUT
switch.pull = digitalio.Pull.UP

index = -1
prev = switch.value

try:
    pixels.fill((0, 0, 0))
    pixels.show()
    print("Waiting for switch on GPIO20 (Ctrl+C to stop)", flush=True)

    while True:
        current = switch.value
        # 눌리는 순간(하강 엣지)에만 색을 넘김
        if prev and not current:
            index = (index + 1) % len(COLORS)
            pixels[0] = COLORS[index]
            pixels.show()
            print("pressed -> {0}".format(NAMES[index]), flush=True)
            time.sleep(DEBOUNCE)
        prev = current
        time.sleep(0.01)
except KeyboardInterrupt:
    pixels.fill((0, 0, 0))
    pixels.show()
    print("LED switch test stopped")
