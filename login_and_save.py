#!/usr/bin/env python3
"""
Open a real browser, let the user log in manually, then save Playwright
storage state for later reuse by `modelscope_keep_alive.py`.
"""

import argparse
import json
import os
import subprocess
import sys
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
DEFAULT_AUTH_FILE = STATE_DIR / "modelscope_auth.json"
DEFAULT_EDGE_USER_DATA_DIR = (
    Path.home() / "AppData" / "Local" / "Microsoft" / "Edge" / "User Data"
)
DEFAULT_URL = "https://www.modelscope.cn/studios/haso2007/openclaw_computer/summary"
DEFAULT_CHECK_INTERVAL = 1800
COOKIE_DOMAIN = ".modelscope.cn"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def default_config():
    return {
        "target_url": DEFAULT_URL,
        "cookies": "",
        "check_interval": DEFAULT_CHECK_INTERVAL,
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
        "last_updated": __import__("datetime").datetime.now().isoformat(),
    }
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def extract_cookie_string(cookies):
    return "; ".join(
        f"{cookie['name']}={cookie['value']}"
        for cookie in cookies
        if COOKIE_DOMAIN.lstrip(".") in cookie.get("domain", "")
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


def resolve_user_data_dir(edge_user_data_dir):
    if not edge_user_data_dir:
        return DEFAULT_EDGE_USER_DATA_DIR
    return Path(edge_user_data_dir).expanduser()


def main():
    parser = argparse.ArgumentParser(
        description="Login to ModelScope manually and save reusable auth state"
    )
    parser.add_argument(
        "--url",
        type=str,
        default=None,
        help="Target private studio URL to open after login",
    )
    parser.add_argument(
        "--auth-file",
        type=str,
        default=None,
        help=f"Output storage state file (default: {DEFAULT_AUTH_FILE.name})",
    )
    parser.add_argument(
        "--browser-channel",
        type=str,
        default=None,
        help="Browser channel to launch, for example `msedge` or `chromium`",
    )
    parser.add_argument(
        "--edge-user-data-dir",
        type=str,
        default=None,
        help="Existing Edge User Data directory, for example the parent of `Profile 2`",
    )
    parser.add_argument(
        "--profile-directory",
        type=str,
        default=None,
        help='Existing Edge profile directory name, for example "Profile 2"',
    )
    args = parser.parse_args()

    config = load_config_file() or default_config()
    target_url = (args.url or config.get("target_url") or DEFAULT_URL).strip()
    check_interval = int(config.get("check_interval", DEFAULT_CHECK_INTERVAL))
    auth_file = resolve_auth_file(args.auth_file or config.get("auth_file"))
    browser_channel = normalize_browser_channel(
        args.browser_channel or config.get("browser_channel")
    )
    edge_user_data_dir = resolve_user_data_dir(args.edge_user_data_dir)
    auth_file.parent.mkdir(parents=True, exist_ok=True)

    ensure_playwright(browser_channel)
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        launch_kwargs = {
            "headless": False,
        }
        if browser_channel and browser_channel != "chromium":
            launch_kwargs["channel"] = browser_channel

        context_kwargs = {
            "user_agent": USER_AGENT,
            "viewport": {"width": 1440, "height": 900},
            "locale": "zh-CN",
            "timezone_id": "Asia/Shanghai",
        }

        using_existing_profile = bool(args.profile_directory or args.edge_user_data_dir)

        try:
            if using_existing_profile:
                launch_args = build_browser_launch_args()
                if args.profile_directory:
                    launch_args.append(f"--profile-directory={args.profile_directory}")
                context = p.chromium.launch_persistent_context(
                    str(edge_user_data_dir),
                    args=launch_args,
                    **context_kwargs,
                    **launch_kwargs,
                )
                browser = None
                page = context.pages[0] if context.pages else context.new_page()
            else:
                browser = p.chromium.launch(
                    args=build_browser_launch_args(),
                    **launch_kwargs,
                )
                if auth_file.exists():
                    context_kwargs["storage_state"] = str(auth_file)
                context = browser.new_context(**context_kwargs)
                page = context.new_page()
        except Exception as exc:
            if using_existing_profile:
                print("")
                print("无法直接接管现有 Edge Profile。")
                print("请先完全关闭所有 Edge 窗口后再试，或者不要传 `--profile-directory`。")
                print(f"User Data Dir: {edge_user_data_dir}")
                print(f"Profile Directory: {args.profile_directory or '<default>'}")
                print(f"Browser Channel: {browser_channel}")
                print(f"原始错误: {exc}")
                sys.exit(1)
            print("")
            print("浏览器启动失败。")
            print("如果系统安装了 Edge，建议这样运行：")
            print("  python login_and_save.py --browser-channel msedge")
            print(f"原始错误: {exc}")
            sys.exit(1)

        page.goto(target_url, wait_until="domcontentloaded", timeout=60000)

        print("")
        print("请在弹出的浏览器中完成 ModelScope 登录。")
        print("登录完成后，确认私有空间页面已经可以正常打开。")
        print("完成后回到终端按 Enter 保存登录态；输入 q 后回车取消。")
        print("")

        answer = input("继续保存登录态? [Enter/q]: ").strip().lower()
        if answer == "q":
            print("已取消，不保存登录态。")
            context.close()
            if browser:
                browser.close()
            return

        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            pass

        title = page.title()
        current_url = page.url
        body_text = page.locator("body").inner_text(timeout=5000)

        if "抱歉，你访问的页面不存在" in body_text or "sorry the page you visited does not exist" in body_text.lower():
            print("")
            print("警告：当前页面仍然是 404/无权限 页面。")
            print("这通常表示登录还没有完成，或者当前账号没有这个私有空间的访问权限。")
            print(f"当前 URL: {current_url}")
            print(f"当前标题: {title}")
            context.close()
            if browser:
                browser.close()
            sys.exit(1)

        context.storage_state(path=str(auth_file))
        cookies = context.cookies()
        save_config_file(
            extract_cookie_string(cookies),
            target_url,
            check_interval,
            auth_file,
            browser_channel,
        )

        print("")
        print(f"登录态已保存到: {auth_file}")
        print(f"当前 URL: {current_url}")
        print(f"当前标题: {title}")
        print("")
        print("后续可直接运行:")
        print("  python modelscope_keep_alive.py")

        context.close()
        if browser:
            browser.close()


if __name__ == "__main__":
    main()
