# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic

import os
import re
import yt_dlp
import random
import asyncio
import aiohttp
from pathlib import Path

from py_yt import Playlist, VideosSearch

from anony import config
from anony.helpers import Track, utils

BASE_URL = config.BASE_URL
API_KEY = config.API_KEY

async def _download_media(link: str, kind: str, exts: list[str], wait: int = 100):
    vid = link.split("v=")[-1].split("&")[0]
    os.makedirs("downloads", exist_ok=True)
    for ext in exts:
        path = f"downloads/{vid}.{ext}"
        if os.path.exists(path):
            return path
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{BASE_URL}/api/{kind}?query={vid}&eq=pro&api={API_KEY}"
            ) as resp:
                res = await resp.json()
            stream = res.get("stream")
            media_type = res.get("type")
            if not stream:
                raise Exception(f"{kind} stream not found")
            if media_type == "live":
                return stream
            for _ in range(wait):
                async with session.get(stream) as r:
                    if r.status == 200:
                        return stream
                    if r.status in (423, 404, 410):
                        await asyncio.sleep(2)
                        continue
                    if r.status in (401, 403, 429):
                        txt = await r.text()
                        raise Exception(
                            f"{kind} blocked {r.status}: {txt[:100]}"
                        )
                    raise Exception(f"{kind} failed ({r.status})")
            raise Exception(f"{kind} processing timeout")
    except Exception:
        raise

async def download_song(link: str):
    return await _download_media(link, "song", ["mp3", "m4a", "webm"], wait=60)

async def download_video(link: str):
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
            return None
        return random.choice(self.cookies)

    async def save_cookies(self, urls: list[str]) -> None:
        async with aiohttp.ClientSession() as session:
            for i, url in enumerate(urls):
                path = f"{self.cookie_dir}/cookie_{i}.txt"
                link = url.replace("me/", "me/raw/")
                async with session.get(link) as resp:
                    resp.raise_for_status()
                    with open(path, "wb") as fw:
                        fw.write(await resp.read())

    def valid(self, url: str) -> bool:
        return bool(re.match(self.regex, url))

    async def search(self, query: str, m_id: int, video: bool = False) -> Track | None:
        _search = VideosSearch(query, limit=1, with_live=False)
        results = await _search.next()
        if results and results["result"]:
            data = results["result"][0]
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
        try:
            if not video:
                file_path = await download_song(url)
            else:
                file_path = await download_video(url)

            if file_path:
                return file_path
        except Exception:
            pass

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
                "format": "(bestvideo[height<=?720][ext=mp4])+(bestaudio)",
                "merge_output_format": "mp4",
            }
        else:
            ydl_opts = {
                **base_opts,
                "format": "bestaudio[ext=webm][acodec=opus]",
            }
        def _download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                try:
                    ydl.download([url])
                except (yt_dlp.utils.DownloadError, yt_dlp.utils.ExtractorError):
                    if cookie:
                        self.cookies.remove(cookie)
                    return None
                except Exception:
                    return None
            return filename

        result = await asyncio.to_thread(_download)
        return result
