#!/usr/bin/env python3
"""써멀 프린터 기본 출력 테스트.

프린터 전원 투입 시 자체 인쇄된 정보 기준:
  9600bps / codepage / U24 / PC936

  python3 testThermalPrint.py
  python3 testThermalPrint.py --baud 19200 --heattime 180
"""

import argparse
import sys
import time

sys.path.insert(0, "/home/poetry/poetry-camera-rpi/python")
sys.path.insert(0, "..")

from Adafruit_Thermal import Adafruit_Thermal

# 42칸 자. 32칸 지점과 42칸 지점에 표시가 있어 인쇄 폭을 눈으로 셀 수 있음.
RULER_DIGITS = "1234567890" * 4 + "12"
RULER_MARKS = "." * 31 + "|" + "." * 9 + "|"


def main():
    parser = argparse.ArgumentParser(description="써멀 프린터 기본 출력 테스트")
    parser.add_argument("--port", default="/dev/serial0")
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument("--heattime", type=int, default=255)
    args = parser.parse_args()

    print("연결: %s @ %d bps (heattime=%d)" % (args.port, args.baud, args.heattime))

    # Adafruit_Thermal 은 firmware/heattime kwargs 를 pyserial 로 그대로 넘겨
    # pyserial 3.5 에서 TypeError 를 냅니다. 생성 후 직접 지정합니다.
    printer = Adafruit_Thermal(args.port, args.baud, timeout=5)
    # ESC 7 n1 n2 n3 : 최대 발열 도트, 발열 시간, 발열 간격
    printer.writeBytes(27, 55, 11, args.heattime, 40)

    printer.justify("C")
    printer.boldOn()
    printer.println("PRINT TEST OK")
    printer.boldOff()
    printer.justify("L")

    printer.println("baud     : %d" % args.baud)
    printer.println("heattime : %d" % args.heattime)
    printer.println("The quick brown fox jumps over")
    printer.println("the lazy dog. 0123456789")

    # 한 줄에 몇 글자가 들어가는지 세기 위한 자
    printer.println(RULER_DIGITS)
    printer.println(RULER_MARKS)

    printer.feed(3)
    printer.flush()
    time.sleep(2)
    printer.close()
    print("전송 완료. 종이를 확인하세요.")


if __name__ == "__main__":
    main()
