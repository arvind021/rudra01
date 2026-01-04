import asyncio
import aiohttp
from pathlib import Path

from anony import logger, config


class MusicApi:
    def __init__(self, timeout: int = 15):
        self.base_url = config.API_URL.rstrip("/")
        self.api_key = config.API_KEY
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.download_dir = Path("downloads")
        self.download_dir.mkdir(exist_ok=True)

    async def download_track(self, url: str) -> str | None:
        vid = url.split("v=")[-1].split("&")[0]
        filename = self.download_dir / f"{vid}.mp3"

        if filename.exists():
            return str(filename)

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(
                f"{self.base_url}/api/song?query={vid}&api={self.api_key}"
            ) as resp:
                if resp.status != 200:
                    return None
                res = await resp.json(content_type=None)

            stream = res.get("stream")
            if not stream:
                return None

            for _ in range(60):
                async with session.get(stream) as r:
                    if r.status == 200:
                        with open(filename, "wb") as f:
                            async for chunk in r.content.iter_chunked(32 * 1024):
                                if chunk:
                                    f.write(chunk)
                        return str(filename)

                    if r.status in (202, 204, 404):
                        await asyncio.sleep(2)
                        continue

                    return None

        return None