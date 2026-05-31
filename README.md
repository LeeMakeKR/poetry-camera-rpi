# 시 카메라 (Poetry Camera)
시를 인식해서 시로 표현하는 카메라입니다.

이 프로젝트는 https://github.com/bokito-studio/poetry-camera-rpi의 포크로 시작했습니다. 해당 프로젝트가 진행이 멈춰 진행이 되지 않아 프로젝트를 최신 패키지에 맞게 업데이트하고, 한글로 구현하는 것을 목표로 합니다.

## 필요한 하드웨어
- 라즈베리 파이 제로 2w
- 라즈베리 파이용 카메라
- 영수증 프린터
- 전원장치
- 스위치 등



## 파트 6. 전원 회로 만들기
[TODO] 이것을 정리하고 설명 단계 :)

<img width="1217" alt="image" src="https://github.com/carolynz/poetry-camera-rpi/assets/1395087/dca36686-fcfa-43ba-86f6-155bd1aab0e5">

## 파트 7: 이동 중에 WiFi 네트워크 변경
카메라가 작동하려면 WiFi가 필요합니다. `wpa_supplicant.conf`를 편집해서 항상 모바일 핫스팟을 하드코드할 수 있습니다. 즉시 새로운 WiFi 네트워크에 연결하고 싶다면, [이 간단한 튜토리얼](https://www.raspberrypi.com/tutorials/host-a-hotel-wifi-hotspot/)을 플러그 앤 플레이 코드와 함께 따르면 됩니다. (자동으로 튜토리얼의 Flask 앱과 우리 메인 카메라 코드를 두 개의 cron 작업으로 동시에 실행할 수 있습니다.)

위의 튜토리얼을 수행하려면 microUSB 포트에 연결된 두 번째 WiFi 어댑터가 필요합니다. 확실히 Linux/라즈베리 파이에서 작동하는 플러그 앤 플레이 WiFi 어댑터를 받으세요.

