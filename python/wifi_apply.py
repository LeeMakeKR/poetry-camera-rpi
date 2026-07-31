#!/usr/bin/env python3
"""wifi_networks.txt 를 읽어 NetworkManager 에 와이파이 프로필을 등록/갱신합니다.

부팅 시 main.py 보다 먼저 실행되도록 poetry-camera.service 의 ExecStartPre 에
등록되어 있습니다. 손으로 돌릴 때는 root 권한이 필요합니다.

  sudo python3 python/wifi_apply.py

wifi_networks.txt 형식 (저장소 루트에 둡니다):
  와이파이이름,비밀번호,우선순위(선택)

우선순위 숫자가 클수록 먼저 시도합니다. 여러 장소를 다닌다면 휴대폰 핫스팟을
가장 높은 우선순위로 넣어 두면, 모르는 장소에서도 핫스팟만 켜면 접속됩니다.
"""

import os
import subprocess
import sys
from pathlib import Path

# 이 파일은 python/ 안에 있고 설정 파일은 저장소 루트에 둡니다.
BASE_DIR = Path(__file__).resolve().parent.parent
NETWORKS_FILE = BASE_DIR / "wifi_networks.txt"
EXAMPLE_FILE = BASE_DIR / "wifi_networks.example.txt"


def load_networks():
    if not NETWORKS_FILE.exists():
        print("%s 가 없어 와이파이 설정을 건너뜁니다." % NETWORKS_FILE.name)
        print("  cp %s %s 후 편집하세요." % (EXAMPLE_FILE, NETWORKS_FILE))
        return []

    networks = []
    for line in NETWORKS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 2:
            print("형식 오류로 건너뜀: %s" % line)
            continue

        ssid, password = parts[0], parts[1]
        priority = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
        networks.append((ssid, password, priority))

    return networks


def existing_connections():
    result = subprocess.run(
        ["nmcli", "-t", "-f", "NAME", "connection", "show"],
        capture_output=True, text=True, check=True,
    )
    return set(result.stdout.splitlines())


def apply_network(ssid, password, priority, known):
    if ssid in known:
        cmd = [
            "nmcli", "connection", "modify", ssid,
            "wifi-sec.psk", password,
            "connection.autoconnect", "yes",
            "connection.autoconnect-priority", str(priority),
        ]
    else:
        cmd = [
            "nmcli", "connection", "add", "type", "wifi",
            "con-name", ssid, "ifname", "wlan0", "ssid", ssid,
            "wifi-sec.key-mgmt", "wpa-psk", "wifi-sec.psk", password,
            "connection.autoconnect", "yes",
            "connection.autoconnect-priority", str(priority),
        ]

    subprocess.run(cmd, check=True, capture_output=True, text=True)
    print("와이파이 프로필 반영: %s (우선순위 %d)" % (ssid, priority))


def main():
    if os.geteuid() != 0:
        sys.exit("root 권한이 필요합니다: sudo python3 wifi_apply.py")

    networks = load_networks()
    if not networks:
        return

    known = existing_connections()
    for ssid, password, priority in networks:
        try:
            apply_network(ssid, password, priority, known)
        except subprocess.CalledProcessError as exc:
            print("%s 설정 실패: %s" % (ssid, exc.stderr.strip()))


if __name__ == "__main__":
    main()
