# Copyright (c) 2025 AnonymousX1025
# Licensed under the MIT License.
# This file is part of AnonXMusic

import os
import aiohttp
from anony import logger, config


class MusicApi:
    def __init__(self):
        self.api_key = config.API_KEY
        self.api_url = config.API_URL

    async def download_track(self, url: str) -> str | None:
        """
        Downloads a track via the configured Music API.
        Returns local file path on success, None on failure.
        """
        if not self.api_key or not self.api_url:
            return None

        try:
            params = {"url": url, "api_key": self.api_key}
            async with aiohttp.ClientSession() as session:
                async with session.get(self.api_url, params=params, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                    if resp.status != 200:
                        logger.warning("MusicApi returned status %s for %s", resp.status, url)
                        return None

                    content_disp = resp.headers.get("Content-Disposition", "")
                    filename = None

                    if "filename=" in content_disp:
                        filename = content_disp.split("filename=")[-1].strip().strip('"')

                    if not filename:
                        video_id = url.split("v=")[-1].split("&")[0]
                        filename = f"{video_id}.webm"

                    os.makedirs("downloads", exist_ok=True)
                    file_path = f"downloads/{filename}"

                    if os.path.exists(file_path):
                        return file_path

                    with open(file_path, "wb") as f:
                        async for chunk in resp.content.iter_chunked(1024 * 64):
                            f.write(chunk)

                    return file_path

        except aiohttp.ClientError as e:
            logger.warning("MusicApi request failed: %s", e)
            return None
        except Exception as e:
            logger.warning("MusicApi unexpected error: %s", e)
            return None
