#!/usr/bin/env python3
"""파이 UART 루프백 테스트.

파이의 TX(핀 8)와 RX(핀 10)를 점퍼선 하나로 직접 연결한 뒤 실행합니다.
보낸 문자열이 그대로 되돌아오면 파이 UART 송수신 회로가 정상이라는 뜻이며,
이후 문제는 전적으로 프린터 쪽(전원/배선/보레이트)에 있습니다.

  1) 프린터에서 핀 8, 핀 10 연결을 뺍니다.
  2) 핀 8 <-> 핀 10 을 점퍼선으로 직접 연결합니다.
  3) python3 testUartLoopback.py
"""

import sys
import time

import serial

PORT = "/dev/serial0"
BAUDS = [9600, 19200, 115200]
PAYLOAD = b"LOOPBACK-OK-0123456789"


def run(baud):
    with serial.Serial(PORT, baud, timeout=2) as ser:
        ser.reset_input_buffer()
        ser.write(PAYLOAD)
        ser.flush()
        time.sleep(0.3)
        echoed = ser.read(len(PAYLOAD))

    if echoed == PAYLOAD:
        print("  %6d bps : PASS  (%s)" % (baud, echoed.decode()))
        return True
    if not echoed:
        print("  %6d bps : FAIL  수신 0바이트" % baud)
    else:
        print("  %6d bps : FAIL  깨짐 -> %r" % (baud, echoed))
    return False


def main():
    print("핀 8 <-> 핀 10 을 점퍼선으로 연결한 상태여야 합니다.")
    results = [run(baud) for baud in BAUDS]

    print()
    if all(results):
        print("결과: 파이 UART 정상. 문제는 프린터 전원 또는 배선입니다.")
    elif any(results):
        print("결과: 일부 보레이트만 통과. 배선 접촉 불량을 의심하세요.")
    else:
        print("결과: 전부 실패. 점퍼선 연결 위치(핀 8, 핀 10)를 다시 확인하세요.")
        sys.exit(1)


if __name__ == "__main__":
    main()
