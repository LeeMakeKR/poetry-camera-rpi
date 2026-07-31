#!/usr/bin/env python3
"""카메라 촬영 테스트.

해상도별로 촬영해 파일 크기와 평균 밝기를 함께 출력합니다.
평균 밝기를 보면 사진을 열어보지 않고도 렌즈캡, 케이블 역방향,
조명 부족 같은 문제를 바로 구분할 수 있습니다.

  python3 testCamera.py
  python3 testCamera.py --outdir ~/captures --warmup 4
"""

import argparse
import os
import time

import numpy as np
from picamera2 import Picamera2

# ov5647 (Camera Module v1) 기준 대표 해상도
RESOLUTIONS = [
    (640, 480),
    (1296, 972),
    (1920, 1080),
    (2592, 1944),
]


def describe_brightness(mean):
    if mean < 10:
        return "거의 검정 - 렌즈캡 또는 케이블 역방향 의심"
    if mean < 40:
        return "매우 어두움 - 조명 부족"
    if mean > 245:
        return "거의 백색 - 과노출 또는 직사광"
    if mean > 210:
        return "밝음 - 과노출 경향"
    return "정상 범위"


def capture(picam2, size, outdir, warmup):
    config = picam2.create_still_configuration(main={"size": size})
    picam2.configure(config)
    picam2.start()
    # 자동 노출/화이트밸런스가 수렴할 시간을 줍니다.
    time.sleep(warmup)

    array = picam2.capture_array("main")
    path = os.path.join(outdir, "capture_%dx%d.jpg" % size)
    started = time.time()
    picam2.capture_file(path)
    elapsed = time.time() - started

    picam2.stop()

    # RGB 채널만 사용 (XBGR8888 등 알파 채널이 붙는 포맷 대비)
    mean = float(np.mean(array[:, :, :3]))
    size_kb = os.path.getsize(path) / 1024.0

    print("  %-10s %7.1f KB  %5.1fs  밝기 %5.1f  %s" % (
        "%dx%d" % size, size_kb, elapsed, mean, describe_brightness(mean)))
    return mean


def main():
    parser = argparse.ArgumentParser(description="카메라 촬영 테스트")
    parser.add_argument("--outdir", default=os.path.expanduser("~/testcode/captures"))
    parser.add_argument("--warmup", type=float, default=2.0,
                        help="촬영 전 자동 노출 수렴 대기 시간(초)")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    picam2 = Picamera2()
    props = picam2.camera_properties
    print("모델    : %s" % props.get("Model"))
    print("센서    : %sx%s" % tuple(props.get("PixelArraySize", ("?", "?"))))
    print("저장 위치: %s" % args.outdir)
    print()
    print("  해상도        용량     시간   밝기   판정")

    means = []
    try:
        for size in RESOLUTIONS:
            means.append(capture(picam2, size, args.outdir, args.warmup))
    finally:
        picam2.close()

    print()
    overall = sum(means) / len(means)
    if overall < 10:
        print("결과: 모든 촬영이 거의 검정입니다. 렌즈캡과 리본 케이블 방향을 확인하세요.")
    else:
        print("결과: 촬영 정상. 평균 밝기 %.1f" % overall)


if __name__ == "__main__":
    main()
