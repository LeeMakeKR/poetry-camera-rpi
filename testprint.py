#!/usr/bin/python3
"""Simple thermal printer self-test script."""

import argparse
import sys
from datetime import datetime

from Adafruit_Thermal import Adafruit_Thermal


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Print a simple test page.")
    parser.add_argument("--port", default="/dev/serial0", help="Serial device path")
    parser.add_argument("--baud", type=int, default=9600, help="Serial baud rate")
    parser.add_argument("--timeout", type=float, default=5.0, help="Serial timeout in seconds")
    parser.add_argument(
        "--message",
        default="Thermal printer test OK.",
        help="Message body to print",
    )
    parser.add_argument(
        "--feed-lines",
        type=int,
        default=4,
        help="Blank lines to feed after printing",
    )
    return parser.parse_args()


def print_test_page(printer: Adafruit_Thermal, message: str, feed_lines: int) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    printer.wake()
    printer.setDefault()

    printer.justify("C")
    printer.boldOn()
    printer.println("POETRY CAMERA")
    printer.boldOff()
    printer.println("PRINTER TEST")
    printer.println(timestamp)

    printer.justify("L")
    printer.println("------------------------------")
    printer.println(message)
    printer.println("------------------------------")
    printer.feed(max(feed_lines, 1))


def main() -> int:
    args = parse_args()

    try:
        printer = Adafruit_Thermal(args.port, args.baud, timeout=args.timeout)
    except Exception as exc:
        print(f"Failed to open printer: {exc}", file=sys.stderr)
        return 1

    try:
        print_test_page(printer, args.message, args.feed_lines)
        print("Test print sent successfully.")
        return 0
    except Exception as exc:
        print(f"Printing failed: {exc}", file=sys.stderr)
        return 1
    finally:
        try:
            printer.sleep()
        finally:
            printer.close()


if __name__ == "__main__":
    raise SystemExit(main())
