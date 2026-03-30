# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic

import os
import re
import yt_dlp
import random
import asyncio
import aiohttp
import aioredis
from pathlib import Path

from py_yt import Playlist, VideosSearch

from anony import logger, config
from anony.helpers import Track, utils

BASE_URL = config.BASE_URL
API_KEY = config.API_KEY
CACHE_CHANNEL = config.CACHE_CHANNEL

# In-memory cache for ultra-fast playback
_mem_cache: dict = {}


async def _download_media(link: str, kind: str, exts: list[str], wait: int = 60):
    vid = link.split("v=")[-1].split("&")[0]
    os.makedirs("downloads", exist_ok=True)

    # Return if already downloaded
    for ext in exts:
        path = f"downloads/{vid}.{ext}"
        if os.path.exists(path):
            logger.info(f"Found existing file: {path}")
            return path

    try:
        async with aiohttp.ClientSession() as session:
            # Step 1: Get stream URL from API
            api_url = f"{BASE_URL}/api/{kind}?query={vid}&eq=pro&api={API_KEY}"
            async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status != 200:
                    raise Exception(f"API returned {resp.status}")
                res = await resp.json()

            stream = res.get("stream")
            media_type = res.get("type")

            if not stream:
                raise Exception(f"{kind} stream not found in API response")

            # Step 2: Live stream - return URL directly
            if media_type == "live":
                return stream

            # Step 3: Wait for stream to be ready, then download file
            logger.info(f"Waiting for {kind} to be ready...")
            for attempt in range(wait):
                async with session.get(stream, timeout=aiohttp.ClientTimeout(total=60)) as r:
                    if r.status == 200:
                        # Determine file extension from content-type
                        content_type = r.headers.get("Content-Type", "")
                        if "mp4" in content_type:
                            ext = "mp4"
                        elif "webm" in content_type:
                            ext = "webm"
                        elif "mpeg" in content_type or "mp3" in content_type:
                            ext = "mp3"
                        elif "m4a" in content_type or "mp4a" in content_type:
                            ext = "m4a"
                        else:
                            ext = exts[0]

                        file_path = f"downloads/{vid}.{ext}"

                        # Download the actual file
                        logger.info(f"Downloading {kind} to {file_path}...")
                        with open(file_path, "wb") as f:
                            async for chunk in r.content.iter_chunked(1024 * 64):
                                f.write(chunk)

                        if os.path.getsize(file_path) < 1000:
                            os.remove(file_path)
                            raise Exception("Downloaded file too small, likely invalid")

                        logger.info(f"Downloaded via API: {file_path}")
                        return file_path

                    elif r.status in (423, 404, 410):
                        await asyncio.sleep(2)
                        continue
                    elif r.status in (401, 403, 429):
                        txt = await r.text()
                        raise Exception(f"{kind} blocked {r.status}: {txt[:100]}")
                    else:
                        raise Exception(f"{kind} failed ({r.status})")

            raise Exception(f"{kind} processing timeout after {wait} attempts")

    except Exception as e:
        logger.warning(f"API download failed for {kind}: {e}")
        raise


async def download_song(link: str):
    logger.info(f"Downloading song: {link}")
    return await _download_media(link, "song", ["mp3", "m4a", "webm"], wait=60)


async def download_video(link: str):
    logger.info(f"Downloading video: {link}")
    return await _download_media(link, "video", ["mp4", "webm", "mkv"], wait=90)


class YouTube:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.cookies = []
        self.checked = False
        self.cookie_dir = "anony/cookies"
        self.warned = False
        self.regex = re.compile(
            r"(https?://)?(www\.|m\.|music\.)?"
            r"(youtube\.com/(watch\?v=|shorts/|playlist\?list=)|youtu\.be/)"
            r"([A-Za-z0-9_-]{11}|PL[A-Za-z0-9_-]+)([&?][^\s]*)?"
        )

    def get_cookies(self):
        if not self.checked:
            for file in os.listdir(self.cookie_dir):
                if file.endswith(".txt"):
                    self.cookies.append(f"{self.cookie_dir}/{file}")
            self.checked = True
        if not self.cookies:
            if not self.warned:
                self.warned = True
                logger.warning("Cookies are missing; downloads might fail.")
            return None
        return random.choice(self.cookies)

    async def save_cookies(self, urls: list[str]) -> None:
        logger.info("Saving cookies from urls...")
        async with aiohttp.ClientSession() as session:
            for i, url in enumerate(urls):
                path = f"{self.cookie_dir}/cookie_{i}.txt"
                link = url.replace("me/", "me/raw/")
                async with session.get(link) as resp:
                    resp.raise_for_status()
                    with open(path, "wb") as fw:
                        fw.write(await resp.read())
        logger.info(f"Cookies saved in {self.cookie_dir}.")

    def valid(self, url: str) -> bool:
        return bool(re.match(self.regex, url))

    async def search(self, query: str, m_id: int, video: bool = False) -> Track | None:
        logger.info(f"Searching YouTube: '{query}', video={video}")
        _search = VideosSearch(query, limit=1, with_live=False)
        results = await _search.next()
        if results and results["result"]:
            data = results["result"][0]
            logger.info(f"Found track: {data.get('title')[:50]}")
            return Track(
                id=data.get("id"),
                channel_name=data.get("channel", {}).get("name"),
                duration=data.get("duration"),
                duration_sec=utils.to_seconds(data.get("duration")),
                message_id=m_id,
                title=data.get("title")[:25],
                thumbnail=data.get("thumbnails", [{}])[-1].get("url").split("?")[0],
                url=data.get("link"),
                view_count=data.get("viewCount", {}).get("short"),
                video=video,
            )
        return None

    async def playlist(self, limit: int, user: str, url: str, video: bool) -> list[Track | None]:
        tracks = []
        try:
            plist = await Playlist.get(url)
            for data in plist["videos"][:limit]:
                track = Track(
                    id=data.get("id"),
                    channel_name=data.get("channel", {}).get("name", ""),
                    duration=data.get("duration"),
                    duration_sec=utils.to_seconds(data.get("duration")),
                    title=data.get("title")[:25],
                    thumbnail=data.get("thumbnails")[-1].get("url").split("?")[0],
                    url=data.get("link").split("&list=")[0],
                    user=user,
                    view_count="",
                    video=video,
                )
                tracks.append(track)
        except:
            pass
        return tracks

    async def download(self, video_id: str, video: bool = False) -> str | None:
        url = self.base + video_id
        logger.info(f"Downloading {'video' if video else 'audio'}: {video_id}")

        # Try API first
        try:
            if not video:
                file_path = await download_song(url)
            else:
                file_path = await download_video(url)
            if file_path:
                return file_path
        except Exception as e:
            logger.warning(f"API download failed, falling back to yt-dlp: {e}")

        # Fallback: yt-dlp
        ext = "mp4" if video else "webm"
        filename = f"downloads/{video_id}.{ext}"
        if Path(filename).exists():
            return filename

        cookie = self.get_cookies()
        base_opts = {
            "outtmpl": "downloads/%(id)s.%(ext)s",
            "quiet": True,
            "noplaylist": True,
            "geo_bypass": True,
            "no_warnings": True,
            "overwrites": False,
            "nocheckcertificate": True,
            "cookiefile": cookie,
        }

        if video:
            ydl_opts = {
                **base_opts,
                "format": "(bestvideo[height<=?720][ext=mp4])+(bestaudio[ext=m4a])/bestvideo+bestaudio/best",
                "merge_output_format": "mp4",
            }
        else:
            ydl_opts = {
                **base_opts,
                "format": "bestaudio/best",
                "extractor_args": {"youtube": {"player_client": ["android_vr"]}},
                "http_headers": {"User-Agent": "com.google.android.youtube/"},
            }

        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    ydl.download([url])
                    return filename
                except (yt_dlp.utils.DownloadError, yt_dlp.utils.ExtractorError) as e:
                    logger.error(f"yt-dlp DownloadError: {e}")
                    if cookie:
                        self.cookies = [c for c in self.cookies if c != cookie]
                    return None
                except Exception as e:
                    logger.warning(f"yt-dlp unexpected error: {e}")
                    return None

        return await asyncio.to_thread(_download)

    async def _tg_cache_get(self, video_id: str) -> str | None:
        """Get cached file_id from Redis (tg cache)"""
        try:
            redis = aioredis.from_url("redis://localhost")
            cached = await redis.get(f"tg:{video_id}")
            await redis.close()
            if cached:
                logger.info(f"Telegram cache hit: {video_id}")
                return cached.decode()
        except Exception:
            pass
        return None

    async def _tg_cache_set(self, video_id: str, file_id: str) -> None:
        """Save file_id to Redis (tg cache)"""
        try:
            redis = aioredis.from_url("redis://localhost")
            await redis.set(f"tg:{video_id}", file_id)
            await redis.close()
        except Exception:
            pass

    async def get_stream_url(self, video_id: str, video: bool = False) -> str | None:
        kind = "video" if video else "song"
        cache_key = f"stream:{kind}:{video_id}"
        # Check local file first (fastest)
        for ext in ["mp3", "m4a", "webm", "mp4"]:
            path = f"downloads/{video_id}.{ext}"
            if os.path.exists(path):
                logger.info(f"Local file hit: {path}")
                return path
        # Memory cache check (fastest)
        if cache_key in _mem_cache:
            logger.info(f"Memory cache hit: {video_id}")
            return _mem_cache[cache_key]
        try:
            redis = aioredis.from_url("redis://localhost")
            cached = await redis.get(cache_key)
            await redis.close()
            if cached:
                _mem_cache[cache_key] = cached.decode()
                logger.info(f"Redis cache hit: {video_id}")
                return cached.decode()
        except Exception:
            pass
        try:
            async with aiohttp.ClientSession() as session:
                async def _fetch():
                    api_url = f"{BASE_URL}/api/{kind}?query={video_id}&eq=pro&api={API_KEY}"
                    async with session.get(api_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                        if resp.status != 200:
                            return None
                        res = await resp.json()
                        return res.get("stream")
                streams = await asyncio.gather(_fetch(), _fetch(), _fetch(), return_exceptions=True)
                stream = next((s for s in streams if isinstance(s, str) and s), None)
                if not stream:
                    return None
                for _ in range(30):
                    async with session.get(stream, timeout=aiohttp.ClientTimeout(total=10)) as r:
                        if r.status == 200:
                            _mem_cache[cache_key] = stream
                            try:
                                redis = aioredis.from_url("redis://localhost")
                                await redis.setex(cache_key, 3600, stream)
                                await redis.close()
                                logger.info(f"Redis cached: {video_id}")
                            except Exception:
                                pass
                            return stream
                        elif r.status in (423, 404, 410):
                            await asyncio.sleep(0.5)
                            continue
                        else:
                            return None
                return None
        except Exception as e:
            logger.warning(f"get_stream_url failed: {e}")
            return None
