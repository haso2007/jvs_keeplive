#!/usr/bin/env python3
"""
OpenClaw Gateway Auto-Restart Script

Periodically restarts the OpenClaw gateway to prevent JWT token expiration.

Usage:
    python gateway_restart.py
    python gateway_restart.py --interval 3600
    python gateway_restart.py --interval 1800

Configuration:
    Edit RESTART_INTERVAL_SECONDS below, or pass --interval on the command line.
"""

import argparse
import logging
import subprocess
import sys
import time
from datetime import datetime, timedelta

# ============================================================
# Configuration: Change this value to adjust restart frequency
# ============================================================
RESTART_INTERVAL_SECONDS = 3600  # Default: 3600 (1 hour)
# ============================================================

RESTART_COMMAND = ["ocw", "gateway", "restart"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("gateway-restart")


def restart_gateway():
    """Execute the gateway restart command."""
    cmd_str = " ".join(RESTART_COMMAND)
    logger.info(f"Restarting gateway: {cmd_str}")
    try:
        result = subprocess.run(
            RESTART_COMMAND,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            logger.info(f"[OK] Gateway restarted successfully")
            if result.stdout.strip():
                logger.info(f"  stdout: {result.stdout.strip()}")
        else:
            logger.error(f"[FAIL] Gateway restart failed (exit code {result.returncode})")
            if result.stderr.strip():
                logger.error(f"  stderr: {result.stderr.strip()}")
            if result.stdout.strip():
                logger.error(f"  stdout: {result.stdout.strip()}")
        return result.returncode == 0
    except FileNotFoundError:
        logger.error(f"[FAIL] Command not found: {cmd_str}")
        logger.error(f"  Make sure 'ocw' is in your PATH")
        return False
    except subprocess.TimeoutExpired:
        logger.error(f"[FAIL] Command timed out after 60s")
        return False
    except Exception as e:
        logger.error(f"[FAIL] Unexpected error: {e}")
        return False


def format_duration(seconds):
    """Format seconds into human-readable string."""
    if seconds >= 3600:
        h = seconds // 3600
        m = (seconds % 3600) // 60
        return f"{h}h{m}m" if m else f"{h}h"
    elif seconds >= 60:
        return f"{seconds // 60}m"
    else:
        return f"{seconds}s"


def main():
    parser = argparse.ArgumentParser(description="OpenClaw Gateway Auto-Restart")
    parser.add_argument(
        "--interval",
        type=int,
        default=RESTART_INTERVAL_SECONDS,
        help=f"Restart interval in seconds (default: {RESTART_INTERVAL_SECONDS})",
    )
    args = parser.parse_args()

    interval = args.interval
    interval_str = format_duration(interval)

    logger.info("=" * 55)
    logger.info("OpenClaw Gateway Auto-Restart Started")
    logger.info(f"  Command:  {' '.join(RESTART_COMMAND)}")
    logger.info(f"  Interval: {interval}s ({interval_str})")
    logger.info("=" * 55)

    restart_count = 0

    try:
        while True:
            next_restart = datetime.now() + timedelta(seconds=interval)
            logger.info(f"Next restart at: {next_restart.strftime('%Y-%m-%d %H:%M:%S')}")

            time.sleep(interval)

            restart_count += 1
            logger.info(f"--- Restart #{restart_count} ---")
            restart_gateway()

    except KeyboardInterrupt:
        pass
    finally:
        logger.info("=" * 55)
        logger.info("Auto-Restart Stopped")
        logger.info(f"  Total restarts: {restart_count}")
        logger.info("=" * 55)


if __name__ == "__main__":
    main()
