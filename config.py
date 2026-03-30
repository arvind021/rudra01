# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Bot Configuration"""

    # Telegram API
    API_ID = int(os.getenv("API_ID", 0))
    API_HASH = os.getenv("API_HASH", "")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    
    # ✅ Multiple Userbot Sessions (Optional)
    SESSION = os.getenv("SESSION", "")
    SESSION1 = os.getenv("SESSION1", "")
    SESSION2 = os.getenv("SESSION2", "")
    SESSION3 = os.getenv("SESSION3", "")
    
    # Owner & Logger
    OWNER_ID = int(os.getenv("OWNER_ID", 0))
    LOGGER_ID = int(os.getenv("LOGGER_ID", 0))
    
    # Database
    MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    
    # Redis Cache
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # YouTube & Download
    BASE_URL = os.getenv("BASE_URL", "https://api.babyapi.pro")
    API_KEY = os.getenv("API_KEY", "babyapi")
    CACHE_CHANNEL = int(os.getenv("CACHE_CHANNEL", LOGGER_ID)) if os.getenv("CACHE_CHANNEL") else 0
    
    # Music Settings
    DURATION_LIMIT = int(os.getenv("DURATION_LIMIT", 14400))  # 4 hours
    PLAYLIST_LIMIT = int(os.getenv("PLAYLIST_LIMIT", 50))
    QUEUE_LIMIT = int(os.getenv("QUEUE_LIMIT", 500))
    
    # Support
    SUPPORT_CHAT = os.getenv("SUPPORT_CHAT", "https://t.me/PremMusic")
    SUPPORT_CHANNEL = os.getenv("SUPPORT_CHANNEL", "https://t.me/PremMusic")
    
    # Thumbnails
    DEFAULT_THUMB = os.getenv(
        "DEFAULT_THUMB",
        "https://te.legra.ph/file/6213633868c5c81b91a73.jpg"
    )
    
    # ✅ ADD ये सब नए variables
    AUTO_END = bool(os.getenv("AUTO_END", False))
    ALLOW_USER_REQUESTS = bool(os.getenv("ALLOW_USER_REQUESTS", True))
    ENABLE_CACHE = bool(os.getenv("ENABLE_CACHE", True))
    
    # Features
    PREFIXES = ["/", "!"]
    LOAD_PLUGINS = True
    
    # Assistant Userbot Settings
    ASSISTANT_CLIENTS = int(os.getenv("ASSISTANT_CLIENTS", 1))

    def check(self):
        """Validate required configuration"""
        required = ["API_ID", "API_HASH", "BOT_TOKEN", "OWNER_ID", "LOGGER_ID"]
        missing = []
        
        for key in required:
            value = getattr(self, key, None)
            if not value:
                missing.append(key)
        
        # ✅ SESSION या SESSION1 में से कम से कम एक होना चाहिए
        if not (self.SESSION or self.SESSION1):
            missing.append("SESSION (या SESSION1)")
        
        if missing:
            from anony import logger
            logger.error(f"Missing configuration: {', '.join(missing)}")
            raise ValueError(f"Missing required config: {missing}")
        
        from anony import logger
        logger.info("✅ Configuration validated successfully")
