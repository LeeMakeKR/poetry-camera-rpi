"""써멀 프린터 라스터 이미지 출력 헬퍼.

이 프린터(PC936 계열)는 Adafruit_Thermal.printImage() 가 쓰는 DC2 '*' 명령을
인식하지 못하고 이미지 데이터를 문자로 인쇄합니다. 대신 ESC/POS 라스터 명령
GS v 0 를 씁니다. 자세한 배경은 hardware_setup.md 의 "이미지 출력" 항목 참고.
"""

import time

from PIL import Image
from serial import Serial

WIDTH_DOTS = 384  # 58mm 감열지 기준 도트 폭
WIDTH_BYTES = WIDTH_DOTS // 8
MAX_CHUNK_ROWS = 128  # 한 번에 보낼 최대 행 수. 프린터 버퍼 보호용.
CHUNK_SETTLE = 0.05   # 청크 사이 여유. 버퍼가 비워질 시간을 조금 줍니다.
DEFAULT_LINE_SPACING = 32  # 프린터 기본 줄간격 (문자 24 + 여백 8)


def fit_width(image):
    """가로 384픽셀에 맞춰 비율을 유지한 채 축소하고 그레이스케일로 변환."""
    if image.size[0] == WIDTH_DOTS:
        return image.convert("L")
    ratio = WIDTH_DOTS / float(image.size[0])
    height = int(image.size[1] * ratio)
    return image.convert("L").resize((WIDTH_DOTS, height), Image.LANCZOS)


def to_raster_rows(mono):
    """1비트 이미지를 행별 라스터 바이트로 변환. 1비트 = 검정."""
    if mono.mode != "1":
        mono = mono.convert("1")
    packed = mono.tobytes()  # PIL 이 행당 바이트 경계에 맞춰 채워 줍니다.
    row_bytes = (mono.size[0] + 7) // 8
    # PIL 의 '1' 모드는 흰색이 1이므로 반전해야 검정이 1이 됩니다.
    inverted = bytes(b ^ 0xFF for b in packed)
    return [inverted[i:i + row_bytes] for i in range(0, len(inverted), row_bytes)]


def print_raster(printer, rows, baud):
    """행 목록을 GS v 0 명령으로 인쇄합니다.

    프린터 기본 줄간격은 32도트(문자 24 + 여백 8)입니다. 라스터 명령이
    끝날 때마다 이 여분 8도트가 따라붙어 이미지 사이가 약 1mm 벌어집니다.
    인쇄 동안만 줄간격을 0으로 두고 끝나면 기본값으로 되돌립니다.
    """
    # ESC 3 n : 줄간격을 n 도트로 설정
    printer.writeBytes(27, 51, 0)

    for start in range(0, len(rows), MAX_CHUNK_ROWS):
        chunk = rows[start:start + MAX_CHUNK_ROWS]
        height = len(chunk)
        header = bytes([
            29, 118, 48,                # GS v 0
            0,                          # m = 0 (일반 모드)
            WIDTH_BYTES & 0xFF,         # xL
            (WIDTH_BYTES >> 8) & 0xFF,  # xH
            height & 0xFF,              # yL
            (height >> 8) & 0xFF,       # yH
        ])
        payload = header + b"".join(chunk)

        # writeBytes() 는 대기 시간이 인자 수의 제곱에 비례해 대량 전송에
        # 쓸 수 없습니다. 부모 클래스의 write 로 한 번에 보냅니다.
        printer.timeoutWait()
        Serial.write(printer, payload)
        Serial.flush(printer)

        # 전송 시간과 인쇄 시간은 겹칩니다. 9600bps 로 한 행(48바이트)을
        # 보내는 데 55ms 가 걸리는데 인쇄기는 그보다 훨씬 빨라 항상 전송이
        # 병목입니다. 둘을 더하면 인쇄 시간만큼 그냥 놀게 됩니다.
        transmit = len(payload) * 11.0 / baud
        mechanical = height * printer.dotPrintTime
        time.sleep(max(transmit, mechanical) + CHUNK_SETTLE)

    # 이후의 텍스트 출력과 feed() 가 정상 간격을 갖도록 기본값으로 되돌립니다.
    printer.writeBytes(27, 51, DEFAULT_LINE_SPACING)
    printer.timeoutSet(0)


def print_image(printer, image, baud):
    """PIL 이미지를 384픽셀 폭으로 맞춰 인쇄합니다."""
    rows = to_raster_rows(fit_width(image))
    print_raster(printer, rows, baud)
    return len(rows)
