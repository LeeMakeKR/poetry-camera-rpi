# 하드웨어 목록

- 라즈베리파이 제로 2w
- 라즈베리 파이용 카메라와 케이블
- 전원장치
- ttl 써멀 라벨 프린터
- 프린터 전용 5V 2A 이상 전원 (파이 전원과 별도)

## 핀 배치 요약

| 부품 | 신호 | GPIO | 물리 핀 |
| --- | --- | --- | --- |
| 스위치 | 입력 | GPIO20 | 38 |
| WS2812 | DATA IN | GPIO21 | 40 |
| 써멀 프린터 | Pi TX → 프린터 RX | GPIO14 (TXD) | 8 |
| 써멀 프린터 | Pi RX ← 프린터 TX | GPIO15 (RXD) | 10 |
| 써멀 프린터 | GND 공통 | GND | 6 또는 9 |

## GPIO 배선 권장안

현재 저장소에서 기본으로 사용 중인 핀을 피하고, 아직 사용하지 않는 핀으로 구성하는 것을 권장합니다.

- 스위치: GPIO20 (물리 핀 38)
  - 한쪽 단자를 GPIO20에 연결하고, 다른 쪽 단자를 GND에 연결합니다.
  - 코드에서 내부 풀업을 켜므로 외부 저항은 필요 없습니다. 안 누르면 3.3V(High), 누르면 0V(Low)입니다.
- WS2812: GPIO21 (물리 핀 40)
  - WS2812 DATA IN → GPIO21
  - WS2812 VCC → 5V
  - WS2812 GND → GND
  - 데이터선에는 330~470Ω 저항을 권장합니다.

## 써멀 프린터 (TTL 시리얼) 배선

프린터 케이블은 보통 데이터 3선(RX/TX/GND)과 전원 2선(VH/GND)으로 나뉩니다.

### 데이터 3선

- 프린터 **RX** → 파이 **GPIO14 / TXD** (물리 핀 8)
- 프린터 **TX** → 파이 **GPIO15 / RXD** (물리 핀 10)
- 프린터 **GND** → 파이 **GND** (물리 핀 6)

TX/RX는 서로 엇갈려(cross) 연결합니다. 같은 이름끼리 연결하면 통신이 전혀 되지 않습니다.

**케이블 라벨을 믿지 마세요.** 실제 검증 과정에서 케이블에 표기된 TX/RX가 실물과 반대였습니다. 인쇄가 안 되면 8번 핀과 10번 핀에 꽂은 두 선을 서로 바꿔 끼워보는 것이 가장 빠른 해결책입니다.

### 전원 2선

- 프린터 **VH(+)** → 별도 5V 2A 이상 전원의 (+)
- 프린터 **GND(-)** → 그 전원의 (-)
- 그 전원의 (-)를 파이 GND에도 함께 연결해 **GND를 공통**으로 만듭니다.

## 주의사항

1. **프린터 전원을 파이의 5V 핀에서 뽑지 마세요.** 인쇄 순간 1.5~2A를 당겨서 파이가 리부팅되거나 SD 카드가 손상됩니다. 반드시 별도 전원을 쓰고 GND만 공통으로 묶습니다.
2. **GPIO는 3.3V 전용입니다.** 5V를 입력하면 핀이 즉시 손상됩니다. 프린터 TX가 5V 로직인 모델이라면 파이 RXD로 들어가는 선에 분압 저항(예: 10kΩ + 20kΩ)을 넣으세요. 파이 TX(3.3V)는 프린터 RX가 그대로 인식하므로 변환이 필요 없습니다.
3. WS2812의 VCC는 5V가 맞지만, 스위치는 3.3V 전용입니다. 두 부품의 전압 기준이 다릅니다.

## 파이 UART 설정

`/boot/firmware/config.txt` 에 다음이 있어야 합니다.

```ini
enable_uart=1
dtoverlay=disable-bt
```

- `enable_uart=1` : 시리얼 포트 활성화
- `dtoverlay=disable-bt` : 블루투스를 끄고 안정적인 PL011 UART(`ttyAMA0`)를 `/dev/serial0` 에 연결

`disable-bt` 가 없으면 `/dev/serial0` 이 mini UART(`ttyS0`)로 잡힙니다. mini UART는 보레이트가 CPU 코어 클럭에 연동되어 클럭이 변할 때 글자가 깨집니다. 프린터처럼 지속적으로 데이터를 보내는 장치에는 권장하지 않습니다.

시리얼 콘솔은 꺼져 있어야 합니다. `/boot/firmware/cmdline.txt` 에 `console=serial0,115200` 이 있으면 지웁니다.

확인 명령:

```bash
ls -l /dev/serial0        # -> ttyAMA0 이면 정상
groups                    # -> dialout 포함 시 sudo 없이 접근 가능
```

## 검증된 프린터 설정

프린터에 전원을 넣으면 자체 설정을 인쇄합니다. 이 기기의 값은 다음과 같습니다.

| 항목 | 값 |
| --- | --- |
| 보레이트 | 9600 고정 (19200 이상은 전부 깨짐, 실측 확인) |
| 코드 방식 | codepage |
| 문자 타입 | U24 |
| 언어 | PC936 (중국어 GBK) |
| 한 줄 폭 | 32칸 (실측 확인) |
| heattime | 255 (80/120/180/255 비교 후 선택) |

한 줄 폭 32칸은 `main.py` 의 `wrap_text(poem, 32)` 설정과 일치하므로 코드 수정이 필요 없습니다.

heattime은 라이브러리 기본값이 120이지만 이 기기에서는 255가 가장 선명했습니다. `main.py` 에서 프린터 생성 직후 `printer.writeBytes(27, 55, 11, 255, 40)` 으로 지정합니다. 생성자에 `heattime=` 인자를 넘기면 pyserial 3.5에서 `TypeError` 가 납니다.

heattime 255는 발열 시간이 길어 인쇄가 느리고 순간 전류가 큽니다. 프린터 전원이 2A 이상이어야 합니다.

언어가 PC936이므로 **한글은 인쇄되지 않습니다.** 한글이 필요하면 텍스트를 이미지로 렌더링해 출력해야 하며, 이때 아래 "이미지 출력" 항목의 제약을 함께 따릅니다.

## 이미지 출력 (중요)

### `printImage()` 를 쓰면 안 됩니다

`Adafruit_Thermal.printImage()` 는 **DC2 `*` (18, 42)** 비트맵 명령을 사용합니다. 이 프린터는 이 명령을 인식하지 못하고, 뒤따르는 이미지 데이터 전체를 **문자로 해석해 인쇄**합니다. 384x288 이미지 3장을 시도했을 때 약 4만 바이트가 알 수 없는 문자로 쏟아져 나왔습니다.

프린터 언어가 **PC936 (중국어 GBK)** 인 계열은 DC2 `*` 대신 **`GS v 0` (29, 118, 48)** 라스터 명령을 씁니다. 이 기기에서 `GS v 0` 는 정상 동작을 확인했습니다.

멈추는 방법은 **프린터 전원을 끄는 것뿐**입니다. 파이에서 프로세스를 종료해도 이미 프린터 내부 버퍼로 넘어간 데이터는 계속 인쇄됩니다.

### `GS v 0` 사용법

```text
29 118 48 m xL xH yL yH  +  비트맵 데이터
  m  = 0 (일반 모드)
  xL, xH = 가로 바이트 수 (384도트 = 48바이트)
  yL, yH = 세로 도트 수
```

데이터는 1비트가 검정입니다. 가로는 **384도트 고정**이며, `printImage()` 는 초과분을 축소하지 않고 잘라내므로 보내기 전에 반드시 384픽셀 폭으로 리사이즈해야 합니다.

동작 확인용 최소 예제는 `testcode/testRasterProbe.py` 입니다. 384x32 (종이 약 5cm) 만 인쇄하므로 호환되지 않는 프린터에서 시도해도 피해가 작습니다. **새 프린터를 붙일 때는 항상 이 스크립트를 먼저 돌리세요.**

### 이미지 인쇄 속도

보레이트가 9600 고정이라 **보내는 도트 수가 곧 인쇄 시간**입니다. 한 행은 48바이트이고 9600bps 에서 55ms 가 걸립니다.

인쇄기 자체는 그보다 훨씬 빨라 항상 전송이 병목입니다. 따라서 전송 시간과 인쇄 시간을 **더해서 기다리면 안 됩니다**. `thermal_raster.print_raster()` 는 둘 중 큰 값만 기다립니다. 더하는 방식이었을 때는 시 한 장에 84초가 걸렸습니다.

빈 여백도 그대로 전송되므로 여백을 줄이는 것이 곧 속도 개선입니다. `main.py` 는 줄마다 이미지를 만들지 않고 연 단위로 묶어 한 번에 보냅니다. 줄마다 보내면 위아래 여백이 줄 수만큼 반복됩니다.

측정값 (8줄 시 + 헤더 + 푸터, 폰트 48):

| 방식 | 전송 행수 | 소요 |
| --- | --- | --- |
| 줄 단위 + 대기 중복 | 990 | 84초 |
| 연 단위 + 대기 개선 | 666 | 37초 |

더 줄이려면 폰트 크기를 낮춥니다. 48에서 36으로 내리면 약 25% 더 빨라지지만 글자가 작아집니다.

흑백 변환은 `testcode/testCameraPrint.py` 에서 3가지를 비교했고, **오차확산 디더링(1 DITHER)** 이 실물에서 가장 보기 좋아 기본값으로 두었습니다.

### `writeBytes()` 로 대량 데이터를 보내면 안 됩니다

`Adafruit_Thermal.writeBytes()` 는 인자 N개를 받으면 **바이트마다 N배씩** 대기해 총 대기 시간이 N²에 비례합니다. 48바이트짜리 한 행에 2.6초가 걸려 32행이면 85초입니다.

이미지처럼 큰 데이터는 부모 클래스의 `Serial.write()` 로 한 번에 보내고 대기 시간을 직접 계산합니다.

```python
from serial import Serial

printer.timeoutWait()
Serial.write(printer, payload)
Serial.flush(printer)
time.sleep(len(payload) * 11.0 / baud + height * printer.dotPrintTime)
```

### 알려진 라이브러리 버그

| 위치 | 문제 | 우회 방법 |
| --- | --- | --- |
| `Adafruit_Thermal.py` `printImage()` | DC2 `*` 명령이 이 프린터에서 미지원 | `GS v 0` 로 직접 전송 |
| `Adafruit_Thermal.py` `writeBytes()` | 대기 시간이 N²에 비례 | `Serial.write()` 직접 호출 |
| `Adafruit_Thermal.py` `__init__()` | `firmware` / `heattime` kwargs 를 pyserial 로 그대로 넘겨 pyserial 3.5 에서 `TypeError` | 생성 후 `writeBytes(27, 55, 11, heattime, 40)` 로 지정 |

## 문제 해결

인쇄가 전혀 안 될 때 아래 순서로 좁히면 원인이 빠르게 나옵니다.

1. 프린터 전원만 껐다 켜기 — 설정 페이지가 인쇄되면 전원/모터/용지는 정상
2. `python3 testcode/testUartLoopback.py` — 핀 8과 핀 10을 점퍼선으로 직결한 뒤 실행. PASS면 파이 UART는 정상
3. 위 둘이 모두 정상인데 인쇄가 안 되면 남는 원인은 TX/RX 반전 또는 GND 공통 누락뿐입니다

## 폴더 구조

```text
python/          실행 코드 (main.py, thermal_raster.py, Adafruit_Thermal.py)
fonts/           한글 폰트 (nanum, nanum_handwriting)
images/          촬영본 보관. 파일명은 촬영 시각 (20260731_145213.jpg)
testcode/        하드웨어 검증 스크립트
testcode/reference/  정리 전 원본 코드 스냅샷 (실행용 아님)
```

`python/main.py` 는 자신의 상위 폴더를 저장소 루트로 보고 `fonts/` 와 `images/` 를 찾습니다. 폴더를 옮기면 이 관계가 유지되는지 확인하세요.

## 실행

**반드시 sudo 로 실행합니다.**

```bash
sudo -E PYTHONPATH=/home/poetry/.local/lib/python3.13/site-packages \
  python3 ~/poetry-camera-rpi/python/main.py
```

`main.py` 를 임포트하는 테스트 스크립트(`testKoreanPrint.py`, `testStatusLed.py`)도 마찬가지로 sudo 가 필요합니다.

### sudo 가 필수인 이유

WS2812 를 구동하는 `rpi_ws281x` 는 `/dev/mem` 에 접근합니다. 권한이 없으면 파이썬 예외를 던지는 대신 **프로세스를 세그멘테이션 폴트로 죽입니다.**

```text
Failed to create mailbox device
: Operation not permitted
Segmentation fault        (종료 코드 139)
```

파이썬 `try/except` 로는 막을 수 없습니다. 실행 중 아무 메시지 없이 죽는다면 sudo 를 빠뜨린 것입니다.

프린터와 카메라 자체는 sudo 없이도 동작하므로, LED 를 쓰지 않는 테스트(`testThermalPrint.py`, `testCamera.py` 등)는 일반 권한으로 실행해도 됩니다.

`PYTHONPATH` 를 함께 넘기는 이유는 패키지가 `~/.local` 에 설치되어 있어 root 환경에서 보이지 않기 때문입니다.

`.env` 파일에 `GOOGLE_API_KEY` 가 있어야 시가 생성됩니다. 설정 방법은 `api_setup.md` 를 보세요.

## 참고

- 실제 사용 시에는 코드에서 해당 GPIO를 참조하도록 함께 맞춰야 합니다.
- 테스트 스크립트는 `testcode/` 아래에 있습니다.
  - `testThermalPrint.py` : 기본 출력 확인
  - `testThermal.py` : 보레이트/농도/스타일 전체 진단
  - `testUartLoopback.py` : 파이 UART 자체 점검
  - `testKoreanPrint.py` : API 키 없이 한글 시 인쇄 경로만 확인
  - `testCamera.py`, `testCameraPrint.py` : 촬영 및 사진 인쇄
