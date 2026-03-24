#!/usr/bin/env python3
"""
ModelScope Studio Keep-Alive Script (Playwright)

Keeps a ModelScope Studio page active with a real Chromium browser.
For private spaces, the recommended flow is:

1. Run `python login_and_save.py` once and complete login manually.
2. Run `python modelscope_keep_alive.py` afterwards.

The keep-alive script will reuse the saved Playwright storage state
(`modelscope_auth.json`) and keep refreshing it while running.
"""

import argparse
import asyncio
import json
import logging
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def ensure_playwright(browser_channel="chromium"):
    """Auto-install Playwright and Chromium if missing."""
    if sys.version_info < (3, 9):
        print(f"Error: Python {sys.version_info.major}.{sys.version_info.minor} detected.")
        print("Playwright requires Python 3.9 or higher.")
        sys.exit(1)

    try:
        import playwright  # noqa: F401
    except ImportError:
        print("playwright not found, installing...")
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
            print("Please install manually:")
            print("  pip install playwright")
            print("  playwright install chromium")
            sys.exit(1)

    if browser_channel and browser_channel != "chromium":
        return

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
            print("Please install manually:")
            print("  playwright install chromium")
            sys.exit(1)

PlaywrightError = Exception
PlaywrightTimeoutError = TimeoutError
async_playwright = None

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_FILE = SCRIPT_DIR / "modelscope_keep_alive.json"
LOG_FILE = SCRIPT_DIR / "modelscope_keep_alive.log"
DEFAULT_AUTH_FILE = SCRIPT_DIR / "modelscope_auth.json"
DEFAULT_URL = "https://www.modelscope.cn/studios/haso2007/openclaw_computer/summary"
DEFAULT_CHECK_INTERVAL = 180
COOKIE_DOMAIN = ".modelscope.cn"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

ENTRY_TEXTS = [
    "在线体验",
    "开始体验",
    "进入应用",
    "打开应用",
    "启动",
    "运行",
    "唤醒",
    "继续",
    "恢复",
    "重新连接",
    "Preview",
    "Experience",
    "Launch",
    "Open",
    "Start",
    "Run",
    "Wake up",
    "Resume",
    "Reconnect",
    "Continue",
]

DISMISS_TEXTS = [
    "我知道了",
    "知道了",
    "确认",
    "确定",
    "同意",
    "接受",
    "Allow",
    "Accept",
    "Agree",
    "OK",
    "Close",
    "关闭",
]

TAB_TEXTS = [
    "空间内容",
    "应用",
    "在线体验",
    "预览",
    "Preview",
    "App",
    "Space",
]

LOGIN_URL_KEYWORDS = ["login", "signin", "passport"]
LOGIN_TEXT_KEYWORDS = ["登录", "sign in", "log in", "验证码", "password"]
NOT_FOUND_TEXT_KEYWORDS = [
    "抱歉，你访问的页面不存在",
    "sorry the page you visited does not exist",
    "page does not exist",
]

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
logger = logging.getLogger("modelscope")


def bootstrap_playwright(browser_channel):
    global PlaywrightError
    global PlaywrightTimeoutError
    global async_playwright

    ensure_playwright(browser_channel)
    from playwright.async_api import Error as _PlaywrightError
    from playwright.async_api import TimeoutError as _PlaywrightTimeoutError
    from playwright.async_api import async_playwright as _async_playwright

    PlaywrightError = _PlaywrightError
    PlaywrightTimeoutError = _PlaywrightTimeoutError
    async_playwright = _async_playwright


def default_config(target_url=DEFAULT_URL, check_interval=DEFAULT_CHECK_INTERVAL):
    return {
        "target_url": target_url,
        "cookies": "",
        "check_interval": check_interval,
        "auth_file": DEFAULT_AUTH_FILE.name,
        "browser_channel": "msedge" if sys.platform == "win32" else "chromium",
        "last_updated": "",
    }


def load_config_file():
    if not CONFIG_FILE.exists():
        return None
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def resolve_auth_file(auth_file_value=None):
    raw_value = (auth_file_value or DEFAULT_AUTH_FILE.name).strip()
    candidate = Path(raw_value)
    if candidate.is_absolute():
        return candidate
    return SCRIPT_DIR / candidate


def auth_file_config_value(auth_file):
    auth_file = Path(auth_file)
    try:
        return str(auth_file.relative_to(SCRIPT_DIR))
    except ValueError:
        return str(auth_file)


def save_config_file(cookies, target_url, check_interval, auth_file, browser_channel):
    data = {
        "target_url": target_url,
        "cookies": cookies,
        "check_interval": check_interval,
        "auth_file": auth_file_config_value(auth_file),
        "browser_channel": browser_channel,
        "last_updated": datetime.now().isoformat(),
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def ensure_config_file(target_url=DEFAULT_URL, check_interval=DEFAULT_CHECK_INTERVAL):
    if CONFIG_FILE.exists():
        return
    save_config_file(
        "",
        target_url,
        check_interval,
        DEFAULT_AUTH_FILE,
        "msedge" if sys.platform == "win32" else "chromium",
    )


def parse_cookie_string(cookie_str):
    """Parse 'k1=v1; k2=v2' into Playwright cookie dicts."""
    cookies = []
    for item in cookie_str.split(";"):
        item = item.strip()
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        cookies.append(
            {
                "name": key.strip(),
                "value": value.strip(),
                "domain": COOKIE_DOMAIN,
                "path": "/",
                "secure": True,
            }
        )
    return cookies


async def maybe_wait_for_network_idle(page, timeout_ms=15000):
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except PlaywrightTimeoutError:
        logger.debug("Timed out while waiting for network idle")


def attach_page_logging(page):
    page.on("console", lambda msg: logger.debug(f"[Browser] {msg.type}: {msg.text}"))


def iter_scopes(page):
    yield ("page", page)
    for index, frame in enumerate(page.frames):
        if frame == page.main_frame:
            continue
        label = f"frame#{index}"
        if frame.url:
            label = f"{label} {frame.url}"
        yield (label, frame)


async def try_click_text(scope, label, text):
    pattern = re.compile(re.escape(text), re.IGNORECASE)
    candidates = [
        scope.get_by_role("button", name=pattern),
        scope.locator("a, button, [role='button']").filter(has_text=pattern),
        scope.get_by_text(pattern),
    ]

    for locator in candidates:
        try:
            count = await locator.count()
        except PlaywrightError:
            continue

        for idx in range(min(count, 3)):
            item = locator.nth(idx)
            try:
                await item.wait_for(state="visible", timeout=700)
                await item.scroll_into_view_if_needed(timeout=700)
                await item.click(timeout=1500)
                logger.info(f"Clicked '{text}' on {label}")
                return True
            except (PlaywrightError, PlaywrightTimeoutError):
                continue

    return False


async def try_click_common_texts(page, texts):
    clicked = False
    for label, scope in iter_scopes(page):
        for text in texts:
            if await try_click_text(scope, label, text):
                clicked = True
                await asyncio.sleep(1)
    return clicked


async def get_body_text(page, timeout_ms=3000):
    try:
        return await page.locator("body").inner_text(timeout=timeout_ms)
    except (PlaywrightError, PlaywrightTimeoutError):
        return ""


async def detect_page_flags(page):
    url_lower = page.url.lower()
    body_text = await get_body_text(page)
    body_lower = body_text.lower()

    login_page = any(keyword in url_lower for keyword in LOGIN_URL_KEYWORDS)
    if not login_page:
        login_page = sum(keyword in body_lower for keyword in LOGIN_TEXT_KEYWORDS) >= 2

    not_found_page = False
    if any(keyword in body_lower for keyword in NOT_FOUND_TEXT_KEYWORDS):
        not_found_page = True
    elif "404" in body_lower and "回到首页" in body_text:
        not_found_page = True

    return {
        "login_page": login_page,
        "not_found_page": not_found_page,
        "body_excerpt": body_text[:300].replace("\n", " | "),
    }


async def keep_page_active(page, check_count):
    viewport = page.viewport_size or {"width": 1280, "height": 720}
    max_x = max(80, viewport["width"] - 40)
    max_y = max(120, viewport["height"] - 40)
    x = min(120 + (check_count % 5) * 90, max_x)
    y = min(180 + (check_count % 4) * 60, max_y)

    try:
        await page.bring_to_front()
    except PlaywrightError:
        pass

    try:
        await page.mouse.move(x, y)
        await page.mouse.wheel(0, 240)
        await asyncio.sleep(0.3)
        await page.mouse.wheel(0, -240)
    except PlaywrightError:
        pass

    try:
        await page.locator("body").hover(timeout=1200)
    except (PlaywrightError, PlaywrightTimeoutError):
        pass

    for _, frame in iter_scopes(page):
        if frame == page:
            continue
        try:
            await frame.locator("body").hover(timeout=1000)
            break
        except (PlaywrightError, PlaywrightTimeoutError):
            continue


async def capture_state(page):
    try:
        title = await page.title()
    except PlaywrightError:
        title = "<unavailable>"

    try:
        ready_state = await page.evaluate("document.readyState")
    except PlaywrightError:
        ready_state = "unknown"

    return title, ready_state


async def open_target(page, target_url):
    logger.info(f"Opening target page: {target_url}")
    response = await page.goto(target_url, wait_until="domcontentloaded", timeout=60000)
    await maybe_wait_for_network_idle(page)
    await try_click_common_texts(page, TAB_TEXTS)
    await try_click_common_texts(page, ENTRY_TEXTS)
    await try_click_common_texts(page, DISMISS_TEXTS)
    await maybe_wait_for_network_idle(page, timeout_ms=5000)
    return response


async def create_context(browser, cookie_str, auth_file):
    auth_file = Path(auth_file)
    context_kwargs = {
        "user_agent": USER_AGENT,
        "viewport": {"width": 1440, "height": 900},
        "locale": "zh-CN",
        "timezone_id": "Asia/Shanghai",
    }

    if auth_file.exists():
        context_kwargs["storage_state"] = str(auth_file)
        logger.info(f"Loaded saved login state from {auth_file}")

    context = await browser.new_context(**context_kwargs)

    pw_cookies = parse_cookie_string(cookie_str)
    if pw_cookies:
        await context.add_cookies(pw_cookies)
        logger.info(f"Loaded {len(pw_cookies)} cookies into browser")
    elif not auth_file.exists():
        logger.info("No saved login state or cookies configured; continuing anonymously")

    return context


async def open_session(browser, cookie_str, auth_file):
    context = await create_context(browser, cookie_str, auth_file)
    page = await context.new_page()
    attach_page_logging(page)
    return context, page


async def close_session(context, page):
    try:
        await page.close()
    except Exception:
        pass
    try:
        await context.close()
    except Exception:
        pass


async def persist_session_state(
    context, target_url, check_interval, auth_file, browser_channel
):
    auth_file = Path(auth_file)
    auth_file.parent.mkdir(parents=True, exist_ok=True)

    browser_cookies = await context.cookies()
    cookie_parts = [
        f"{cookie['name']}={cookie['value']}"
        for cookie in browser_cookies
        if COOKIE_DOMAIN.lstrip(".") in cookie.get("domain", "")
    ]

    await context.storage_state(path=str(auth_file))
    save_config_file(
        "; ".join(cookie_parts),
        target_url,
        check_interval,
        auth_file,
        browser_channel,
    )


async def run_keep_alive(
    cookie_str, target_url, check_interval, headed, auth_file, browser_channel
):
    logger.info("=" * 55)
    logger.info("ModelScope Studio Keep-Alive Started (Playwright)")
    logger.info(f"  Target:   {target_url}")
    logger.info(f"  Mode:     {'headed' if headed else 'headless'}")
    logger.info(f"  Check:    Every {check_interval}s")
    logger.info(f"  Auth:     {auth_file}")
    logger.info(f"  Browser:  {browser_channel}")
    logger.info(f"  Config:   {CONFIG_FILE}")
    logger.info("=" * 55)

    async with async_playwright() as p:
        launch_kwargs = {
            "headless": not headed,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        }
        if browser_channel and browser_channel != "chromium":
            launch_kwargs["channel"] = browser_channel
        browser = await p.chromium.launch(**launch_kwargs)

        context, page = await open_session(browser, cookie_str, auth_file)
        config_mtime = CONFIG_FILE.stat().st_mtime if CONFIG_FILE.exists() else None
        auth_mtime = auth_file.stat().st_mtime if auth_file.exists() else None
        check_count = 0

        try:
            response = await open_target(page, target_url)
            if response:
                logger.info(f"[OK] Initial response status: {response.status}")

            title, ready_state = await capture_state(page)
            page_flags = await detect_page_flags(page)
            logger.info(f"[OK] Page loaded - Title: {title}")
            logger.info(f"[OK] Ready state: {ready_state}")

            if page_flags["login_page"]:
                logger.error("[FAIL] Redirected to a login/auth page")
                logger.error("Run `python login_and_save.py` to save a reusable login state.")
                return

            if page_flags["not_found_page"]:
                logger.error("[FAIL] Page rendered as 404 / access denied")
                if not auth_file.exists() and not cookie_str:
                    logger.error("This is expected for private spaces without login state.")
                    logger.error("Run `python login_and_save.py` first, then start keep-alive.")
                else:
                    logger.error(f"Body excerpt: {page_flags['body_excerpt']}")
                return

            await persist_session_state(
                context, target_url, check_interval, auth_file, browser_channel
            )
            auth_mtime = auth_file.stat().st_mtime if auth_file.exists() else auth_mtime

            while True:
                await asyncio.sleep(check_interval)
                check_count += 1

                try:
                    await keep_page_active(page, check_count)
                    await try_click_common_texts(page, ENTRY_TEXTS)
                    await try_click_common_texts(page, DISMISS_TEXTS)

                    title, ready_state = await capture_state(page)
                    page_flags = await detect_page_flags(page)

                    if page_flags["login_page"]:
                        logger.error(
                            f"[FAIL] Check #{check_count} - redirected to login/auth page"
                        )
                    elif page_flags["not_found_page"]:
                        logger.error(f"[FAIL] Check #{check_count} - page rendered as 404")
                        logger.error(f"Body excerpt: {page_flags['body_excerpt']}")
                    else:
                        logger.info(
                            f"[OK] Check #{check_count} - alive - Title: {title} - State: {ready_state}"
                        )

                    await persist_session_state(
                        context, target_url, check_interval, auth_file, browser_channel
                    )
                    config_mtime = CONFIG_FILE.stat().st_mtime if CONFIG_FILE.exists() else None
                    auth_mtime = auth_file.stat().st_mtime if auth_file.exists() else auth_mtime

                except Exception as exc:
                    logger.error(f"[ERROR] Check #{check_count} - page interaction failed: {exc}")
                    logger.info("Attempting to recover by reopening the target page...")
                    await close_session(context, page)
                    context, page = await open_session(browser, cookie_str, auth_file)
                    await open_target(page, target_url)

                if CONFIG_FILE.exists():
                    current_mtime = CONFIG_FILE.stat().st_mtime
                    if config_mtime is not None and current_mtime > config_mtime:
                        config_mtime = current_mtime
                        try:
                            config = load_config_file() or {}
                            new_cookie_str = (config.get("cookies") or "").strip()
                            new_target_url = (config.get("target_url") or target_url).strip()
                            new_interval = int(
                                config.get("check_interval", check_interval) or check_interval
                            )
                            new_auth_file = resolve_auth_file(config.get("auth_file"))
                            new_browser_channel = normalize_browser_channel(
                                config.get("browser_channel")
                            )

                            should_reopen = False

                            if new_cookie_str != cookie_str:
                                cookie_str = new_cookie_str
                                logger.info("Cookie string updated from config file")
                                should_reopen = True

                            if new_auth_file != auth_file:
                                auth_file = new_auth_file
                                logger.info(f"Auth file updated from config: {auth_file}")
                                should_reopen = True

                            if new_target_url and new_target_url != target_url:
                                target_url = new_target_url
                                logger.info(f"Target URL updated from config: {target_url}")
                                should_reopen = True

                            if new_interval != check_interval:
                                check_interval = new_interval
                                logger.info(
                                    f"Check interval updated from config: {check_interval}s"
                                )

                            if new_browser_channel != browser_channel:
                                browser_channel = new_browser_channel
                                logger.warning(
                                    "Browser channel changed in config; restart the script to apply it."
                                )

                            if should_reopen:
                                await close_session(context, page)
                                context, page = await open_session(
                                    browser, cookie_str, auth_file
                                )
                                await open_target(page, target_url)
                                await persist_session_state(
                                    context,
                                    target_url,
                                    check_interval,
                                    auth_file,
                                    browser_channel,
                                )
                                auth_mtime = (
                                    auth_file.stat().st_mtime
                                    if auth_file.exists()
                                    else auth_mtime
                                )
                        except Exception as exc:
                            logger.warning(f"Failed to reload config: {exc}")

                current_auth_mtime = auth_file.stat().st_mtime if auth_file.exists() else None
                if (
                    auth_mtime is not None
                    and current_auth_mtime is not None
                    and current_auth_mtime > auth_mtime
                ):
                    logger.info("Detected refreshed login state, reopening browser context...")
                    auth_mtime = current_auth_mtime
                    await close_session(context, page)
                    context, page = await open_session(browser, cookie_str, auth_file)
                    await open_target(page, target_url)

        except (KeyboardInterrupt, asyncio.CancelledError):
            pass
        finally:
            logger.info("=" * 55)
            logger.info("Keep-Alive Stopped")
            logger.info(f"  Total checks: {check_count}")
            logger.info("=" * 55)
            await close_session(context, page)
            await browser.close()


def main():
    parser = argparse.ArgumentParser(
        description="ModelScope Studio Keep-Alive (Playwright)"
    )
    parser.add_argument(
        "--check-interval",
        type=int,
        default=None,
        help=(
            "Status check interval in seconds "
            f"(default: from config or {DEFAULT_CHECK_INTERVAL})"
        ),
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="Override the target studio URL",
    )
    parser.add_argument(
        "--auth-file",
        type=str,
        default=None,
        help=f"Saved Playwright login state file (default: {DEFAULT_AUTH_FILE.name})",
    )
    parser.add_argument(
        "--browser-channel",
        type=str,
        default=None,
        help="Browser channel to launch, for example `msedge` or `chromium`",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run with a visible browser window (default: headless)",
    )
    args = parser.parse_args()

    ensure_config_file(DEFAULT_URL, DEFAULT_CHECK_INTERVAL)
    config = load_config_file() or default_config()

    target_url = (args.url or config.get("target_url") or DEFAULT_URL).strip()
    cookie_str = (config.get("cookies") or "").strip()
    check_interval = args.check_interval or int(
        config.get("check_interval", DEFAULT_CHECK_INTERVAL)
    )
    auth_file = resolve_auth_file(args.auth_file or config.get("auth_file"))
    browser_channel = normalize_browser_channel(
        args.browser_channel or config.get("browser_channel")
    )

    bootstrap_playwright(browser_channel)
    save_config_file(cookie_str, target_url, check_interval, auth_file, browser_channel)
    logger.info(f"Loaded config from {CONFIG_FILE}")

    asyncio.run(
        run_keep_alive(
            cookie_str,
            target_url,
            check_interval,
            args.headed,
            auth_file,
            browser_channel,
        )
    )


if __name__ == "__main__":
    main()
def normalize_browser_channel(browser_channel):
    value = (browser_channel or "").strip()
    if not value:
        return "msedge" if sys.platform == "win32" else "chromium"
    return value
