#!/usr/bin/env python3
"""
JVS WebUI Keep-Alive Script (Playwright)

Uses a headless Chromium browser to keep the JVS chat page alive,
so that frontend JS can maintain WebSocket connections and refresh tokens.

Usage:
    python jvs_keep_alive.py
    python jvs_keep_alive.py --interval 300
    python jvs_keep_alive.py --headed
"""

import argparse
import asyncio
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def ensure_playwright():
    """Auto-install playwright and chromium if missing."""
    # Check Python version: playwright requires 3.9+
    if sys.version_info < (3, 9):
        print(f"Error: Python {sys.version_info.major}.{sys.version_info.minor} detected.")
        print("Playwright requires Python 3.9 or higher.")
        print("")
        print("Options:")
        print("  1. Install Python 3.9+:  apt install python3.9  (or use pyenv)")
        print("  2. Use Docker:  docker run -it python:3.11 bash")
        sys.exit(1)

    try:
        import playwright  # noqa: F401
    except ImportError:
        print("playwright not found, installing...")
        # Try multiple pip install methods
        pip_cmds = [
            [sys.executable, "-m", "pip", "install", "playwright"],
            ["pip3", "install", "playwright"],
            ["pip", "install", "playwright"],
        ]
        installed = False
        for cmd in pip_cmds:
            try:
                subprocess.check_call(cmd)
                installed = True
                break
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        if not installed:
            print("Error: Failed to install playwright.")
            print("")
            print("Please install manually:")
            print("  pip3 install playwright")
            print("  playwright install chromium")
            sys.exit(1)

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            p.chromium.executable_path
    except Exception:
        print("Chromium not found, installing...")
        pw_cmds = [
            [sys.executable, "-m", "playwright", "install", "chromium"],
            ["playwright", "install", "chromium"],
        ]
        installed = False
        for cmd in pw_cmds:
            try:
                subprocess.check_call(cmd)
                installed = True
                break
            except (subprocess.CalledProcessError, FileNotFoundError):
                continue
        if not installed:
            print("Error: Failed to install Chromium.")
            print("")
            print("Please install manually:")
            print("  playwright install chromium")
            sys.exit(1)


ensure_playwright()

from playwright.async_api import async_playwright  # noqa: E402

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_FILE = SCRIPT_DIR / "jvs_keep_alive.json"
LOG_FILE = SCRIPT_DIR / "jvs_keep_alive.log"
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
        logging.FileHandler(str(LOG_FILE), encoding="utf-8"),
    ],
)
logger = logging.getLogger("jvs")


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


def parse_cookie_string(cookie_str):
    """Parse 'k1=v1; k2=v2' into a list of Playwright cookie dicts."""
    cookies = []
    for item in cookie_str.split(";"):
        item = item.strip()
        if "=" in item:
            key, value = item.split("=", 1)
            cookies.append(
                {
                    "name": key.strip(),
                    "value": value.strip(),
                    "domain": ".aliyun.com",
                    "path": "/",
                }
            )
    return cookies


async def run_keep_alive(cookie_str, interval, headed):
    chat_url = f"{BASE_URL}/chat?currentWuyingServerId={SERVER_ID}"

    logger.info("=" * 55)
    logger.info("JVS WebUI Keep-Alive Started (Playwright)")
    logger.info(f"  Target:   {chat_url}")
    logger.info(f"  Interval: {interval}s")
    logger.info(f"  Mode:     {'headed' if headed else 'headless'}")
    logger.info(f"  Config:   {CONFIG_FILE}")
    logger.info("=" * 55)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not headed)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 720},
        )

        # Load cookies into browser context
        pw_cookies = parse_cookie_string(cookie_str)
        if pw_cookies:
            await context.add_cookies(pw_cookies)
            logger.info(f"Loaded {len(pw_cookies)} cookies into browser")

        page = await context.new_page()

        # Navigate to chat page
        logger.info("Opening chat page...")
        try:
            resp = await page.goto(chat_url, wait_until="networkidle", timeout=60000)
            if resp and resp.status == 200:
                title = await page.title()
                logger.info(f"[OK] Page loaded - Title: {title}")
            else:
                status = resp.status if resp else "N/A"
                logger.warning(f"[WARN] Page loaded with status: {status}")
                url = page.url
                if "login" in url.lower():
                    logger.error("[FAIL] Redirected to login page. Cookie may be expired.")
        except Exception as e:
            logger.error(f"[ERROR] Failed to load page: {e}")

        # Keep alive loop
        success_count = 0
        fail_count = 0
        config_mtime = CONFIG_FILE.stat().st_mtime if CONFIG_FILE.exists() else None

        try:
            while True:
                await asyncio.sleep(interval)

                # Check config file for updates
                if CONFIG_FILE.exists():
                    current_mtime = CONFIG_FILE.stat().st_mtime
                    if config_mtime is not None and current_mtime > config_mtime:
                        config_mtime = current_mtime
                        try:
                            config = load_config_file()
                            if config:
                                new_cookie = (config.get("cookies") or "").strip()
                                new_interval = config.get("interval", interval)
                                if new_interval != interval:
                                    interval = int(new_interval)
                                    logger.info(f"Reloaded interval: {interval}s")
                                if new_cookie and new_cookie != cookie_str:
                                    cookie_str = new_cookie
                                    await context.clear_cookies()
                                    await context.add_cookies(parse_cookie_string(new_cookie))
                                    logger.info("Reloaded new cookies from config")
                        except Exception as e:
                            logger.warning(f"Failed to reload config: {e}")

                # Reload the page to trigger frontend JS
                try:
                    resp = await page.reload(wait_until="networkidle", timeout=60000)
                    if resp and resp.status == 200:
                        success_count += 1
                        fail_count = 0
                        title = await page.title()
                        logger.info(
                            f"[OK] Heartbeat #{success_count} - "
                            f"Title: {title}"
                        )

                        # Save current browser cookies back to config
                        browser_cookies = await context.cookies()
                        cookie_parts = [
                            f"{c['name']}={c['value']}" for c in browser_cookies
                        ]
                        save_config_file("; ".join(cookie_parts), interval)
                        if CONFIG_FILE.exists():
                            config_mtime = CONFIG_FILE.stat().st_mtime
                    else:
                        fail_count += 1
                        status = resp.status if resp else "N/A"
                        url = page.url
                        if "login" in url.lower():
                            logger.error(
                                f"[FAIL] Redirected to login. "
                                f"Cookie expired. Failures: {fail_count}"
                            )
                        else:
                            logger.warning(
                                f"[WARN] Status: {status}. Failures: {fail_count}"
                            )

                except Exception as e:
                    fail_count += 1
                    logger.error(f"[ERROR] Reload failed: {e}. Failures: {fail_count}")

                if fail_count >= 3:
                    logger.error(
                        f"{fail_count} consecutive failures. "
                        f"Please update cookie in {CONFIG_FILE}"
                    )
                if fail_count >= 10:
                    logger.error("Too many failures, stopping.")
                    break

        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            logger.info("=" * 55)
            logger.info("Keep-Alive Stopped")
            logger.info(f"  Total heartbeats: {success_count}")
            logger.info("=" * 55)
            await browser.close()


def main():
    parser = argparse.ArgumentParser(description="JVS WebUI Keep-Alive (Playwright)")
    parser.add_argument(
        "--interval",
        type=int,
        default=None,
        help="Page reload interval in seconds (default: from config or 600)",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run with visible browser window (default: headless)",
    )
    args = parser.parse_args()

    ensure_config_file(600)
    config = load_config_file()
    if not config or not (config.get("cookies") or "").strip():
        print("No cookie configured.")
        print(f"Edit: {CONFIG_FILE}")
        sys.exit(1)

    cookie_str = config["cookies"].strip()
    interval = args.interval or int(config.get("interval", 600))

    logger.info(f"Loaded config from {CONFIG_FILE}")

    asyncio.run(run_keep_alive(cookie_str, interval, args.headed))


if __name__ == "__main__":
    main()
