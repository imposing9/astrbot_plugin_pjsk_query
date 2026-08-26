"""Haruki Project SEKAI master-data client."""

from __future__ import annotations

import asyncio
import time
from typing import Any
from urllib.parse import quote

import aiohttp


HARUKI_CDN = "https://sekai-master-cdn.haruki.seiunx.com"
HARUKI_EVENT_TRACKER = "https://toolbox-api-direct.haruki.seiunx.com/event-tracker"
HARUKI_SEKAI_API = "http://127.0.0.1:9999"
HARUKI_REPOSITORIES = {
    "jp": "haruki-sekai-master",
    "en": "haruki-sekai-en-master",
    "tw": "haruki-sekai-tc-master",
    "kr": "haruki-sekai-kr-master",
    "cn": "haruki-sekai-sc-master",
}


class PJSKDataClient:
    """Fetch versioned master data from Haruki Dev Team's public CDN."""

    def __init__(
        self,
        cdn_url: str = HARUKI_CDN,
        region: str = "cn",
        timeout: int = 15,
        cache_ttl: int = 1800,
        event_tracker_url: str = HARUKI_EVENT_TRACKER,
        sekai_api_url: str = HARUKI_SEKAI_API,
    ):
        self.cdn_url = (cdn_url or HARUKI_CDN).rstrip("/")
        self.event_tracker_url = (event_tracker_url or HARUKI_EVENT_TRACKER).rstrip("/")
        self.sekai_api_url = (sekai_api_url or HARUKI_SEKAI_API).rstrip("/")
        self.region = region if region in HARUKI_REPOSITORIES else "cn"
        self.timeout = aiohttp.ClientTimeout(total=max(timeout, 1))
        self.cache_ttl = max(cache_ttl, 0)
        self._cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._version: tuple[float, dict[str, str]] | None = None
        self._version_lock = asyncio.Lock()

    @property
    def repository(self) -> str:
        return HARUKI_REPOSITORIES[self.region]

    def _prefix(self) -> str:
        """Return the base that already contains the region repository path if needed.

        The default data_source is a CDN root (``.../haruki-sekai-sc-master`` is
        appended automatically), while raw GitHub URLs already include the full
        ``<owner>/<repository>/<branch>`` path and must not be duplicated.
        """
        if "raw.githubusercontent.com" in self.cdn_url:
            return self.cdn_url
        return f"{self.cdn_url}/{self.repository}"

    async def _get_version(self, session: aiohttp.ClientSession) -> dict[str, str]:
        now = time.monotonic()
        if self._version and now - self._version[0] < self.cache_ttl:
            return self._version[1]

        async with self._version_lock:
            now = time.monotonic()
            if self._version and now - self._version[0] < self.cache_ttl:
                return self._version[1]
            url = f"{self._prefix()}/versions/current_version.json"
            async with session.get(url, params={"t": str(time.time_ns())}) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
            if not isinstance(payload, dict):
                raise ValueError("Haruki 版本接口返回了无效数据")
            data_version = str(payload.get("dataVersion", "")).strip()
            cdn_version = str(payload.get("cdnVersion", "")).strip()
            version = cdn_version if self.region in {"cn", "tw", "kr"} and cdn_version else data_version
            if not version:
                raise ValueError("Haruki 版本接口缺少 dataVersion/cdnVersion")
            result = {"version": version, "data_version": data_version, "cdn_version": cdn_version}
            self._version = (time.monotonic(), result)
            return result

    async def table(self, name: str) -> list[dict[str, Any]]:
        now = time.monotonic()
        cached = self._cache.get(name)
        if cached and now - cached[0] < self.cache_ttl:
            return cached[1]

        lock = self._locks.setdefault(name, asyncio.Lock())
        async with lock:
            cached = self._cache.get(name)
            if cached and time.monotonic() - cached[0] < self.cache_ttl:
                return cached[1]
            headers = {
                "Accept": "application/json",
                "User-Agent": "astrbot-plugin-pjsk-query/1.0",
            }
            async with aiohttp.ClientSession(timeout=self.timeout, headers=headers) as session:
                version = await self._get_version(session)
                url = f"{self._prefix()}/master/{quote(name, safe='')}.json"
                async with session.get(url, params={"version": version["version"]}) as response:
                    response.raise_for_status()
                    payload = await response.json(content_type=None)
            if not isinstance(payload, list):
                raise ValueError(f"数据表 {name} 的格式不是列表")
            self._cache[name] = (time.monotonic(), payload)
            return payload

    async def player_profile(self, player_id: str, server: str = "cn") -> dict[str, Any]:
        """Query a player profile through Haruki-Sekai-API."""
        server = server.lower() if server.lower() in HARUKI_REPOSITORIES else "cn"
        if not self.sekai_api_url:
            raise ValueError("未配置 sekai_api_url")
        url = f"{self.sekai_api_url}/api/{server}/{player_id}/profile"
        headers = {"Accept": "application/json", "User-Agent": "astrbot-plugin-pjsk-query/1.0"}
        async with aiohttp.ClientSession(timeout=self.timeout, headers=headers) as session:
            async with session.get(url) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        if not isinstance(payload, dict):
            raise ValueError("Haruki 玩家资料接口返回了无效数据")
        return payload

    async def event_overview(self, event_id: int, interval: int = 3600) -> dict[str, Any]:
        """Read the public overview used by Haruki Toolbox's rank-border page."""
        if event_id <= 0:
            raise ValueError("活动 ID 必须为正整数")
        url = (
            f"{self.event_tracker_url}/api/v2/web/events/{self.region}/"
            f"{event_id}/leaderboards/total/overview"
        )
        headers = {"Accept": "application/json", "User-Agent": "astrbot-plugin-pjsk-query/1.0"}
        async with aiohttp.ClientSession(timeout=self.timeout, headers=headers) as session:
            async with session.get(url, params={"interval": str(max(interval, 1))}) as response:
                response.raise_for_status()
                payload = await response.json(content_type=None)
        if not isinstance(payload, dict):
            raise ValueError("Haruki 榜线接口返回了无效数据")
        return payload
