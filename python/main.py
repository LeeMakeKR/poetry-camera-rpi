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
import re
import signal
import socket
import sys
import threading
import time
from datetime import datetime

import google.generativeai as genai
from dotenv import load_dotenv
from google.api_core import exceptions as google_exceptions
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
COLOR_RETRY = (48, 32, 0)  # 노랑. 요청 한도에 걸려 기다리는 중
COLOR_ERROR = (64, 0, 0)

# 요청 한도(429)에 걸렸을 때 다시 시도하기까지의 간격입니다.
# 분당 한도는 대개 첫 대기에서 풀립니다.
RETRY_DELAYS = (5, 15, 45)
# 서버가 알려 준 대기 시간이 이보다 길면 기다리지 않고 포기합니다.
# 셔터를 누른 사람을 몇 분씩 세워 둘 수는 없습니다.
MAX_RETRY_WAIT = 60

# 한 번의 시 생성 요청을 기다릴 최대 시간(초).
# 이 값이 없으면 응답이 오지 않을 때 영원히 블록됩니다. 셔터 콜백은
# gpiozero 스레드 하나로 돌아가므로, 여기서 굳으면 버튼이 아예 죽습니다.
# 초록 점멸인 채로 멈춰 있던 원인이 이것입니다.
REQUEST_TIMEOUT = 60

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

# 촬영할 때마다 이 중 하나를 무작위로 고릅니다. 폰트와 같은 방식입니다.
# line_rule 의 {min}, {max} 는 그때의 폰트 크기로 계산한 글자 수로 채워집니다.
# 형식마다 줄 길이 규칙이 다릅니다. 산문시는 줄을 나누지 않고 wrap_line() 에 맡깁니다.
POEM_FORMS = [
    {
        "name": "자유시",
        "structure": "전체 8-12줄 내외의 자유시로 쓰세요."
                     " 3개의 연으로 나누고 연 사이에 빈 줄을 넣으세요.",
        "line_rule": "각 줄은 공백 포함 {min}~{max}글자로 쓰세요.",
    },
    {
        "name": "시조",
        "structure": "초장, 중장, 종장 세 장으로 이루어진 시조로 쓰세요."
                     " 각 장을 하나의 연으로 두고 연 사이에 빈 줄을 넣으세요."
                     " 종장의 첫 마디는 세 글자로 시작하는 시조의 규칙을 지키세요.",
        "line_rule": "각 장은 두 줄로 나누고, 각 줄은 공백 포함 {min}~{max}글자로 쓰세요.",
    },
#    {
#        "name": "산문시",
#        "structure": "행을 나누지 않고 이어지는 문장으로 쓰는 산문시로 쓰세요."
#                     " 두세 개의 짧은 문단으로 나누고 문단 사이에 빈 줄을 넣으세요.",
#        "line_rule": "문단 안에서는 줄을 나누지 말고 문장을 이어서 쓰세요."
#                     " 문단마다 두세 문장이면 충분합니다.",
#    },
    {
        "name": "민요풍 7·5조",
        "structure": "김소월의 시처럼 7자와 5자가 번갈아 나오는 7·5조 가락으로 쓰세요."
                     " 3개의 연으로 나누고 각 연은 4줄, 연 사이에 빈 줄을 넣으세요.",
        "line_rule": "가락을 지키는 것이 먼저입니다."
                     " 한 줄이 공백 포함 {max}글자를 넘지 않게만 하세요.",
    },
    {
        "name": "단시",
        "structure": "군더더기를 모두 덜어낸 아주 짧은 시로 쓰세요."
                     " 연을 나누지 말고 4줄 안에 끝내세요.",
        "line_rule": "각 줄은 공백 포함 {min}~{max}글자로 쓰세요.",
    },
    {
        "name": "절구풍 4행시",
        "structure": "한시의 절구처럼 네 줄로 기승전결을 이루게 쓰세요."
                     " 첫 줄에서 장면을 열고, 둘째 줄에서 이어받고,"
                     " 셋째 줄에서 방향을 틀고, 넷째 줄에서 거두세요."
                     " 연을 나누지 말고 네 줄로 끝내세요.",
        "line_rule": "네 줄의 길이를 서로 비슷하게 맞추고,"
                     " 각 줄은 공백 포함 {min}~{max}글자로 쓰세요.",
    },
    {
        "name": "하이쿠풍 3행시",
        "structure": "세 줄로 끝나는 아주 짧은 시로 쓰세요."
                     " 계절이나 날씨의 기척을 한 번 넣고, 순간 하나만 붙잡으세요."
                     " 설명하거나 감상을 말하지 말고 본 것만 놓아두세요."
                     " 연을 나누지 말고 세 줄로 끝내세요.",
        # 음수율이 짧아 {min} 하한을 강요하면 가락이 깨집니다. 상한만 둡니다.
        "line_rule": "첫 줄과 셋째 줄은 짧게, 가운데 줄은 그보다 길게 쓰세요."
                     " 한 줄이 공백 포함 {max}글자를 넘지 않게만 하세요.",
    },
]


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


def calculate_line_range(font_size=BODY_FONT_SIZE, width=WIDTH_DOTS):
    """폰트 크기에 맞는 한 줄 글자 수의 최소와 최대.

    최대만 알려 주면 모델이 훨씬 짧게 써서 오른쪽이 30~50% 비어 버립니다.
    채워야 할 하한을 함께 줘야 종이 폭을 제대로 씁니다.
    """
    maximum = calculate_chars_per_line(font_size, width)
    return max(int(maximum * 0.8), 6), maximum


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


# 프린터 기본 폰트는 한 줄에 32칸입니다. 점선 한 줄이면 뜯을 자리가 분명해집니다.
# 프린터 내장 문자만 쓰므로 아스키로 둡니다. 한글이나 가위 기호는 여기서 깨집니다.
SEPARATOR_LINE = "- " * 16


def print_separator():
    if printer is None:
        return
    try:
        printer.justify("C")
        printer.println()
        printer.println(SEPARATOR_LINE)
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


def build_prompt(form, min_chars, max_chars):
    line_rule = form["line_rule"].format(min=min_chars, max=max_chars)

    return """%s

제공된 이미지를 기반으로 한국어 시를 작성하세요. 형식은 %s입니다.

형식 규칙:
%s

중요한 제약사항:
1. 첫 줄에 전체 주제를 관통하는 1-2단어 이내의 간결한 제목을 배치하세요
2. 제목 다음 줄을 비우고 본문을 시작하세요
3. %s
4. 좁은 영수증에 인쇄되므로, 짧은 줄만 이어지면 오른쪽이 휑하게 빕니다.
   줄을 정해진 길이에 가깝게 채우되, 시의 형식에 맞는 것이 매우 중요합니다. 
5. 이미지의 중앙에 보이는 주제에 집중하고, 제일 중요한 요소를 중심으로 시를 전개하세요

시는 이미지에서 보이는 세부 사항을 자연스럽게 하나의 주제로 통합해야 합니다.
이미지에 대한 참조는 미묘하면서도 명확해야 합니다.
어휘를 단순하게 유지하고 절제된 관점을 사용해야 합니다.
분위기, 대기, 사물, 색상 및 흥미로운 세부 사항에 집중하세요.

한국어 시만 응답하고 다른 것은 응답하지 마세요.""" % (
        system_prompt, form["name"], form["structure"], line_rule)


# 429 응답에 들어 있는 대기 시간. 형식이 두 가지라 둘 다 받습니다.
#   retry_delay { seconds: 26 }   /   "retryDelay": "26s"
RETRY_DELAY_PATTERN = re.compile(r"retry_?delay\D{0,30}?(\d+)", re.IGNORECASE)


def parse_retry_delay(text):
    """429 가 알려 준 대기 시간(초). 없거나 너무 길면 None."""
    match = RETRY_DELAY_PATTERN.search(text)
    if not match:
        return None

    seconds = int(match.group(1))
    return seconds if 0 < seconds <= MAX_RETRY_WAIT else None


def is_daily_quota(text):
    """일일 한도인지. 분당 한도와 달리 기다려도 오늘 안에는 풀리지 않습니다."""
    lowered = text.lower()
    return "perday" in lowered or "per day" in lowered


def is_spend_cap(text):
    """AI Studio 의 월 지출 상한에 걸렸는지.

    요청 수 한도가 아니라 금액 한도라 429 로 오지만 성격이 다릅니다.
    사람이 상한을 올려 주기 전에는 몇 초를 기다리든 그대로 실패합니다.
    """
    lowered = text.lower()
    return "spending cap" in lowered or "spend cap" in lowered


def generate_poem(model, parts):
    """시를 생성합니다. 요청 한도에 걸리면 기다렸다 다시 시도합니다.

    분당 한도는 잠깐 기다리면 풀리지만 일일 한도는 다음날까지 풀리지 않습니다.
    구분하지 않고 재시도하면 될 일이 아닌데 1분을 버리고 같은 오류를 봅니다.
    """
    for attempt in range(len(RETRY_DELAYS) + 1):
        try:
            return model.generate_content(
                parts, request_options={"timeout": REQUEST_TIMEOUT})
        except google_exceptions.ResourceExhausted as exc:
            text = str(exc)

            # 사람이 손대야 풀리는 것들은 기다리지 않고 바로 포기합니다.
            if is_spend_cap(text):
                print("월 지출 상한에 걸렸습니다. 기다려도 풀리지 않습니다.")
                print("  상한 조정 : https://ai.studio/spend")
                raise

            if is_daily_quota(text):
                print("일일 요청 한도를 다 썼습니다. 오늘은 재시도해도 풀리지 않습니다.")
                print("  한도 확인 : https://aistudio.google.com/apikey")
                raise

            if attempt == len(RETRY_DELAYS):
                print("요청 한도가 %d번 재시도 뒤에도 풀리지 않았습니다."
                      % len(RETRY_DELAYS))
                raise

            # 서버가 알려 준 시간이 있으면 그쪽을 따릅니다. 우리 추측보다 정확합니다.
            wait = parse_retry_delay(text) or RETRY_DELAYS[attempt]
            print("분당 요청 한도 초과. %d초 후 다시 시도합니다 (%d/%d)"
                  % (wait, attempt + 1, len(RETRY_DELAYS)))

            status_led.blink(COLOR_RETRY)
            time.sleep(wait)
            status_led.blink(COLOR_CAPTURE)


def describe_error(exc):
    """오류를 종이에 적을 원인과 해결 방법으로 바꿉니다.

    LED 색만으로는 와이파이가 끊긴 건지 API 키가 틀린 건지 알 수 없어,
    파이에 SSH 로 들어가야만 이유를 알 수 있었습니다.

    문구가 영어인 이유는 프린터 내장 폰트가 PC936(중국어)이라 한글이 아예
    찍히지 않기 때문입니다. 한글을 내려면 폰트로 이미지를 그려야 하는데,
    폰트나 렌더링이 고장 난 경우에도 오류만은 나와야 해서 내장 폰트를 씁니다.
    한 줄에 32칸이므로 문구를 그 안에 맞춥니다.
    """
    text = str(exc)

    if isinstance(exc, google_exceptions.ResourceExhausted):
        if is_spend_cap(text):
            return "SPEND CAP REACHED", "RAISE IT AT ai.studio/spend"
        if is_daily_quota(text):
            return "DAILY LIMIT REACHED", "TRY AGAIN TOMORROW"
        return "TOO MANY REQUESTS", "WAIT A MINUTE AND RETRY"

    if isinstance(exc, (google_exceptions.Unauthenticated,
                        google_exceptions.PermissionDenied)):
        return "API KEY REJECTED", "CHECK GOOGLE_API_KEY IN .env"

    if isinstance(exc, (google_exceptions.ServiceUnavailable,
                        google_exceptions.DeadlineExceeded)):
        return "SERVER NOT RESPONDING", "TRY AGAIN LATER"

    if isinstance(exc, OSError):
        return "NO INTERNET", "CHECK WIFI"

    # 여기까지 오면 예상 못 한 오류입니다. 종류 이름이라도 남겨야
    # 나중에 로그를 볼 때 어디를 봐야 할지 알 수 있습니다.
    return "UNEXPECTED ERROR", type(exc).__name__[:32]


def print_error_receipt(cause, remedy):
    """오류 원인을 종이에 인쇄합니다. 프린터가 죽었으면 조용히 넘어갑니다.

    폰트도 라스터 변환도 거치지 않고 내장 폰트로만 찍습니다. 그래야
    폰트가 없거나 이미지 출력이 깨진 상황에서도 이유가 종이에 남습니다.
    """
    if printer is None:
        return

    try:
        printer.justify("L")
        printer.println(SEPARATOR_LINE)
        printer.println("POEM FAILED")
        printer.println(cause)
        printer.println(remedy)
        printer.println(datetime.now().strftime("%Y-%m-%d %H:%M"))
        printer.println(SEPARATOR_LINE)
        printer.feed(3)
    except Exception as exc:
        # 오류를 알리다 또 실패해도 원래 오류 처리를 막으면 안 됩니다.
        print("오류 안내 출력 실패: %s" % exc)


def take_photo_and_print_poem():
    global is_processing
    global SELECTED_FONT_PATH

    if is_processing:
        print("이미 처리 중입니다. 완료될 때까지 기다려 주세요.")
        return

    if not has_network():
        # 네트워크 없이는 시를 만들 수 없으므로 촬영하지 않습니다.
        # 빨강 점멸만으로는 이유를 알 수 없어 종이에도 남깁니다.
        print_error_receipt("NO INTERNET", "CHECK WIFI")
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
        # 폰트를 방금 골랐으므로 줄 길이도 그 폰트 기준으로 다시 계산합니다.
        min_chars, max_chars = calculate_line_range()
        form = random.choice(POEM_FORMS)
        print("시 형식: %s / 한 줄 %d~%d자" % (form["name"], min_chars, max_chars))

        print("시 생성 중 (최대 %d초 대기)" % REQUEST_TIMEOUT)
        # with 로 닫아 줍니다. 열어 두면 촬영할 때마다 파일 핸들이 쌓입니다.
        with Image.open(image_path) as photo:
            response = generate_poem(
                model, [build_prompt(form, min_chars, max_chars), photo])
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
        cause, remedy = describe_error(exc)
        print_error_receipt(cause, remedy)
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
