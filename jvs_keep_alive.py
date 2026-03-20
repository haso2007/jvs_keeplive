#!/usr/bin/env python3
"""
JVS WebUI Keep-Alive Script

Usage:
    python jvs_keep_alive.py
    python jvs_keep_alive.py --setup
    python jvs_keep_alive.py --cookie "k1=v1; k2=v2"
    python jvs_keep_alive.py --interval 300
"""

import argparse
import json
import logging
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_FILE = SCRIPT_DIR / "jvs_keep_alive.json"
BASE_URL = "https://jvs.wuying.aliyun.com"
SERVER_ID = "ws-0bzwu4jwtufq53i4c"

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("jvs_keep_alive.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("jvs")


def parse_cookie_string(cookie_str):
    cookies = {}
    for item in cookie_str.split(";"):
        item = item.strip()
        if "=" in item:
            key, value = item.split("=", 1)
            cookies[key.strip()] = value.strip()
    return cookies


def load_config_file():
    if not CONFIG_FILE.exists():
        return None
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_config_file(interval=600):
    if CONFIG_FILE.exists():
        return
    save_config_file("", interval)


def save_config_file(cookies, interval):
    data = {
        "cookies": cookies,
        "interval": interval,
        "last_updated": datetime.now().isoformat(),
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class JVSKeepAlive:
    def __init__(self, cookie_str, interval=600):
        self.cookie_str = cookie_str
        self.interval = interval
        self.running = True
        self.success_count = 0
        self.fail_count = 0
        self.config_mtime = None
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,image/apng,*/*;q=0.8"
                ),
                "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8",
                "Referer": f"{BASE_URL}/",
            }
        )
        self.apply_cookie_string(cookie_str)
        if CONFIG_FILE.exists():
            self.config_mtime = CONFIG_FILE.stat().st_mtime

    def apply_cookie_string(self, cookie_str):
        self.cookie_str = cookie_str
        self.session.cookies.clear()
        cookies = parse_cookie_string(cookie_str)
        for key, value in cookies.items():
            self.session.cookies.set(key, value)
        logger.info(f"Loaded {len(cookies)} cookies")

    def reload_config_if_changed(self):
        if not CONFIG_FILE.exists():
            return
        current_mtime = CONFIG_FILE.stat().st_mtime
        if self.config_mtime is not None and current_mtime <= self.config_mtime:
            return
        self.config_mtime = current_mtime
        try:
            config = load_config_file()
            if not config:
                return
            new_cookie = (config.get("cookies") or "").strip()
            new_interval = config.get("interval", self.interval)
            if new_interval != self.interval:
                self.interval = int(new_interval)
                logger.info(f"Reloaded interval from config: {self.interval}s")
            if new_cookie and new_cookie != self.cookie_str:
                self.apply_cookie_string(new_cookie)
                logger.info("Reloaded new cookie from config file")
        except Exception as e:
            logger.warning(f"Failed to reload config: {e}")

    def heartbeat(self):
        url = f"{BASE_URL}/chat?currentWuyingServerId={SERVER_ID}"
        try:
            resp = self.session.get(url, timeout=30)

            if resp.cookies:
                self.session.cookies.update(resp.cookies)
                logger.info("Updated cookies from server response")

            if resp.status_code == 200:
                self.success_count += 1
                self.fail_count = 0
                logger.info(
                    f"[OK] Heartbeat #{self.success_count} - "
                    f"Status: {resp.status_code}, Size: {len(resp.text)} chars"
                )
                return True

            if resp.status_code in (301, 302):
                location = resp.headers.get("Location", "")
                self.fail_count += 1
                if "login" in location.lower():
                    logger.error(
                        f"[FAIL] Redirected to login page. "
                        f"Cookie expired. Failures: {self.fail_count}"
                    )
                else:
                    logger.warning(
                        f"[WARN] Redirected to {location}. Failures: {self.fail_count}"
                    )
                return False

            self.fail_count += 1
            logger.warning(
                f"[WARN] Status: {resp.status_code}. Failures: {self.fail_count}"
            )
            return False

        except requests.exceptions.Timeout:
            self.fail_count += 1
            logger.warning(f"[TIMEOUT] Failures: {self.fail_count}")
            return False
        except requests.exceptions.ConnectionError as e:
            self.fail_count += 1
            logger.warning(f"[CONN_ERR] {e}. Failures: {self.fail_count}")
            return False
        except Exception as e:
            self.fail_count += 1
            logger.error(f"[ERROR] {e}. Failures: {self.fail_count}")
            return False

    def save_current_cookies(self):
        cookie_parts = [f"{k}={v}" for k, v in self.session.cookies.items()]
        save_config_file("; ".join(cookie_parts), self.interval)
        if CONFIG_FILE.exists():
            self.config_mtime = CONFIG_FILE.stat().st_mtime

    def run(self):
        logger.info("=" * 55)
        logger.info("JVS WebUI Keep-Alive Started")
        logger.info(f"  Target: {BASE_URL}")
        logger.info(f"  Server: {SERVER_ID}")
        logger.info(f"  Interval: {self.interval}s")
        logger.info(f"  Config: {CONFIG_FILE}")
        logger.info("=" * 55)

        self.reload_config_if_changed()
        self.heartbeat()
        self.save_current_cookies()

        while self.running:
            try:
                time.sleep(self.interval)
            except KeyboardInterrupt:
                break

            if not self.running:
                break

            self.reload_config_if_changed()
            self.heartbeat()
            self.save_current_cookies()

            if self.fail_count >= 3:
                logger.error(
                    f"{self.fail_count} consecutive failures. "
                    f"Please update cookie in {CONFIG_FILE} and keep the script running."
                )
            if self.fail_count >= 10:
                logger.error("Too many failures, stopping.")
                break

        logger.info("=" * 55)
        logger.info("Keep-Alive Stopped")
        logger.info(f"  Total heartbeats: {self.success_count}")
        logger.info("=" * 55)

    def stop(self):
        self.running = False


def main():
    parser = argparse.ArgumentParser(description="JVS WebUI Keep-Alive")
    parser.add_argument("--setup", action="store_true", help="Interactive setup")
    parser.add_argument("--cookie", type=str, help="Cookie string")
    parser.add_argument(
        "--interval",
        type=int,
        default=600,
        help="Heartbeat interval in seconds (default: 600)",
    )
    args = parser.parse_args()

    if args.cookie:
        cookie = args.cookie.strip()
        interval = args.interval
    elif args.setup:
        print("\nJVS WebUI Keep-Alive Setup")
        print("=" * 40)
        print("Paste cookie from browser F12 > Network > any request > Headers > Cookie")
        cookie = input("\nCookie: ").strip()
        if not cookie:
            print("No cookie provided.")
            sys.exit(1)
        interval = args.interval
        save_config_file(cookie, interval)
        print(f"Config saved to {CONFIG_FILE}")
    else:
        ensure_config_file(args.interval)
        config = load_config_file()
        if not config or not (config.get("cookies") or "").strip():
            print("No cookie configured.")
            print(f"Edit: {CONFIG_FILE}")
            print(f"Or run: python {Path(__file__).name} --setup")
            sys.exit(1)
        cookie = config["cookies"].strip()
        interval = int(config.get("interval", args.interval))
        logger.info(f"Loaded config from {CONFIG_FILE}")

    keeper = JVSKeepAlive(cookie, interval=interval)

    def on_signal(signum, frame):
        keeper.stop()

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    keeper.run()


if __name__ == "__main__":
    main()
