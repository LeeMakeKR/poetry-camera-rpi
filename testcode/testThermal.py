#!/usr/bin/env python3
"""TTL 써멀 프린터 진단 테스트.

종이에 인쇄된 결과만 보고 어떤 설정을 써야 하는지 바로 알 수 있도록,
모든 출력 블록에 그 블록이 사용한 설정값을 함께 인쇄합니다.

사용법:
  python3 testThermal.py baud            # 1단계: 보레이트 찾기
  python3 testThermal.py heat --baud 9600    # 2단계: 농도(heat) 찾기
  python3 testThermal.py full --baud 9600    # 3단계: 폭/펌웨어/스타일 확인

기본 포트는 /dev/serial0 이며 dialout 그룹이면 sudo 없이 실행됩니다.
"""

import argparse
import sys
import time

sys.path.insert(0, "/home/poetry/poetry-camera-rpi/python")
sys.path.insert(0, "..")

from Adafruit_Thermal import Adafruit_Thermal

CANDIDATE_BAUDS = [9600, 19200, 38400, 57600, 115200]
CANDIDATE_HEATTIMES = [80, 120, 180, 255]

# 42칸 자. 32칸/42칸 지점에 표시가 있어 인쇄 폭을 눈으로 셀 수 있음.
RULER_DIGITS = "1234567890" * 4 + "12"
RULER_MARKS = "." * 31 + "|" + "." * 9 + "|"


def open_printer(port, baud, firmware, heattime):
    # Adafruit_Thermal 은 firmware/heattime kwargs 를 그대로 pyserial 로 넘겨서
    # pyserial 3.5 에서 TypeError 가 납니다. 생성 후 직접 지정합니다.
    printer = Adafruit_Thermal(port, baud, timeout=5)
    printer.firmwareVersion = firmware
    # ESC 7 n1 n2 n3 : 최대 발열 도트, 발열 시간, 발열 간격
    printer.writeBytes(27, 55, 11, heattime, 40)
    return printer


def banner(printer, title):
    printer.justify("C")
    printer.boldOn()
    printer.println("=" * 32)
    printer.println(title)
    printer.println("=" * 32)
    printer.boldOff()
    printer.justify("L")


def stage_baud(args):
    """보레이트를 바꿔가며 같은 문장을 인쇄. 읽히는 블록의 숫자가 정답."""
    print("[baud] 후보 %d개 시도. 종이에서 글자가 읽히는 블록을 찾으세요." % len(CANDIDATE_BAUDS))
    for baud in CANDIDATE_BAUDS:
        print("  -> %d bps 전송 중" % baud)
        try:
            printer = open_printer(args.port, baud, args.firmware, args.heattime)
        except Exception as exc:  # 포트 자체를 못 여는 경우
            print("     실패: %s" % exc)
            continue

        printer.justify("C")
        printer.setSize("L")
        printer.println("BAUD %d" % baud)
        printer.setSize("S")
        printer.println("this line must be readable")
        printer.println("ABCDEFG 0123456789")
        printer.justify("L")
        printer.feed(3)
        printer.flush()
        time.sleep(1.5)
        printer.close()

    print("[baud] 완료. 깨끗하게 읽힌 블록의 숫자를 --baud 값으로 쓰세요.")


def stage_heat(args):
    """heat time을 바꿔가며 같은 문장을 인쇄. 가장 선명한 블록이 정답."""
    print("[heat] 후보 %d개 시도. 가장 선명하고 번지지 않은 블록을 고르세요." % len(CANDIDATE_HEATTIMES))
    for heattime in CANDIDATE_HEATTIMES:
        print("  -> heattime=%d" % heattime)
        printer = open_printer(args.port, args.baud, args.firmware, heattime)

        printer.justify("C")
        printer.setSize("M")
        printer.println("HEATTIME %d" % heattime)
        printer.setSize("S")
        printer.justify("L")
        printer.println("The quick brown fox jumps over")
        printer.println("the lazy dog. 0123456789")
        printer.boldOn()
        printer.println("BOLD SAMPLE - check for smear")
        printer.boldOff()
        # 흑백 대비 확인용 반전 블록
        printer.inverseOn()
        printer.println(" SOLID BLACK BLOCK TEST ")
        printer.inverseOff()
        printer.feed(3)
        printer.flush()
        time.sleep(2)
        printer.close()

    print("[heat] 완료. 흐리면 값을 올리고, 번지면 내리세요.")


def stage_full(args):
    """확정된 설정으로 폭/펌웨어/스타일/한글을 한 번에 점검."""
    print("[full] baud=%d firmware=%d heattime=%d" % (args.baud, args.firmware, args.heattime))
    printer = open_printer(args.port, args.baud, args.firmware, args.heattime)

    banner(printer, "PRINTER SELF TEST")
    printer.println("port     : %s" % args.port)
    printer.println("baud     : %d" % args.baud)
    printer.println("firmware : %.2f" % (args.firmware / 100.0))
    printer.println("heattime : %d" % args.heattime)
    printer.feed(1)

    # --- 1. 인쇄 폭 ---
    banner(printer, "1. COLUMN WIDTH")
    printer.println("count the digits that fit:")
    printer.println(RULER_DIGITS)
    printer.println(RULER_MARKS)
    printer.println("first | = col 32, second = col 42")
    printer.println("-> use that number as line width")
    printer.feed(1)

    # --- 2. 글자 크기 ---
    banner(printer, "2. TEXT SIZE")
    for size in ("S", "M", "L"):
        printer.setSize(size)
        printer.println("size %s 0123456789" % size)
    printer.setSize("S")
    printer.feed(1)

    # --- 3. 스타일 ---
    banner(printer, "3. STYLES")
    printer.boldOn()
    printer.println("bold on")
    printer.boldOff()
    printer.underlineOn()
    printer.println("underline on")
    printer.underlineOff()
    printer.inverseOn()
    printer.println("inverse on")
    printer.inverseOff()
    printer.doubleHeightOn()
    printer.println("double height")
    printer.doubleHeightOff()
    printer.upsideDownOn()
    printer.println("upside down")
    printer.upsideDownOff()
    printer.strikeOn()
    printer.println("strike through")
    printer.strikeOff()
    printer.println("(missing/garbled item = not")
    printer.println(" supported by this firmware)")
    printer.feed(1)

    # --- 4. 정렬 ---
    banner(printer, "4. JUSTIFY")
    for mode, label in (("L", "LEFT"), ("C", "CENTER"), ("R", "RIGHT")):
        printer.justify(mode)
        printer.println(label)
    printer.justify("L")
    printer.feed(1)

    # --- 5. 줄간격 ---
    banner(printer, "5. LINE HEIGHT")
    for height in (24, 32, 48):
        printer.setLineHeight(height)
        printer.println("lineHeight %d" % height)
    printer.setLineHeight()
    printer.feed(1)

    # --- 6. 한글 ---
    banner(printer, "6. KOREAN / UTF-8")
    try:
        printer.println("한글 테스트 가나다")
        printer.println("-> readable = codepage ok")
        printer.println("-> garbage  = ASCII only")
    except Exception as exc:
        printer.println("korean write failed")
        print("  한글 전송 예외: %s" % exc)
    printer.feed(1)

    # --- 7. 상태 ---
    banner(printer, "7. STATUS")
    try:
        paper = printer.hasPaper()
        printer.println("hasPaper() = %s" % paper)
        print("  hasPaper() = %s" % paper)
    except Exception as exc:
        printer.println("hasPaper() unsupported")
        print("  hasPaper 예외: %s" % exc)

    printer.justify("C")
    printer.boldOn()
    printer.println("END OF TEST")
    printer.boldOff()
    printer.justify("L")
    printer.feed(4)
    printer.flush()
    time.sleep(2)
    printer.close()
    print("[full] 완료.")


def main():
    parser = argparse.ArgumentParser(description="TTL 써멀 프린터 진단 테스트")
    parser.add_argument("stage", choices=["baud", "heat", "full"])
    parser.add_argument("--port", default="/dev/serial0")
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument("--firmware", type=int, default=268,
                        help="268 또는 264. feed/barcode 동작이 이상하면 264로 시도")
    parser.add_argument("--heattime", type=int, default=255)
    args = parser.parse_args()

    {"baud": stage_baud, "heat": stage_heat, "full": stage_full}[args.stage](args)


if __name__ == "__main__":
    main()
