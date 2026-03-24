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
import os
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


def resolve_state_dir():
    raw_value = os.environ.get("MODELSCOPE_STATE_DIR", "").strip()
    if not raw_value:
        return SCRIPT_DIR

    candidate = Path(raw_value).expanduser()
    if not candidate.is_absolute():
        candidate = SCRIPT_DIR / candidate
    return candidate.resolve()


STATE_DIR = resolve_state_dir()
STATE_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = STATE_DIR / "modelscope_keep_alive.json"
LOG_FILE = STATE_DIR / "modelscope_keep_alive.log"
DEFAULT_AUTH_FILE = STATE_DIR / "modelscope_auth.json"
DEFAULT_URL = "https://www.modelscope.cn/studios/haso2007/openclaw_computer/summary"
DEFAULT_CHECK_INTERVAL = 1800
ACTIVATION_RETRY_COOLDOWN_SECONDS = 300
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
ACTIVATION_HINT_TEXT_KEYWORDS = [
    "长时间未激活",
    "创空间长时间未激活",
    "正在为您重新部署",
    "预计10分钟内完成",
    "重新部署",
    "部署中",
    "启动中",
    "创建空间",
    "空间准备中",
    "正在启动",
    "已停止",
    "已休眠",
    "休眠",
    "待运行",
]
ACTIVATION_ENTRY_TEXTS = [
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
ACTIVATION_ONLY_ENTRY_TEXTS = {
    "唤醒",
    "恢复",
    "重新连接",
    "Wake up",
    "Resume",
    "Reconnect",
}

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
    with open(CONFIG_FILE, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def resolve_auth_file(auth_file_value=None):
    raw_value = (auth_file_value or DEFAULT_AUTH_FILE.name).strip()
    candidate = Path(raw_value)
    if candidate.is_absolute():
        return candidate
    return STATE_DIR / candidate


def auth_file_config_value(auth_file):
    auth_file = Path(auth_file)
    try:
        return str(auth_file.relative_to(STATE_DIR))
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


def normalize_browser_channel(browser_channel):
    value = (browser_channel or "").strip()
    if not value:
        return "msedge" if sys.platform == "win32" else "chromium"
    return value


def build_browser_launch_args():
    launch_args = [
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
    ]
    if sys.platform.startswith("linux"):
        launch_args.extend(
            [
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ]
        )
    return launch_args


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


def build_text_locators(scope, text):
    pattern = re.compile(re.escape(text), re.IGNORECASE)
    return [
        scope.get_by_role("button", name=pattern),
        scope.locator("a, button, [role='button']").filter(has_text=pattern),
        scope.get_by_text(pattern),
    ]


async def try_click_text(scope, label, text):
    candidates = build_text_locators(scope, text)

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


async def find_visible_action_texts(page, texts, max_matches=5):
    matches = []
    for label, scope in iter_scopes(page):
        for text in texts:
            if text in matches:
                continue
            for locator in build_text_locators(scope, text):
                try:
                    count = await locator.count()
                except PlaywrightError:
                    continue

                for idx in range(min(count, 3)):
                    item = locator.nth(idx)
                    try:
                        if await item.is_visible():
                            matches.append(text)
                            break
                    except PlaywrightError:
                        continue

                if text in matches:
                    break

            if len(matches) >= max_matches:
                return matches

    return matches


async def try_click_common_texts(page, texts, max_clicks=None):
    clicked = False
    click_count = 0
    for label, scope in iter_scopes(page):
        for text in texts:
            if max_clicks is not None and click_count >= max_clicks:
                return clicked
            if await try_click_text(scope, label, text):
                clicked = True
                click_count += 1
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
    visible_entry_controls = await find_visible_action_texts(page, ACTIVATION_ENTRY_TEXTS)

    login_page = any(keyword in url_lower for keyword in LOGIN_URL_KEYWORDS)
    if not login_page:
        login_page = sum(keyword in body_lower for keyword in LOGIN_TEXT_KEYWORDS) >= 2

    not_found_page = False
    if any(keyword in body_lower for keyword in NOT_FOUND_TEXT_KEYWORDS):
        not_found_page = True
    elif "404" in body_lower and "回到首页" in body_text:
        not_found_page = True

    activation_hints = [
        keyword for keyword in ACTIVATION_HINT_TEXT_KEYWORDS if keyword.lower() in body_lower
    ]
    activation_needed = bool(activation_hints)
    if not activation_needed:
        activation_needed = any(
            text in ACTIVATION_ONLY_ENTRY_TEXTS for text in visible_entry_controls
        )

    return {
        "login_page": login_page,
        "not_found_page": not_found_page,
        "activation_needed": activation_needed,
        "activation_hints": activation_hints,
        "entry_controls": visible_entry_controls,
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
    await try_click_common_texts(page, TAB_TEXTS, max_clicks=1)
    await try_click_common_texts(page, DISMISS_TEXTS, max_clicks=2)
    await maybe_wait_for_network_idle(page, timeout_ms=5000)
    return response


async def maybe_activate_space(page, page_flags, reason, force=False):
    should_activate = force or page_flags["activation_needed"]
    if not should_activate:
        return False

    if page_flags["activation_hints"]:
        logger.info(
            f"Activation required ({reason}) - hints: {', '.join(page_flags['activation_hints'])}"
        )
    elif page_flags["entry_controls"]:
        logger.info(
            f"Activation attempt ({reason}) - visible controls: {', '.join(page_flags['entry_controls'])}"
        )
    else:
        logger.info(f"Activation attempt ({reason}) - trying common entry controls")

    await try_click_common_texts(page, TAB_TEXTS, max_clicks=1)
    clicked = await try_click_common_texts(page, ENTRY_TEXTS, max_clicks=2)
    if clicked:
        await try_click_common_texts(page, DISMISS_TEXTS, max_clicks=2)
        await maybe_wait_for_network_idle(page, timeout_ms=10000)
    return clicked


async def open_and_prepare(page, target_url, activation_reason, force_initial_activation=False):
    response = await open_target(page, target_url)
    title, ready_state = await capture_state(page)
    page_flags = await detect_page_flags(page)
    activation_clicked = False

    if not page_flags["login_page"] and not page_flags["not_found_page"]:
        should_force_activate = force_initial_activation and bool(page_flags["entry_controls"])
        activation_clicked = await maybe_activate_space(
            page,
            page_flags,
            activation_reason,
            force=should_force_activate,
        )
        if activation_clicked:
            title, ready_state = await capture_state(page)
            page_flags = await detect_page_flags(page)

    return response, title, ready_state, page_flags, activation_clicked


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
            "args": build_browser_launch_args(),
        }
        if browser_channel and browser_channel != "chromium":
            launch_kwargs["channel"] = browser_channel
        browser = await p.chromium.launch(**launch_kwargs)

        context, page = await open_session(browser, cookie_str, auth_file)
        config_mtime = CONFIG_FILE.stat().st_mtime if CONFIG_FILE.exists() else None
        auth_mtime = auth_file.stat().st_mtime if auth_file.exists() else None
        check_count = 0
        last_activation_attempt_at = None

        try:
            response, title, ready_state, page_flags, activation_clicked = await open_and_prepare(
                page,
                target_url,
                activation_reason="initial open",
                force_initial_activation=True,
            )
            if response:
                logger.info(f"[OK] Initial response status: {response.status}")

            if activation_clicked:
                last_activation_attempt_at = asyncio.get_running_loop().time()

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

                    title, ready_state = await capture_state(page)
                    page_flags = await detect_page_flags(page)
                    now = asyncio.get_running_loop().time()

                    if page_flags["activation_needed"]:
                        can_retry_activation = (
                            last_activation_attempt_at is None
                            or now - last_activation_attempt_at
                            >= ACTIVATION_RETRY_COOLDOWN_SECONDS
                        )
                        if can_retry_activation:
                            activation_clicked = await maybe_activate_space(
                                page,
                                page_flags,
                                reason=f"check #{check_count}",
                            )
                            if activation_clicked:
                                last_activation_attempt_at = now
                                title, ready_state = await capture_state(page)
                                page_flags = await detect_page_flags(page)
                        else:
                            remaining = int(
                                ACTIVATION_RETRY_COOLDOWN_SECONDS
                                - (now - last_activation_attempt_at)
                            )
                            logger.info(
                                f"Activation still pending; next retry in about {max(1, remaining)}s"
                            )

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
                    (
                        _,
                        _title,
                        _ready_state,
                        _page_flags,
                        activation_clicked,
                    ) = await open_and_prepare(
                        page,
                        target_url,
                        activation_reason=f"recovery #{check_count}",
                        force_initial_activation=True,
                    )
                    if activation_clicked:
                        last_activation_attempt_at = asyncio.get_running_loop().time()

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
                                (
                                    _,
                                    _title,
                                    _ready_state,
                                    _page_flags,
                                    activation_clicked,
                                ) = await open_and_prepare(
                                    page,
                                    target_url,
                                    activation_reason="config reload",
                                    force_initial_activation=True,
                                )
                                await persist_session_state(
                                    context,
                                    target_url,
                                    check_interval,
                                    auth_file,
                                    browser_channel,
                                )
                                if activation_clicked:
                                    last_activation_attempt_at = (
                                        asyncio.get_running_loop().time()
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
                    (
                        _,
                        _title,
                        _ready_state,
                        _page_flags,
                        activation_clicked,
                    ) = await open_and_prepare(
                        page,
                        target_url,
                        activation_reason="auth refresh",
                        force_initial_activation=True,
                    )
                    if activation_clicked:
                        last_activation_attempt_at = asyncio.get_running_loop().time()

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
