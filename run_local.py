#!/usr/bin/env python3
"""
Wrapper pour exécuter FXMomentumBot en continu en local.
Scans toutes les 5 minutes, uniquement dans les fenêtres horaires définies (heure Paris).

Fenêtres actives :  01h–03h  |  09h–11h  |  15h–17h  |  20h–22h
"""

import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fx_momentum_bot import FOREX_PAIRS, TELEGRAM_BOT_TOKEN, MOMENTUM_CHANNEL_ID, scan_all

from dotenv import load_dotenv
from telegram import Bot

load_dotenv()

TZ_PARIS          = ZoneInfo("Europe/Paris")
SCAN_INTERVAL_MIN = 5
WINDOWS           = [(1, 3), (9, 11), (15, 17), (20, 22)]  # [start_h, end_h[ heure Paris

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("momentum_bot.log"),
    ],
)
log = logging.getLogger(__name__)


def now_paris() -> datetime:
    return datetime.now(TZ_PARIS)


def in_window(dt: datetime) -> bool:
    return any(start <= dt.hour < end for start, end in WINDOWS)


def seconds_until_next_window(dt: datetime) -> float:
    """Retourne le nombre de secondes avant le début de la prochaine fenêtre."""
    for start, _ in WINDOWS:
        candidate = dt.replace(hour=start, minute=0, second=0, microsecond=0)
        if candidate > dt:
            return (candidate - dt).total_seconds()
    # Toutes les fenêtres du jour sont passées → première fenêtre du lendemain
    tomorrow_first = dt.replace(hour=WINDOWS[0][0], minute=0, second=0, microsecond=0) + timedelta(days=1)
    return (tomorrow_first - dt).total_seconds()


async def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN manquant dans .env")
    if not MOMENTUM_CHANNEL_ID:
        raise ValueError("MOMENTUM_CHANNEL_ID manquant dans .env")

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    me  = await bot.get_me()
    now = now_paris()
    utc_offset = now.strftime("%z")          # ex: +0200
    utc_label  = f"UTC{utc_offset[:3]}:{utc_offset[3:]}"  # → UTC+02:00

    log.info(f"FXMomentumBot connecté : @{me.username}")
    log.info(f"Channel cible : {MOMENTUM_CHANNEL_ID}")
    log.info(f"Paires surveillées : {len(FOREX_PAIRS)}")
    log.info(f"Heure locale : {now.strftime('%Y-%m-%d %H:%M:%S')} Paris ({utc_label})")
    log.info(f"Interval : {SCAN_INTERVAL_MIN} min — Fenêtres : " +
             "  ".join(f"{s:02d}h–{e:02d}h" for s, e in WINDOWS) + f" ({utc_label})")
    log.info("Ctrl+C pour arrêter\n")

    while True:
        now = now_paris()

        if in_window(now):
            await scan_all(bot)
            next_scan = now_paris() + timedelta(minutes=SCAN_INTERVAL_MIN)
            log.info(f"Prochain scan à {next_scan.strftime('%H:%M:%S')} (Paris)\n")
            await asyncio.sleep(SCAN_INTERVAL_MIN * 60)
        else:
            wait = seconds_until_next_window(now)
            wake = now_paris() + timedelta(seconds=wait)
            log.info(f"Hors fenêtre — attente jusqu'à {wake.strftime('%H:%M:%S')} (Paris) "
                     f"({wait / 60:.0f} min)\n")
            await asyncio.sleep(wait)


if __name__ == "__main__":
    asyncio.run(main())
