#!/usr/bin/env python3
"""촬영 -> 인쇄 연동 테스트.

카메라로 한 장 찍은 뒤 흑백 변환 방식을 바꿔 인쇄합니다.
종이에 각 방식의 이름이 함께 찍히므로 어느 쪽이 나은지 바로 고를 수 있습니다.

이 프린터는 Adafruit_Thermal.printImage() 가 쓰는 DC2 '*' 명령을 지원하지
않으므로 thermal_raster 모듈의 GS v 0 방식으로 출력합니다.

  python3 testCameraPrint.py                     # 3가지 방식 비교
  python3 testCameraPrint.py --variant 2         # 2번만 인쇄
  python3 testCameraPrint.py --image ~/a.jpg     # 촬영 대신 파일 사용
"""

import argparse
import os
import sys
import time

sys.path.insert(0, "/home/poetry/poetry-camera-rpi/python")
sys.path.insert(0, "..")

from PIL import Image, ImageEnhance, ImageOps

from Adafruit_Thermal import Adafruit_Thermal
from thermal_raster import fit_width, print_raster, to_raster_rows


def capture_photo(path, warmup):
    from picamera2 import Picamera2

    picam2 = Picamera2()
    picam2.configure(picam2.create_still_configuration(main={"size": (1296, 972)}))
    picam2.start()
    time.sleep(warmup)
    picam2.capture_file(path)
    picam2.close()
    return path


def variant_dither(gray):
    """기본: 그레이스케일 -> 오차확산 디더링."""
    return gray.convert("1")


def variant_autocontrast(gray):
    """자동 대비 보정 후 디더링. 실내 사진에서 형태가 또렷해집니다."""
    return ImageOps.autocontrast(gray, cutoff=2).convert("1")


def variant_threshold(gray):
    """디더링 없이 임계값 이진화. 글자나 도형이 많은 장면에 유리합니다."""
    boosted = ImageEnhance.Contrast(gray).enhance(1.6)
    return boosted.point(lambda p: 255 if p > 128 else 0, mode="1")


VARIANTS = [
    ("1 DITHER", variant_dither),
    ("2 AUTOCONTRAST", variant_autocontrast),
    ("3 THRESHOLD", variant_threshold),
]


def main():
    parser = argparse.ArgumentParser(description="촬영 -> 인쇄 연동 테스트")
    parser.add_argument("--image", help="지정하면 촬영 대신 이 파일을 사용")
    parser.add_argument("--outdir", default=os.path.expanduser("~/testcode/captures"))
    # 1 DITHER 가 실물 인쇄에서 가장 보기 좋아 기본값으로 씁니다.
    parser.add_argument("--variant", choices=["1", "2", "3", "all"], default="1")
    parser.add_argument("--port", default="/dev/serial0")
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument("--heattime", type=int, default=255)
    parser.add_argument("--warmup", type=float, default=2.0)
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    if args.image:
        source = os.path.expanduser(args.image)
        print("사용할 이미지: %s" % source)
    else:
        source = os.path.join(args.outdir, "print_source.jpg")
        print("촬영 중 (워밍업 %.1fs)" % args.warmup)
        capture_photo(source, args.warmup)
        print("촬영 완료: %s" % source)

    gray = fit_width(Image.open(source))
    print("인쇄 크기: %dx%d" % gray.size)

    selected = VARIANTS if args.variant == "all" else [
        v for v in VARIANTS if v[0].startswith(args.variant)
    ]

    printer = Adafruit_Thermal(args.port, args.baud, timeout=5)
    printer.writeBytes(27, 55, 11, args.heattime, 40)

    for label, convert in selected:
        mono = convert(gray)
        mono.save(os.path.join(args.outdir, "print_%s.png" % label.split()[0]))
        rows = to_raster_rows(mono)

        printer.justify("C")
        printer.boldOn()
        printer.println(label)
        printer.boldOff()
        printer.justify("L")
        printer.flush()
        time.sleep(0.3)

        started = time.time()
        print_raster(printer, rows, args.baud)
        print("  %-16s %d행 인쇄, %.1fs" % (label, len(rows), time.time() - started))

        printer.feed(2)
        printer.flush()
        time.sleep(0.5)
1
    printer.feed(3)
    printer.flush()
    time.sleep(2)
    printer.close()
    print("완료. 종이에서 가장 잘 보이는 번호를 고르세요.")


if __name__ == "__main__":
    main()
