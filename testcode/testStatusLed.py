#!/usr/bin/env python3
"""main.py 의 상태 LED 단계를 순서대로 재현합니다.

카메라나 API 없이 색 전환만 눈으로 확인할 때 씁니다.
WS2812 는 /dev/mem 에 접근하므로 반드시 sudo 로 실행해야 합니다.
sudo 없이 실행하면 예외가 아니라 세그멘테이션 폴트로 죽습니다.

  sudo -E PYTHONPATH=/home/poetry/.local/lib/python3.13/site-packages \
    python3 testStatusLed.py
"""

import os
import sys
import time

# sudo 로 실행하면 ~ 가 /root 로 바뀌므로 경로를 직접 지정합니다.
for candidate in (
    "/home/poetry/poetry-camera-rpi/python",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python"),
):
    if os.path.isdir(candidate):
        sys.path.insert(0, candidate)

import main

STAGES = [
    ("부팅/초기화 - 빨강 고정", lambda: main.status_led.solid(main.COLOR_BOOT), 3),
    ("준비 완료 - 초록 고정", lambda: main.status_led.solid(main.COLOR_IDLE), 3),
    ("촬영/시 생성 - 초록 점멸", lambda: main.status_led.blink(main.COLOR_CAPTURE), 5),
    ("인쇄 중 - 파랑 점멸", lambda: main.status_led.blink(main.COLOR_PRINT), 5),
    ("완료 - 초록 고정", lambda: main.status_led.solid(main.COLOR_IDLE), 3),
]


def run():
    for label, action, seconds in STAGES:
        print("%-24s (%d초)" % (label, seconds))
        action()
        time.sleep(seconds)

    main.status_led.off()
    print("테스트 종료 - LED 끔")


if __name__ == "__main__":
    run()
