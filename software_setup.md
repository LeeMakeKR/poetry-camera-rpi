## 소프트웨어

# 라즈베리 파이 이미지 설치

# ssh 접속



이 코드는 현재 Google의 Gemini 모델을 사용해서 이미지를 시로 변환합니다. 또한 [Adafruit의 열감지식 프린터 Python 라이브러리](https://github.com/adafruit/Python-Thermal-Printer)의 프린터 드라이버를 사용합니다.

[Google AI Studio 계정 & Gemini API 키](https://aistudio.google.com/)를 받아야 합니다. 특정 한도 내에서 무료로 이용할 수 있습니다.

현재 파이에서 실행 중인 `main.py` 스크립트:
- 셔터 버튼을 클릭할 때 사진을 찍습니다
- 사진을 Gemini 모델에 보내서 사진에 캡션을 달도록 합니다
- 캡션을 받으면, Gemini 모델에 캡션을 시로 변환하도록 요청합니다
- 시를 받으면, 열감지식 영수증 프린터에서 시를 인쇄합니다


# 모두 함께 모으기
다음 튜토리얼에서 개선했습니다:
- [라즈베리 파이와 열감지식 프린터를 사용한 인스턴트 카메라](https://learn.adafruit.com/instant-camera-using-raspberry-pi-and-thermal-printer)
- [라즈베리 파이와 CUPS를 사용한 네트워크 열감지식 프린터](https://learn.adafruit.com/networked-thermal-printer-using-cups-and-raspberry-pi)

### 파트 1. 라즈베리 파이 & 카메라가 작동하는지 확인
1. 라즈베리 파이를 카메라 모듈에 연결합니다.

2. 파이에 새로 설치한 라즈베리 파이 OS가 있는 SD 카드를 삽입합니다.

3. 파이를 미니 HDMI로 모니터에 연결합니다.

5. 전원을 연결합니다. 파이에 녹색 불이 보이고 모니터에 시작 화면이 표시되어야 합니다.

7. 파이가 켜지면 파이에서 터미널을 열어서 변경을 시작합니다.

8. 카메라 & 시리얼 입력에 대해 라즈베리 파이 하드웨어를 설정합니다:
```shell
sudo raspi-config
```

9. 다음 설정을 조정하고 싶을 것입니다:
    - 글래머: ON (최신 버전의 Raspbian OS에서 카메라 설정용)
    - 시리얼 포트: ON (영수증 프린터 입력에 액세스할 수 있습니다)
    - 시리얼 콘솔: OFF (이것이 무엇인지 모르겠습니다)

    필요에 따라 시스템을 재시작합니다.

[튜토리얼 TODO: 기본 카메라 테스트 스크립트 포함 & 원하는 동작 표시]

### 파트 2. 프린터가 작동하는지 확인
1. 시스템을 업데이트하고 요구 사항을 설치합니다. 이 모든 것이 필요한지 확실하지 않습니다. 나중에 이것을 다시 살펴보고 불필요한 것을 제거할 수 있습니다.
```shell
$ sudo apt-get update
$ sudo apt-get install git cups build-essential libcups2-dev libcupsimage2-dev python3-serial python-pil python-unidecode
```

2. Adafruit 열감지식 프린터를 작동시키기 위해 필요한 소프트웨어를 설치합니다.
```shell
$ cd
$ git clone https://github.com/adafruit/zj-58
$ cd zj-58
$ make
$ sudo ./install
```

3. Poetry Camera 소프트웨어가 포함된 이 저장소를 복제합니다:
```shell
$ cd
$ git clone https://github.com/carolynz/poetry-camera-rpi.git
```

4. 복제한 `poetry-camera-rpi` 디렉토리로 이동한 후, `requirements.txt` 파일을 참조하여 필요한 파이썬 패키지들을 설치합니다:
```shell
$ cd poetry-camera-rpi
$ pip install -r requirements.txt
```

5. 열감지식 프린터를 설정하고 전원과 파이에 연결합니다. [이 튜토리얼의 다이어그램 및 지침을 참조하세요.](https://learn.adafruit.com/networked-thermal-printer-using-cups-and-raspberry-pi/connect-and-configure-printer)
   작동하는지 테스트합니다. 프린터의 보드 레이트(예: `19200`)에 주의하세요. 나중에 이것을 사용할 것입니다.

6. *만약* 프린터의 보드 레이트가 `19200`과 다르다면, `main.py`를 열고 그 번호를 프린터의 보드 레이트로 바꾸세요:
```shell
# main.py:

# 프린터 인스턴스 만들기
printer = Adafruit_Thermal('/dev/serial0', 19200, timeout=5)
```

[TODO] 프린터가 작동하는지 테스트하는 설정 스크립트가 필요합니다

### 파트 3. AI 설정
1. Google AI Studio 계정을 설정하고 Gemini API 키를 생성합니다.

2. Poetry Camera 코드가 있는 디렉토리로 이동하고 `.env` 파일을 만듭니다. 이 파일은 Gemini API 키와 같은 민감한 세부 정보를 저장합니다:
```nano .env```

3. .env에 API 키를 추가합니다:
```GEMINI_API_KEY=pasteyourAPIkeyhere```

[TODO] gemini 테스트 스크립트 추가


### 파트 4. 엔드-투-엔드로 작동하게 하기
[TODO] 배선도 포함

1. 버튼을 연결합니다

2. Poetry Camera 스크립트를 실행합니다.
```shell
$ python main.py
```

3. 셔터 버튼이 켜져 있는지 확인합니다. 카메라가 사진을 찍을 준비가 되었음을 나타냅니다.

4. 셔터 버튼을 클릭하고 시가 인쇄될 때까지 기다립니다.

[TODO] 다양한 일반적인 오류 메시지의 문제 해결 지침

## 파트 5. 카메라가 켜질 때 Poetry Camera 코드 자동 실행

1. `cron` 작업을 설정해서 시작할 때 Python 스크립트를 실행합니다. 먼저 기본 편집기에서 `crontab` 파일을 열기:
```shell
$ crontab -e
```

2 그런 다음 다음 줄을 `crontab`에 추가해서 컴퓨터를 부팅할 때 스크립트를 실행합니다.
```shell
# 시작할 때 Poetry Camera 스크립트 실행
@reboot python /home/pi/poetry-camera-rpi/main.py >> /home/pi/poetry-camera-rpi/errors.txt 2>&1
```
`>> {...}errors.txt 2>&1`은 오류 메시지를 `errors.txt`에 쓰므로 디버깅할 수 있습니다. 일반적인 실패 모드는 파일을 찾을 수 없다는 것입니다. 모든 파일 경로가 절대 파일 경로이고 올바른 사용자 이름 및 디렉토리 이름이 있는지 확인하세요.

- 이것이 작동하도록 시스템을 재부팅합니다
```shell
sudo reboot
```
이제 카메라를 재부팅하고 LED 불이 켜질 때까지 기다리세요!
