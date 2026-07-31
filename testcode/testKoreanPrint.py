#!/usr/bin/env python3
"""한글 시 인쇄 경로만 따로 시험합니다.

Gemini API 키 없이 main.py 의 인쇄 함수들을 그대로 호출해
폰트 렌더링과 GS v 0 라스터 출력이 맞는지 확인합니다.

main.py 를 임포트하므로 WS2812 초기화가 함께 일어납니다.
sudo 없이 실행하면 세그멘테이션 폴트로 죽으니 반드시 sudo 를 붙이세요.

  sudo -E PYTHONPATH=/home/poetry/.local/lib/python3.13/site-packages \
    python3 testKoreanPrint.py
"""

import os
import sys

for candidate in (
    os.path.expanduser("~/poetry-camera-rpi/python"),
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "python"),
):
    if os.path.isdir(candidate):
        sys.path.insert(0, candidate)

import main

SAMPLE_POEM = """저녁 마당

빨래가 바람에 젖은 목을 흔들고
담장 위 고양이는 눈을 반쯤 감는다

식은 밥솥에서 김이 마지막으로 오르고
숟가락 두 개가 나란히 놓인다

문틈으로 들어온 저녁이
발밑까지 천천히 번진다"""


def main_test():
    main.SELECTED_FONT_PATH = main.get_random_korean_font()
    print("한 줄 최대 글자수: %d자" % main.calculate_chars_per_line())

    main.print_header()
    main.print_separator()
    main.print_poem(SAMPLE_POEM)
    main.print_separator()
    main.print_footer()
    print("인쇄 완료. 종이를 확인하세요.")


if __name__ == "__main__":
    main_test()
