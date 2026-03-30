# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic


import time
import logging
from logging.handlers import RotatingFileHandler

logging.basicConfig(
    format="[%(asctime)s - %(levelname)s] - %(name)s: %(message)s",
    datefmt="%d-%b-%y %H:%M:%S",
    handlers=[
        RotatingFileHandler("log.txt", maxBytes=10485760, backupCount=5),
        logging.StreamHandler(),
    ],
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("ntgcalls").setLevel(logging.CRITICAL)
logging.getLogger("pymongo").setLevel(logging.ERROR)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("pytgcalls").setLevel(logging.ERROR)
logger = logging.getLogger(__name__)


__version__ = "3.0.1"

from config import Config

config = Config()
config.check()
tasks = []
boot = time.time()

from anony.core.bot import Bot
app = Bot()

from anony.core.dir import ensure_dirs
ensure_dirs()

from anony.core.userbot import Userbot
userbot = Userbot()

from anony.core.mongo import MongoDB
db = MongoDB()

from anony.core.lang import Language
lang = Language()

from anony.core.telegram import Telegram
from anony.core.youtube import YouTube
tg = Telegram()
yt = YouTube()

from anony.helpers import Queue
queue = Queue()

from anony.core.calls import TgCall
anon = TgCall()

# ✅ Redis initialization
import aioredis
import asyncio

async def init_redis():
    """Initialize Redis connection"""
    try:
        redis = aioredis.from_url(config.REDIS_URL)
        await redis.ping()
        logger.info(f"✅ Redis connected: {config.REDIS_URL}")
        await yt.init_redis()  # Initialize YouTube Redis cache
        return redis
    except Exception as e:
        logger.warning(f"⚠️ Redis connection failed: {e}")
        logger.info("Bot will work without Redis caching")
        return None

# Store Redis connection globally
redis_conn = None

async def init_app():
    """Initialize application"""
    global redis_conn
    try:
        redis_conn = await init_redis()
    except Exception as e:
        logger.warning(f"Redis init failed: {e}")

async def stop() -> None:
    """Stop the application gracefully"""
    logger.info("🛑 Stopping...")
    
    # Cancel all tasks
    for task in tasks:
        task.cancel()
        try:
            await task
        except:
            pass
    
    # Close connections
    try:
        await app.exit()
    except:
        pass
    
    try:
        await userbot.exit()
    except:
        pass
    
    try:
        await db.close()
    except:
        pass
    
    # Close Redis
    global redis_conn
    if redis_conn:
        try:
            await redis_conn.close()
            logger.info("Redis connection closed")
        except:
            pass

    logger.info("✅ Stopped.\n")
