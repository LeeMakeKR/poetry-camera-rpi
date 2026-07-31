# API 키 설정

시를 생성하려면 Google Gemini API 키가 필요합니다. 키는 저장소 루트의 `.env` 파일 한 곳에서만 읽습니다.

## 1. 키 발급

<https://aistudio.google.com/apikey> 에서 발급합니다. 무료 등급으로도 이 프로젝트는 충분히 돌아갑니다.

## 2. .env 파일 만들기

라즈베리파이에서 저장소 루트로 이동한 뒤 템플릿을 복사합니다.

```bash
cd ~/poetry-camera-rpi
cp .env.example .env
nano .env
```

`.env` 의 내용은 다음 한 줄이면 됩니다. 따옴표나 공백 없이 붙여 씁니다.

```text
GOOGLE_API_KEY=AIza로_시작하는_실제_키
```

키를 남이 못 읽게 권한도 좁혀 둡니다.

```bash
chmod 600 .env
```

## 3. 확인

```bash
sudo -E PYTHONPATH=/home/poetry/.local/lib/python3.13/site-packages \
  python3 ~/poetry-camera-rpi/python/main.py
```

키를 제대로 읽으면 `GOOGLE_API_KEY 를 찾지 못했습니다` 메시지가 나오지 않습니다. 메시지가 보이면 그 아래에 파일 위치와 해결 방법이 함께 출력됩니다.

`main.py` 는 WS2812 때문에 **반드시 sudo 로 실행**해야 합니다. 자세한 이유는 `hardware_setup.md` 의 "실행" 항목에 있습니다.

## 키가 저장소에 올라가지 않는 이유

`.gitignore` 에 다음이 들어 있습니다.

```text
.env
.env.*
!.env.example
```

`.env` 와 `.env.local` 같은 변형은 모두 제외되고, 키가 없는 템플릿 `.env.example` 만 저장소에 남습니다.

`.env.example` 에는 **절대 실제 키를 적지 마세요.** 이 파일은 커밋됩니다.

## 키가 이미 커밋된 경우

한 번 커밋된 키는 파일을 지워도 git 이력에 남습니다. 그때는 파일을 지우는 것으로 끝내지 말고 **발급처에서 해당 키를 폐기하고 새로 발급**하세요. 그게 가장 확실합니다.

## 참고

- 코드에서 키를 읽는 위치는 `python/main.py` 의 `ENV_PATH` 입니다.
- `.env` 는 `python/` 이 아니라 **저장소 루트**에 둡니다. 실행 위치가 달라져도 같은 파일을 보도록 경로를 고정해 두었습니다.
