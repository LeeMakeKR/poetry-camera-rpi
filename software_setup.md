# 소프트웨어 설정

이 코드는 Google Gemini 모델로 사진을 한국어 시로 바꾸고, [Adafruit 감열 프린터 라이브러리](https://github.com/adafruit/Python-Thermal-Printer)로 인쇄합니다.

설치 순서는 다음과 같습니다. **API 키를 넣기 전에는 자동 실행을 켜지 마세요.** 이유는 아래 "파트 5" 에 적었습니다.

1. 라즈베리파이 인터페이스 설정
2. 패키지 설치
3. 배선
4. API 키 입력
5. 와이파이 등록
6. 수동 실행으로 동작 확인
7. 자동 실행 등록

## 파트 1. 라즈베리파이 설정

```shell
sudo raspi-config
```

- **Serial Port** (프린터): `3 Interface Options` → `I6 Serial Port` → 시리얼 로그인 셸 `No` → 시리얼 하드웨어 `Yes`
- **Camera**: 최근 라즈베리파이 OS 는 `camera_auto_detect=1` 로 자동 인식되어 별도 설정이 필요 없습니다.

![raspi-config 설정 화면](pics/2026-06-04%20151615.png)

이어서 `/boot/firmware/config.txt` 끝에 다음 줄이 있어야 합니다.

```ini
enable_uart=1
dtoverlay=disable-bt
```

`disable-bt` 가 없으면 `/dev/serial0` 이 mini UART 로 잡혀 프린터 출력이 깨집니다. 자세한 내용은 `hardware_setup.md` 를 보세요. 추가 후에는 재부팅이 필요합니다.

## 파트 2. 저장소와 패키지 설치

```shell
cd ~
git clone https://github.com/LeeMakeKR/poetry-camera-rpi.git
cd poetry-camera-rpi
pip3 install -r requirements.txt --break-system-packages
```

라즈베리파이 OS(Bookworm 이후)는 시스템 파이썬을 보호하므로 `--break-system-packages` 가 필요합니다.

## 파트 3. 배선

핀 배치와 주의사항은 `hardware_setup.md` 에 정리되어 있습니다. 요약하면 다음과 같습니다.

| 부품 | 신호 | GPIO | 물리 핀 |
| --- | --- | --- | --- |
| 셔터 스위치 | 입력 | GPIO20 | 38 |
| WS2812 상태 LED | DATA IN | GPIO21 | 40 |
| 프린터 RX | Pi TX | GPIO14 | 8 |
| 프린터 TX | Pi RX | GPIO15 | 10 |

- 프린터 전원은 **반드시 별도 5V 2A 이상**을 쓰고 GND 만 파이와 공통으로 묶습니다.
- GPIO 는 3.3V 전용입니다. 5V 를 입력하면 핀이 손상됩니다.
- 케이블에 적힌 TX/RX 라벨이 실물과 반대인 경우가 있습니다. 인쇄가 안 되면 8번과 10번에 꽂은 두 선을 서로 바꿔 보세요.

배선 후 아래 순서로 확인하면 문제를 빨리 좁힐 수 있습니다.

```shell
python3 testcode/testUartLoopback.py    # 파이 UART 자체 점검
python3 testcode/testThermalPrint.py    # 프린터 텍스트 출력
python3 testcode/testCamera.py          # 카메라 촬영
sudo -E PYTHONPATH=/home/poetry/.local/lib/python3.13/site-packages \
  python3 testcode/testStatusLed.py     # 상태 LED 색 전환
```

## 파트 4. API 키 입력

**자동 실행을 켜기 전에 반드시 이 단계를 끝내세요.**

```shell
cd ~/poetry-camera-rpi
cp .env.example .env
nano .env
```

`.env` 에 발급받은 키를 한 줄로 넣습니다.

```text
GOOGLE_API_KEY=AIza로_시작하는_실제_키
```

```shell
chmod 600 .env
```

키 발급 방법과 `.gitignore` 동작은 `api_setup.md` 에 자세히 있습니다. `.env` 는 저장소에 올라가지 않습니다.

## 파트 5. 와이파이 등록

시 생성에는 인터넷이 필요합니다. 장소를 옮겨 다닌다면 갈 만한 곳의 와이파이를 미리 등록해 두세요.

```shell
cd ~/poetry-camera-rpi
cp wifi_networks.example.txt wifi_networks.txt
nano wifi_networks.txt
```

형식은 `이름,비밀번호,우선순위` 이고 우선순위 숫자가 클수록 먼저 시도합니다.

```text
내폰핫스팟,핫스팟비밀번호,20
집와이파이,비밀번호,10
작업실와이파이,비밀번호,5
```

등록:

```shell
sudo python3 python/wifi_apply.py
```

이 스크립트는 `nmcli` 로 NetworkManager 에 프로필을 만듭니다. 부팅할 때도 `poetry-camera.service` 가 자동으로 한 번 실행하므로, 파일만 고쳐 두면 다음 부팅부터 반영됩니다.

`wifi_networks.txt` 는 `.gitignore` 에 있어 저장소에 올라가지 않습니다.

### 처음 가는 장소에서 와이파이를 바꾸려면

**휴대폰 핫스팟을 가장 높은 우선순위로 등록해 두는 것이 핵심입니다.**

1. 휴대폰 핫스팟을 켭니다
2. 파이가 자동으로 붙습니다 (LED 가 빨강 점멸에서 초록으로 바뀜)
3. 같은 핫스팟에 노트북을 붙이고 SSH 로 접속합니다
4. `wifi_networks.txt` 에 그 장소의 와이파이를 추가하고 `sudo python3 python/wifi_apply.py` 를 실행합니다

파이를 AP 모드로 바꿔 웹페이지에서 설정하는 방식(comitup 등)도 있지만, 별도 데몬이 무선 장치를 계속 감시해야 해서 촬영 동작과 충돌할 여지가 있습니다. 핫스팟 방식이 더 단순하고 안정적입니다.

### 연결이 안 될 때

와이파이가 없으면 LED 가 **빨강 점멸**로 바뀌고 셔터 버튼을 눌러도 촬영하지 않습니다. 사진만 찍고 시를 못 만드는 상태를 피하기 위해서입니다.

부팅 직후에는 와이파이가 붙는 데 시간이 걸리므로 최대 60초를 기다립니다. 그 뒤에도 연결이 안 되면 빨강 점멸을 유지하고, 연결된 뒤 셔터 버튼을 누르면 다시 확인해 초록으로 돌아갑니다.

## 파트 6. 수동 실행으로 확인

자동 실행을 등록하기 전에 손으로 한 번 돌려 봅니다.

```shell
sudo -E PYTHONPATH=/home/poetry/.local/lib/python3.13/site-packages \
  python3 ~/poetry-camera-rpi/python/main.py
```

`main.py` 는 WS2812 때문에 **반드시 sudo** 로 실행해야 합니다. sudo 없이 실행하면 아무 메시지 없이 세그멘테이션 폴트로 죽습니다.

정상이라면 LED 가 다음 순서로 바뀝니다.

| 단계 | LED |
| --- | --- |
| 부팅/초기화 | 빨강 고정 |
| 촬영 대기 | 초록 고정 |
| 촬영·시 생성 | 초록 점멸 |
| 인쇄 중 | 파랑 점멸 |
| 완료 | 초록 고정 |
| 오류 | 빨강 2초 후 초록 복귀 |
| **와이파이 없음** | **빨강 점멸** |

초록 고정 상태에서 셔터 버튼을 눌러 시가 인쇄되면 여기까지 성공입니다. 촬영본은 `images/` 에 촬영 시각 이름으로 쌓입니다.

### 왜 API 키를 먼저 넣어야 하나

자동 실행을 먼저 켜면 부팅할 때마다 키 없는 `main.py` 가 실행됩니다. 카메라와 프린터를 이미 점유한 상태라 손으로 테스트를 돌릴 수 없고, 매번 서비스를 멈춰 가며 작업해야 합니다.

이를 막기 위해 서비스 파일에 다음 줄을 넣어 두었습니다.

```ini
ExecStartPre=/usr/bin/test -s /home/poetry/poetry-camera-rpi/.env
```

`.env` 가 없거나 비어 있으면 서비스가 시작되지 않고 실패로 끝납니다. 그래도 순서를 지키는 편이 낫습니다.

## 파트 7. 부팅 시 자동 실행 등록

수동 실행이 확인된 뒤에만 진행하세요.

```shell
sudo cp ~/poetry-camera-rpi/poetry-camera.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable poetry-camera.service
sudo systemctl start poetry-camera.service
```

상태와 로그 확인:

```shell
systemctl status poetry-camera.service
journalctl -u poetry-camera.service -f
```

재부팅해서 확인:

```shell
sudo reboot
```

부팅 후 LED 가 빨강에서 초록으로 바뀌면 정상입니다.

### 자동 실행 끄기

코드를 고치거나 테스트 스크립트를 돌릴 때는 서비스를 멈춰야 카메라와 프린터가 풀립니다.

```shell
sudo systemctl stop poetry-camera.service     # 지금만 멈춤
sudo systemctl disable poetry-camera.service  # 다음 부팅부터 안 뜸
```

다시 켤 때는 `enable` 과 `start` 를 다시 실행합니다.

### 코드를 고친 뒤

```shell
sudo systemctl restart poetry-camera.service
```

## 문제 해결

| 증상 | 원인과 조치 |
| --- | --- |
| 아무 메시지 없이 죽음 (종료 코드 139) | sudo 를 빠뜨렸습니다. WS2812 가 권한 없이 죽습니다 |
| `GOOGLE_API_KEY 를 찾지 못했습니다` | 파트 4 를 다시 하세요. 메시지 아래에 파일 경로가 함께 나옵니다 |
| 인쇄가 전혀 안 됨 | 프린터 전원만 껐다 켜서 설정 페이지가 나오는지 확인 → 나오면 배선(TX/RX, GND) 문제 |
| 인쇄물이 알 수 없는 문자로 도배됨 | 이미지 명령 호환 문제입니다. 프린터 전원을 끄세요. `hardware_setup.md` 의 "이미지 출력" 참고 |
| 서비스가 계속 재시작됨 | `journalctl -u poetry-camera.service` 로 원인 확인. `.env` 누락이면 `ExecStartPre` 에서 멈춥니다 |
| 카메라를 못 엶 | 서비스가 이미 점유 중일 수 있습니다. `sudo systemctl stop poetry-camera.service` 후 재시도 |
| LED 가 빨강으로 계속 점멸 | 와이파이 미연결입니다. 휴대폰 핫스팟을 켜거나 `nmcli device wifi list` 로 신호를 확인하세요 |
| 와이파이를 등록했는데 안 붙음 | `sudo python3 python/wifi_apply.py` 를 실행했는지, 이름과 비밀번호 앞뒤에 공백이 없는지 확인하세요 |

## 폰트

네이버 나눔글꼴 <https://hangeul.naver.com/font> 을 사용합니다. `fonts/` 아래 모든 `.ttf` / `.otf` 를 재귀적으로 찾아 실행할 때마다 하나를 무작위로 고릅니다.
