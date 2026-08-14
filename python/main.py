#!/usr/bin/python3
# 사진을 찍어 한국어 시를 만들고 감열 프린터로 출력합니다.
# picamera2 예제 capture_jpeg.py 를 기반으로 함.
#
# 하드웨어 설정과 실측값의 근거는 hardware_setup.md 를 참고하세요.
#   - 셔터 버튼 : GPIO20 (내부 풀업, 누르면 LOW)
#   - 상태 LED  : WS2812 1개, GPIO21
#   - 프린터    : /dev/serial0, 9600bps 고정, heattime 255
#   - 한글 출력 : 폰트로 이미지를 그린 뒤 GS v 0 라스터 명령으로 전송

import glob
import os
import random
import signal
import socket
import sys
import threading
import time
from datetime import datetime

import google.generativeai as genai
from dotenv import load_dotenv
from gpiozero import Button
from PIL import Image, ImageDraw, ImageFont
from picamera2 import Picamera2

# 이 파일은 python/ 안에 있고, fonts/ 와 images/ 는 저장소 루트에 있습니다.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPT_DIR)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from Adafruit_Thermal import Adafruit_Thermal
from thermal_raster import WIDTH_DOTS, print_image

###########################
# 설정
###########################

SHUTTER_PIN = 20        # 물리 핀 38
PIXEL_PIN_NUMBER = 21   # 물리 핀 40
PRINTER_PORT = "/dev/serial0"
PRINTER_BAUD = 9600     # 이 프린터는 9600 고정. 다른 프린터는 다를 수 있음.
PRINTER_HEATTIME = 255  # 80/120/180/255 비교 후 선택한 값

FONT_DIR = os.path.join(BASE_DIR, "fonts")
IMAGE_DIR = os.path.join(BASE_DIR, "images")

BODY_FONT_SIZE = 38   # 실물 확인 후 조정한 값
TITLE_FONT_SIZE = 40  # 본문보다 2도트 크게

# 9600bps 에서는 보내는 도트 수가 곧 인쇄 시간입니다.
# 빈 여백도 그대로 전송되므로 최소한만 둡니다.
BLOCK_MARGIN = 0  # 덩어리 위아래 여백 (도트)
LINE_GAP = 6      # 줄 사이 간격 (도트)
TEXT_MARGIN = 6  # 좌측 여백 (도트)

# 상태 표시 색상
# 부팅~초기화: 빨강 고정 -> 준비 완료: 초록 고정
# 촬영/시 생성: 초록 점멸 -> 인쇄: 파랑 점멸 -> 완료: 다시 초록 고정
COLOR_BOOT = (64, 0, 0)
COLOR_IDLE = (0, 32, 0)
COLOR_CAPTURE = (0, 48, 0)
COLOR_PRINT = (0, 0, 64)
COLOR_ERROR = (64, 0, 0)

# 네트워크가 끊기면 빨강 점멸로 알립니다. 시 생성에 인터넷이 필요합니다.
NETWORK_CHECK_HOST = ("8.8.8.8", 53)  # DNS 포트. 이름 해석 없이 연결만 확인
NETWORK_CHECK_TIMEOUT = 3
NETWORK_WAIT_SECONDS = 60  # 부팅 직후 와이파이가 붙을 때까지 기다릴 시간

# API 키는 저장소 루트의 .env 파일에서만 읽습니다.
# 작업 폴더가 달라져도 같은 파일을 보도록 경로를 명시합니다.
# 템플릿은 .env.example 이고, .env 는 .gitignore 에 있어 커밋되지 않습니다.
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(ENV_PATH)
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
else:
    # 키가 없어도 인쇄 관련 함수는 그대로 시험할 수 있게 두고, 안내만 합니다.
    print("GOOGLE_API_KEY 를 찾지 못했습니다. 시 생성은 실패합니다.")
    print("  키 파일 위치 : %s" % ENV_PATH)
    if not os.path.exists(ENV_PATH):
        print("  해결 방법   : cp %s %s 후 키를 채우세요"
              % (os.path.join(BASE_DIR, ".env.example"), ENV_PATH))
    else:
        print("  해결 방법   : 위 파일에 GOOGLE_API_KEY=... 줄을 추가하세요")

###########################
# 상태 LED (WS2812)
###########################


class StatusLed:
    """WS2812 한 개로 대기/처리/오류 상태를 표시합니다.

    neopixel 을 못 쓰는 환경에서도 프로그램이 멈추지 않도록 실패를 흡수합니다.
    """

    def __init__(self, pin_number):
        self._pixels = None
        self._blink_stop = None
        self._blink_thread = None
        try:
            import board
            import neopixel

            self._pixels = neopixel.NeoPixel(
                getattr(board, "D%d" % pin_number),
                1,
                brightness=1.0,
                auto_write=True,
                pixel_order=neopixel.GRB,
            )
            self.off()
        except Exception as exc:
            print("WS2812 초기화 실패, LED 없이 계속 진행합니다: %s" % exc)

    def _write(self, color):
        if self._pixels is not None:
            try:
                self._pixels.fill(color)
            except Exception as exc:
                print("LED 출력 실패: %s" % exc)

    def solid(self, color):
        self.stop_blink()
        self._write(color)

    def off(self):
        self.solid((0, 0, 0))

    def blink(self, color, interval=0.4):
        self.stop_blink()
        if self._pixels is None:
            return

        stop = threading.Event()

        def loop():
            on = True
            while not stop.is_set():
                self._write(color if on else (0, 0, 0))
                on = not on
                stop.wait(interval)
            self._write((0, 0, 0))

        self._blink_stop = stop
        self._blink_thread = threading.Thread(target=loop, daemon=True)
        self._blink_thread.start()

    def stop_blink(self):
        if self._blink_stop is not None:
            self._blink_stop.set()
            self._blink_thread.join(timeout=1)
            self._blink_stop = None
            self._blink_thread = None


###########################
# 초기화
###########################

status_led = StatusLed(PIXEL_PIN_NUMBER)
# 초기화가 끝날 때까지 빨강. 준비되면 main() 에서 초록으로 바꿉니다.
status_led.solid(COLOR_BOOT)

try:
    printer = Adafruit_Thermal(PRINTER_PORT, PRINTER_BAUD, timeout=5)
    # ESC 7 n1 n2 n3 : 최대 발열 도트, 발열 시간, 발열 간격
    printer.writeBytes(27, 55, 11, PRINTER_HEATTIME, 40)
    print("프린터 연결: %s @ %dbps" % (PRINTER_PORT, PRINTER_BAUD))
except Exception as exc:
    printer = None
    print("프린터 연결 실패, 인쇄 없이 계속 진행합니다: %s" % exc)

picam2 = Picamera2()
picam2.start()
time.sleep(2)  # 처음 몇 프레임은 품질이 낮아 예열 시간을 둡니다.

# bounce_time 으로 버튼 채터링을 막습니다.
shutter_button = Button(SHUTTER_PIN, bounce_time=0.1)

is_processing = False
SELECTED_FONT_PATH = None

###########################
# 프롬프트
###########################

system_prompt = """당신은 한국어 시를 쓰는 시인입니다. 우아하고 감정적으로 영향력 있는 한국어 시를 전문으로 합니다.
미묘함을 사용하고 현대적인 구어체 스타일로 작성합니다.
일상적인 한국어를 사용하되, 문학적인 기교를 사용합니다.
시는 문학적이면서도 공감하고 이해하기 쉬워야 합니다.
친밀하고 개인적인 진실에 집중하며, '진실', '시간', '침묵', '인생', '사랑', '평화', '전쟁', '증오', '행복' 같은 추상적이고 큰 단어를 직접적으로 사용하지 않습니다.
대신 구체적이고 명확한 언어를 사용하여 그러한 아이디어를 말하지 않고 보여줘야 합니다.
섬세하고 아름다운 한국어 시를 만드는 방법에 대해 신중하게 생각하세요.
이것은 매우 중요하며, 지나치게 서투르거나 진부한 시는 피해야 합니다."""

poem_format = "8줄 자유시 (한국어)"


###########################
# 네트워크
###########################


def has_network():
    """인터넷에 나갈 수 있는지 확인합니다."""
    try:
        socket.create_connection(NETWORK_CHECK_HOST, NETWORK_CHECK_TIMEOUT).close()
        return True
    except OSError:
        return False


def set_ready_state():
    """대기 상태 LED. 네트워크가 없으면 초록 대신 빨강 점멸로 알립니다."""
    if has_network():
        status_led.solid(COLOR_IDLE)
        return True

    status_led.blink(COLOR_ERROR)
    print("와이파이에 연결되어 있지 않습니다. 시 생성을 할 수 없습니다.")
    print("  wifi_networks.txt 를 확인하거나 휴대폰 핫스팟을 켜 보세요.")
    return False


def wait_for_network(seconds=NETWORK_WAIT_SECONDS):
    """부팅 직후 와이파이가 붙을 때까지 기다립니다. 기다리는 동안 빨강 점멸."""
    if has_network():
        return True

    print("와이파이 연결을 기다립니다 (최대 %d초)" % seconds)
    status_led.blink(COLOR_ERROR)

    deadline = time.time() + seconds
    while time.time() < deadline:
        time.sleep(3)
        if has_network():
            print("와이파이 연결됨")
            return True

    print("와이파이에 연결하지 못했습니다. 연결되면 자동으로 초록으로 바뀝니다.")
    return False


###########################
# 폰트
###########################


def get_random_korean_font():
    """fonts/ 아래에서 한글 폰트를 하나 무작위로 고릅니다."""
    patterns = ["*.ttf", "*.otf", "*.TTF", "*.OTF"]
    font_files = []
    for pattern in patterns:
        font_files.extend(glob.glob(os.path.join(FONT_DIR, "**", pattern), recursive=True))

    if not font_files:
        print("%s 에서 폰트를 찾지 못했습니다." % FONT_DIR)
        return None

    selected = random.choice(font_files)
    print("선택된 폰트: %s" % os.path.relpath(selected, BASE_DIR))
    return selected


def load_font(size):
    if SELECTED_FONT_PATH:
        try:
            return ImageFont.truetype(SELECTED_FONT_PATH, size)
        except Exception as exc:
            print("폰트 로드 실패, 기본 폰트를 사용합니다: %s" % exc)
    return ImageFont.load_default()


def usable_width(width=WIDTH_DOTS):
    """좌우 여백과 볼드 효과를 뺀 실제로 글자를 그릴 수 있는 폭."""
    return width - TEXT_MARGIN * 2 - 2


def measure_text(font, text):
    """폰트로 그렸을 때의 가로 폭(도트). 다음 글자가 시작할 위치까지 포함합니다."""
    try:
        return font.getlength(text)
    except AttributeError:
        # 아주 오래된 Pillow 대비. 잉크 폭이라 살짝 작게 나옵니다.
        bbox = font.getbbox(text)
        return bbox[2] - bbox[0]


def wrap_line(line, font, max_width):
    """실측 폭으로 한 줄을 나눕니다.

    폰트마다 글자 폭이 크게 다릅니다. 손글씨 폰트는 같은 글자 수라도 고딕보다
    훨씬 넓어 용지 밖으로 밀려납니다. 글자 수가 아니라 실제 픽셀 폭으로 끊습니다.
    한국어는 띄어쓰기가 드물어 단어 단위로만 나누면 여전히 넘치므로,
    단어 하나가 이미 폭을 넘으면 글자 단위로 끊습니다.
    """
    if not line or measure_text(font, line) <= max_width:
        return [line]

    wrapped = []
    current = ""
    for word in line.split(" "):
        candidate = word if not current else current + " " + word
        if measure_text(font, candidate) <= max_width:
            current = candidate
            continue

        if current:
            wrapped.append(current)
            current = ""

        for char in word:
            if current and measure_text(font, current + char) > max_width:
                wrapped.append(current)
                current = char
            else:
                current += char

    if current:
        wrapped.append(current)
    return wrapped


def calculate_chars_per_line(font_size=BODY_FONT_SIZE, width=WIDTH_DOTS):
    """선택된 폰트 기준으로 한 줄에 들어갈 글자 수를 추정합니다."""
    font = load_font(font_size)
    sample = "가나다라마바사아자차카타파하 일이삼사오육칠팔구십"

    widths = []
    for char in sample:
        try:
            widths.append(measure_text(font, char))
        except Exception:
            widths.append(font_size)

    if not widths:
        return 12

    average = sum(widths) / float(len(widths))
    return max(int(usable_width(width) / average), 8)


###########################
# 한글 이미지 출력
###########################


def create_korean_block_image(lines, font_size=BODY_FONT_SIZE, width=WIDTH_DOTS):
    """여러 줄을 하나의 흑백 이미지로 그립니다.

    9600bps 에서는 보내는 바이트 수가 곧 인쇄 시간입니다. 줄마다 이미지를
    따로 만들면 위아래 여백이 줄 수만큼 반복되어 전체의 절반 가까이가 빈
    흰 공간이 됩니다. 한 덩어리로 그려 여백을 한 번만 넣습니다.
    """
    font = load_font(font_size)

    # 용지 폭을 넘는 줄을 먼저 나눕니다. 여기서 걸러야 헤더, 시 본문, 푸터가
    # 모두 같은 규칙으로 처리됩니다. 나누지 않으면 오른쪽이 조용히 잘립니다.
    max_width = usable_width(width)
    wrapped = []
    for line in lines:
        wrapped.extend(wrap_line(line, font, max_width))
    lines = wrapped or [""]

    try:
        ascent, descent = font.getmetrics()
    except Exception:
        ascent, descent = font_size, int(font_size * 0.25)

    line_height = ascent + descent
    height = BLOCK_MARGIN * 2 + line_height * len(lines) + LINE_GAP * (len(lines) - 1)

    image = Image.new("RGB", (width, max(height, 8)), "white")
    draw = ImageDraw.Draw(image)

    y = BLOCK_MARGIN
    for line in lines:
        # 1픽셀씩 어긋나게 네 번 그려 굵기를 만듭니다.
        for dx in range(2):
            for dy in range(2):
                draw.text((TEXT_MARGIN + dx, y + dy), line, font=font, fill="black")
        y += line_height + LINE_GAP

    return image.convert("1")


def print_korean_lines(lines, font_size=BODY_FONT_SIZE):
    """여러 줄을 한 번의 라스터 전송으로 인쇄합니다."""
    if printer is None:
        print("프린터 없음: %s" % " / ".join(lines))
        return

    if not lines:
        return

    try:
        image = create_korean_block_image(lines, font_size=font_size)
        print_image(printer, image, PRINTER_BAUD)
    except Exception as exc:
        print("한글 출력 실패 (%s): %s" % (" / ".join(lines), exc))


def print_korean_text(text, font_size=BODY_FONT_SIZE):
    """한 줄짜리 편의 함수."""
    print_korean_lines([text], font_size=font_size)


###########################
# 영수증 구성 요소
###########################


def print_separator():
    if printer is None:
        return
    try:
        printer.justify("C")
        printer.println()
        printer.println("`'. .'`'. .'`'. .'`'. .'`'. .'`")
        printer.println("   `     `     `     `     `   ")
        printer.println()
        printer.justify("L")
    except Exception as exc:
        print("구분선 출력 실패: %s" % exc)


def print_header():
    if printer is None:
        return
    try:
        now = datetime.now()
        printer.justify("C")
        # 날짜와 시각을 한 덩어리로 보내 전송량을 줄입니다.
        print_korean_lines([
            now.strftime("%Y년 %m월 %d일"),
            now.strftime("%H:%M"),
        ])
        printer.justify("L")
    except Exception as exc:
        print("헤더 출력 실패: %s" % exc)


def print_poem(poem):
    """첫 줄을 제목으로, 빈 줄로 나뉜 나머지를 연으로 인쇄합니다."""
    if printer is None:
        print("프린터 없음. 시를 인쇄하지 않습니다.")
        return

    lines = poem.strip().split("\n")
    if not lines:
        return

    printer.justify("L")

    title = lines[0].strip()
    if title:
        print_korean_text(title, font_size=TITLE_FONT_SIZE)
        printer.feed(1)

    stanzas = []
    current = []
    for line in lines[1:]:
        stripped = line.strip()
        if stripped:
            current.append(stripped)
        elif current:
            stanzas.append(current)
            current = []
    if current:
        stanzas.append(current)

    # 연 단위로 한 번에 보냅니다. 줄마다 보내면 여백이 줄 수만큼 반복됩니다.
    for index, stanza in enumerate(stanzas):
        print_korean_lines(stanza)
        if index < len(stanzas) - 1:
            printer.feed(1)


def print_footer():
    if printer is None:
        return
    try:
        printer.justify("C")
        print_korean_text("이 시는 AI가 작성했습니다")
        printer.println()
        printer.justify("L")
        # 손으로 뜯을 여백을 확보합니다.
        printer.feed(5)
    except Exception as exc:
        print("푸터 출력 실패: %s" % exc)


###########################
# 핵심 동작
###########################


def build_prompt(chars_per_line):
    return """%s

제공된 이미지를 기반으로 다음 형식으로 한국어 시를 작성하세요: %s

중요한 제약사항:
1. 첫 줄에 전체 주제를 관통하는 1-2단어 이내의 간결한 제목을 배치하세요
2. 제목 다음 줄을 비우고 본문을 시작하세요
3. 각 줄은 공백 포함 최대 %d글자를 넘지 않게 작성하세요. 공백은 반(1/2)글자로 계산합니다.
4. 전체적으로 3연 구조를 따르며, 각 연 사이에 빈 줄을 넣어 명확히 구분하세요
5. 이미지의 중앙에 보이는 주제에 집중하고, 제일 중요한 요소를 중심으로 시를 전개하세요

시는 이미지에서 보이는 세부 사항을 자연스럽게 하나의 주제로 통합해야 합니다.
이미지에 대한 참조는 미묘하면서도 명확해야 합니다.
어휘를 단순하게 유지하고 절제된 관점을 사용해야 합니다.
분위기, 대기, 사물, 색상 및 흥미로운 세부 사항에 집중하세요.

한국어 시만 응답하고 다른 것은 응답하지 마세요.""" % (
        system_prompt, poem_format, chars_per_line)


def take_photo_and_print_poem():
    global is_processing
    global SELECTED_FONT_PATH

    if is_processing:
        print("이미 처리 중입니다. 완료될 때까지 기다려 주세요.")
        return

    if not has_network():
        # 네트워크 없이는 시를 만들 수 없으므로 촬영하지 않고 빨강 점멸만 남깁니다.
        set_ready_state()
        return

    is_processing = True
    # 촬영과 시 생성 동안은 초록 점멸
    status_led.blink(COLOR_CAPTURE)
    print("사진 촬영 및 시 생성 시작")

    # 시작할 때 한 번만 고르면 재부팅 전까지 계속 같은 폰트로 나옵니다.
    # 찍을 때마다 다시 골라야 장마다 폰트가 달라집니다.
    SELECTED_FONT_PATH = get_random_korean_font()

    image_path = None
    try:
        os.makedirs(IMAGE_DIR, exist_ok=True)
        # 촬영본은 images/ 에 시각 순으로 쌓입니다.
        image_path = os.path.join(
            IMAGE_DIR, datetime.now().strftime("%Y%m%d_%H%M%S.jpg"))
        picam2.capture_file(image_path)
        print("촬영 완료: %s" % image_path)

        model = genai.GenerativeModel("models/gemini-2.5-flash")
        chars_per_line = calculate_chars_per_line()

        print("시 생성 중")
        response = model.generate_content(
            [build_prompt(chars_per_line), Image.open(image_path)])
        poem = response.text

        print("--------POEM BELOW-------")
        print(poem)
        print("-------------------------")

        # 인쇄 동안은 파랑 점멸
        status_led.blink(COLOR_PRINT)
        print_header()
        print_separator()
        print_poem(poem)
        print_separator()
        print_footer()

    except Exception as exc:
        print("처리 중 오류: %s" % exc)
        status_led.solid(COLOR_ERROR)
        time.sleep(2)
    finally:
        is_processing = False
        set_ready_state()
        print("처리 완료. 셔터 버튼 대기 중\n")


###########################
# 종료 처리
###########################


def handle_keyboard_interrupt(sig, frame):
    print("Ctrl+C 감지, 스크립트를 종료합니다")
    status_led.off()
    # 파이 전체가 내려가지 않도록 RPi 포럼에서 찾은 우회 방법
    os.kill(os.getpid(), signal.SIGUSR1)


signal.signal(signal.SIGINT, handle_keyboard_interrupt)


###########################
# 시작
###########################


def main():
    global SELECTED_FONT_PATH

    # 시작할 때 한 번 골라 폰트가 실제로 있는지 확인합니다.
    # 실제로 쓰는 폰트는 촬영할 때마다 다시 고릅니다.
    SELECTED_FONT_PATH = get_random_korean_font()
    print("한 줄 최대 글자수(이 폰트 기준): %d자" % calculate_chars_per_line())

    shutter_button.when_pressed = take_photo_and_print_poem

    # 부팅 직후에는 와이파이가 아직 안 붙었을 수 있어 잠시 기다립니다.
    wait_for_network()

    if set_ready_state():
        print("준비 완료. GPIO%d 셔터 버튼을 누르세요." % SHUTTER_PIN)
    else:
        print("와이파이 연결 후 셔터 버튼을 누르면 다시 확인합니다.")

    signal.pause()


if __name__ == "__main__":
    main()
