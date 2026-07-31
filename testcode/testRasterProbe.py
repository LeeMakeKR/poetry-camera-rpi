#!/usr/bin/env python3
"""GS v 0 라스터 비트맵 명령 호환성 확인.

Adafruit_Thermal.printImage() 가 쓰는 DC2 '*' (18, 42) 명령을 이 프린터가
인식하지 못해 이미지 데이터가 전부 문자로 인쇄되는 문제가 있었습니다.
이 스크립트는 대안인 ESC/POS 라스터 명령 GS v 0 (29, 118, 48) 를
384x32 픽셀, 즉 종이 약 5cm 분량으로만 시험합니다.

정상이면 아래 4개 띠가 순서대로 보입니다.
  1) 꽉 찬 검정 띠
  2) 세로 줄무늬
  3) 왼쪽 절반만 검정
  4) 꽉 찬 검정 띠

문자가 쏟아지면 이 프린터는 GS v 0 도 지원하지 않는 것입니다.

  python3 testRasterProbe.py
"""

import argparse
import sys
import time

sys.path.insert(0, "/home/poetry/poetry-camera-rpi/python")
sys.path.insert(0, "..")

from serial import Serial

from Adafruit_Thermal import Adafruit_Thermal

WIDTH_DOTS = 384
WIDTH_BYTES = WIDTH_DOTS // 8  # 48
DEFAULT_BAND_HEIGHT = 40


def build_pattern(band_height):
    """4개 띠로 구성된 흑백 패턴을 라스터 바이트로 만듭니다."""
    rows = []
    # 1) 꽉 찬 검정
    rows += [bytes([0xFF] * WIDTH_BYTES)] * band_height
    # 2) 세로 줄무늬 (1픽셀 검정 / 1픽셀 흰색)
    rows += [bytes([0xAA] * WIDTH_BYTES)] * band_height
    # 3) 왼쪽 절반만 검정 (좌우 방향 확인용)
    half = bytes([0xFF] * (WIDTH_BYTES // 2) + [0x00] * (WIDTH_BYTES // 2))
    rows += [half] * band_height
    # 4) 꽉 찬 검정
    rows += [bytes([0xFF] * WIDTH_BYTES)] * band_height
    return rows


def send_raster(printer, rows, baud):
    """GS v 0 m xL xH yL yH + 비트맵 데이터.

    Adafruit_Thermal.writeBytes() 는 인자 N개를 넘기면 바이트마다 N배씩
    대기해 총 대기 시간이 N^2 에 비례합니다. 대량 데이터에는 쓸 수 없으므로
    부모 클래스인 Serial.write 로 한 번에 보내고 대기 시간을 직접 계산합니다.
    """
    height = len(rows)
    header = bytes([
        29, 118, 48,                 # GS v 0
        0,                           # m = 0 (일반 모드)
        WIDTH_BYTES & 0xFF,          # xL
        (WIDTH_BYTES >> 8) & 0xFF,   # xH
        height & 0xFF,               # yL
        (height >> 8) & 0xFF,        # yH
    ])
    payload = header + b"".join(rows)

    printer.timeoutWait()
    Serial.write(printer, payload)
    Serial.flush(printer)

    # 전송 시간(1바이트 = 시작/정지 비트 포함 11비트) + 실제 인쇄 시간
    wait = len(payload) * 11.0 / baud + height * printer.dotPrintTime
    time.sleep(wait)
    printer.timeoutSet(0)


def main():
    parser = argparse.ArgumentParser(description="GS v 0 라스터 명령 호환성 확인")
    parser.add_argument("--port", default="/dev/serial0")
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument("--heattime", type=int, default=255)
    parser.add_argument("--band", type=int, default=DEFAULT_BAND_HEIGHT,
                        help="띠 하나의 높이(도트). 기본 40 = 띠 4개로 160도트")
    args = parser.parse_args()

    printer = Adafruit_Thermal(args.port, args.baud, timeout=5)
    printer.writeBytes(27, 55, 11, args.heattime, 40)

    printer.justify("C")
    printer.boldOn()
    printer.println("GS v 0 RASTER PROBE")
    printer.boldOff()
    printer.justify("L")
    printer.flush()
    time.sleep(0.5)

    pattern = build_pattern(args.band)
    print("라스터 데이터 %d바이트 전송 중 (384x%d)" % (
        WIDTH_BYTES * len(pattern), len(pattern)))
    send_raster(printer, pattern, args.baud)

    printer.feed(3)
    printer.flush()
    time.sleep(2)
    printer.close()
    print("전송 완료. 띠 4개가 보이면 성공입니다.")


if __name__ == "__main__":
    main()
