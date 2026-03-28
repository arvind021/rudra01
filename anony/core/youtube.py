# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic

import os
import re
import yt_dlp
import random
import asyncio
import aiohttp
import logging
from pathlib import Path

from py_yt import Playlist, VideosSearch

from anony import config
from anony.helpers import Track, utils

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
asyncio.get_event_loop().set_debug(True)  # Debug asyncio

BASE_URL = config.BASE_URL
API_KEY = config.API_KEY

async def _download_media(link: str, kind: str, exts: list[str], wait: int = 100):
    vid = link.split("v=")[-1].split("&")[0]
    logger.debug(f"Starting _download_media for {kind}: vid={vid}, exts={exts}")
    
    os.makedirs("downloads", exist_ok=True)
    for ext in exts:
        path = f"downloads/{vid}.{ext}"
        if os.path.exists(path):
            logger.info(f"Found existing file: {path}")
            return path
    
    try:
        logger.debug(f"Fetching from API: {BASE_URL}/api/{kind}?query={vid}&eq=pro&api={API_KEY}")
        async with aiohttp.ClientSession() as session:
            # Add trace config for aiohttp debugging
            trace_config = aiohttp.TraceConfig()
            trace_config.on_request_start.append(
                lambda *args: logger.debug(f"AIOHTTP request start: {args}")
            )
            trace_config.on_request_end.append(
                lambda *args: logger.debug(f"AIOHTTP request end: {args}")
            )
            session_tracer = aiohttp.TraceConfig()
            session_tracer.on_request_start.append(
                lambda session, ctx, params: logger.debug(f'Starting {kind} request {params.method} {params.url}')
            )
            session_tracer.on_request_end.append(
                lambda session, ctx, response: logger.debug(f'Ended {kind} request {response.status}')
            )
            
            async with aiohttp.ClientSession(trace_configs=[session_tracer]) as session:
                async with session.get(
                    f"{BASE_URL}/api/{kind}?query={vid}&eq=pro&api={API_KEY}"
                ) as resp:
                    logger.debug(f"API response status: {resp.status}")
                    res = await resp.json()
                    logger.debug(f"API response: {res}")
                    
            stream = res.get("stream")
            media_type = res.get("type")
            logger.debug(f"Stream: {stream}, Type: {media_type}")
            
            if not stream:
                logger.error(f"{kind} stream not found in response")
                raise Exception(f"{kind} stream not found")
                
            if media_type == "live":
                logger.info(f"Live stream detected: {stream}")
                return stream
                
            logger.info(f"Waiting for {kind} processing, max {wait} attempts")
            for attempt in range(wait):
                logger.debug(f"Attempt {attempt + 1}/{wait} for stream availability")
                async with session.get(stream) as r:
                    logger.debug(f"Stream check status: {r.status}")
                    if r.status == 200:
                        logger.info(f"Stream ready after {attempt + 1} attempts")
                        return stream
                    if r.status in (423, 404, 410):
                        await asyncio.sleep(2)
                        continue
                    if r.status in (401, 403, 429):
                        txt = await r.text()
                        logger.error(f"{kind} blocked {r.status}: {txt[:100]}")
                        raise Exception(f"{kind} blocked {r.status}: {txt[:100]}")
                    logger.warning(f"{kind} failed ({r.status}) on attempt {attempt + 1}")
                    raise Exception(f"{kind} failed ({r.status})")
            logger.error(f"{kind} processing timeout after {wait} attempts")
            raise Exception(f"{kind} processing timeout")
    except Exception as e:
        logger.exception(f"Exception in _download_media for {kind}: {e}")
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
            r"(https?://)?(www.|m.|music.)?"
            r"(youtube.com/(watch?v=|shorts/|playlist?list=)|youtu.be/)"
            r"([A-Za-z0-9_-]{11}|PL[A-Za-z0-9_-]+)([&?][^s]*)?"
        )
        logger.info("YouTube class initialized")

    def get_cookies(self):
        if not self.checked:
            logger.debug(f"Checking cookies in {self.cookie_dir}")
            if os.path.exists(self.cookie_dir):
                for file in os.listdir(self.cookie_dir):
                    if file.endswith(".txt"):
                        self.cookies.append(f"{self.cookie_dir}/{file}")
            self.checked = True
            logger.info(f"Found {len(self.cookies)} cookie files")
        if not self.cookies:
            if not self.warned:
                logger.warning("No cookies available")
                self.warned = True
            return None
        cookie = random.choice(self.cookies)
        logger.debug(f"Selected cookie: {cookie}")
        return cookie

    async def save_cookies(self, urls: list[str]) -> None:
        logger.info(f"Saving {len(urls)} cookies")
        async with aiohttp.ClientSession() as session:
            for i, url in enumerate(urls):
                path = f"{self.cookie_dir}/cookie_{i}.txt"
                link = url.replace("me/", "me/raw/")
                logger.debug(f"Downloading cookie {i}: {link} -> {path}")
                async with session.get(link) as resp:
                    resp.raise_for_status()
                    with open(path, "wb") as fw:
                        content = await resp.read()
                        fw.write(content)
                        logger.info(f"Saved cookie {path} ({len(content)} bytes)")

    def valid(self, url: str) -> bool:
        is_valid = bool(re.match(self.regex, url))
        logger.debug(f"URL valid check '{url}': {is_valid}")
        return is_valid

    async def search(self, query: str, m_id: int, video: bool = False) -> Track | None:
        logger.info(f"Searching YouTube: '{query}', video={video}")
        try:
            _search = VideosSearch(query, limit=1, with_live=False)
            results = await _search.next()
            logger.debug(f"Search results: {results}")
            if results and results["result"]:
                data = results["result"][0]
                logger.info(f"Found track: {data.get('title')[:50]}")
                track = Track(
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
                return track
            logger.warning("No search results found")
        except Exception as e:
            logger.exception(f"Search error: {e}")
        return None

    async def playlist(self, limit: int, user: str, url: str, video: bool) -> list[Track | None]:
        logger.info(f"Fetching playlist: {url} limit={limit}")
        tracks = []
        try:
            plist = await Playlist.get(url)
            logger.debug(f"Playlist data: {len(plist.get('videos', []))} videos")
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
                logger.debug(f"Added track: {track.title}")
        except Exception as e:
            logger.exception(f"Playlist fetch error: {e}")
        logger.info(f"Playlist returned {len(tracks)} tracks")
        return tracks

    async def download(self, video_id: str, video: bool = False) -> str | None:
        url = self.base + video_id
        logger.info(f"Downloading { 'video' if video else 'audio' }: {video_id}")
        
        try:
            if not video:
                file_path = await download_song(url)
            else:
                file_path = await download_video(url)
            if file_path:
                logger.info(f"Downloaded via API: {file_path}")
                return file_path
        except Exception as e:
            logger.warning(f"API download failed, falling back to yt-dlp: {e}")

        ext = "mp4" if video else "webm"
        filename = f"downloads/{video_id}.{ext}"
        if Path(filename).exists():
            logger.info(f"Found existing fallback file: {filename}")
            return filename
            
        cookie = self.get_cookies()
        base_opts = {
            "outtmpl": "downloads/%(id)s.%(ext)s",
            "quiet": False,  # Changed to False for verbose yt-dlp output
            "noplaylist": True,
            "geo_bypass": True,
            "no_warnings": False,  # Show warnings
            "overwrites": False,
            "nocheckcertificate": True,
            "cookiefile": cookie,
            "verbose": True,  # Enable yt-dlp verbose logging
        }
        if video:
            ydl_opts = {
                **base_opts,
                "format": "(bestvideo[height<=?720][ext=mp4])+(bestaudio)",
                "merge_output_format": "mp4",
            }
        else:
            ydl_opts = {
                **base_opts,
                "format": "bestaudio[ext=webm][acodec=opus]",
            }
        
        def _download():
            try:
                logger.info(f"Starting yt-dlp download with opts: {ydl_opts}")
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                logger.info(f"yt-dlp download completed: {filename}")
                return filename
            except yt_dlp.utils.DownloadError as e:
                logger.error(f"yt-dlp DownloadError: {e}")
                if cookie:
                    logger.warning(f"Removing bad cookie: {cookie}")
                    self.cookies = [c for c in self.cookies if c != cookie]
                return None
            except Exception as e:
                logger.exception(f"yt-dlp unexpected error: {e}")
                return None

        result = await asyncio.to_thread(_download)
        return result
