"""AstrBot entry point for Project SEKAI game-data queries."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Image, Node, Nodes, Plain
from astrbot.api.star import Context, Star

from .client import PJSKDataClient
from .formatters import (
    card_image_url,
    card_text,
    chart_text,
    choose_music,
    event_text,
    music_text,
    search,
    value,
)

HELP_TEXT = (
    "世界计划：缤纷舞台查询\n"
    "查卡 <关键词>｜查角色 <关键词>｜查曲 <关键词>\n"
    "查谱面 <歌曲 ID 或关键词>｜查活动 <关键词>\n"
    "当前活动｜查榜线 [档位] [间隔]｜查活动榜线 <活动> [档位] [间隔]\n"
    "查玩家 <玩家ID> [服务器]｜绑定玩家 <玩家ID> [服务器]\n"
    "解除绑定 [服务器或序号]｜玩家状态 [序号或服务器]\n"
    "随机曲 [关键词]\n"
    "数据来自 Haruki Dev Team 公开主数据；默认查询简中服。"
)

HELP_TEMPLATE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: "Microsoft YaHei", "PingFang SC", "Segoe UI", sans-serif;
    background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
    color: #f8fafc;
    padding: 32px;
  }
  .card {
    max-width: 780px;
    margin: 0 auto;
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 20px;
    padding: 28px 30px;
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.35);
  }
  .title { font-size: 30px; font-weight: 800; color: #fff; }
  .subtitle { margin-top: 4px; font-size: 14px; color: #94a3b8; }
  .divider {
    height: 2px;
    margin: 18px 0;
    background: linear-gradient(90deg, #38bdf8, #a78bfa);
    border-radius: 2px;
  }
  .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .cmd {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 12px 14px;
  }
  .cmd-name { font-size: 16px; font-weight: 700; color: #7dd3fc; }
  .cmd-desc { margin-top: 4px; font-size: 13px; color: #cbd5e1; line-height: 1.5; }
  .cmd-example {
    margin-top: 6px;
    font-size: 12px;
    color: #94a3b8;
    font-family: Consolas, "Courier New", monospace;
  }
  .footer { margin-top: 20px; text-align: center; font-size: 12px; color: #64748b; }
</style>
</head>
<body>
<div class="card">
  <div class="title">世界计划：缤纷舞台查询</div>
  <div class="subtitle">Project SEKAI · Haruki 公开主数据 · 默认查询简中服</div>
  <div class="divider"></div>
  <div class="grid">
    {% for cmd in commands %}
    <div class="cmd">
      <div class="cmd-name">{{ cmd.name }}</div>
      <div class="cmd-desc">{{ cmd.desc }}</div>
      {% if cmd.example %}<div class="cmd-example">{{ cmd.example }}</div>{% endif %}
    </div>
    {% endfor %}
  </div>
  <div class="footer">数据来自 Haruki Dev Team 公开主数据</div>
</div>
</body>
</html>
"""


def _command_pattern(*names: str) -> str:
    """Build a regex that matches a command prefix without requiring '@'."""
    return r"^\s*(?:" + "|".join(re.escape(name) for name in names) + r")(?:\s+.*)?$"


class PJSKQueryPlugin(Star):
    """世界计划：缤纷舞台公开主数据查询。"""

    def __init__(self, context: Context, config: dict[str, Any] | None = None):
        super().__init__(context)
        self.config = config or {}
        self.limit = max(int(self.config.get("result_limit", 5)), 1)
        self.group_whitelist = [
            str(item) for item in (self.config.get("group_whitelist", []) or [])
        ]
        self.enable_player_commands = bool(self.config.get("enable_player_commands", False))
        self.bindings_path = Path(__file__).resolve().parent / "data" / "player_bindings.json"
        self.player_bindings = self._load_bindings()
        self.client = PJSKDataClient(
            self.config.get(
                "data_source",
                "https://sekai-master-cdn.haruki.seiunx.com",
            ),
            self.config.get("region", "cn"),
            int(self.config.get("request_timeout", 15)),
            int(self.config.get("cache_ttl", 1800)),
            self.config.get("event_tracker_url", "https://toolbox-api-direct.haruki.seiunx.com/event-tracker"),
            self.config.get("sekai_api_url", "http://127.0.0.1:9999"),
        )

    def _group_allowed(self, event: AstrMessageEvent) -> bool:
        """Return False when the group is not in group_whitelist (if configured)."""
        if not self.group_whitelist:
            return True
        group_id = event.get_group_id()
        if group_id is None:
            return True
        return str(group_id) in self.group_whitelist

    @staticmethod
    def _extract_arg(event: AstrMessageEvent, *names: str) -> str | None:
        """Extract the argument after a command prefix from a raw message.

        Returns None if the message does not start with any of the given names.
        """
        text = event.message_str.strip()
        for name in names:
            if text == name:
                return ""
            if text.startswith(name + " "):
                return text[len(name):].strip()
        return None

    def _load_bindings(self) -> dict[str, list[dict[str, Any]]]:
        try:
            if self.bindings_path.exists():
                data = json.loads(self.bindings_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
        except Exception as exc:
            logger.warning("PJSK 读取玩家绑定失败: %s", exc)
        return {}

    def _save_bindings(self) -> None:
        try:
            self.bindings_path.parent.mkdir(parents=True, exist_ok=True)
            self.bindings_path.write_text(
                json.dumps(self.player_bindings, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("PJSK 保存玩家绑定失败: %s", exc)

    def _user_bindings(self, sender_id: Any) -> list[dict[str, Any]]:
        key = str(sender_id)
        return self.player_bindings.setdefault(key, [])

    @staticmethod
    def _profile_value(data: Any, *keys: str) -> Any:
        if isinstance(data, dict):
            for key in keys:
                value = data.get(key)
                if value not in (None, ""):
                    return value
            for value in data.values():
                if isinstance(value, dict):
                    for key in keys:
                        inner = value.get(key)
                        if inner not in (None, ""):
                            return inner
        return "-"

    @staticmethod
    def _format_player_profile(profile: dict[str, Any], player_id: str, server: str) -> str:
        name = PJSKQueryPlugin._profile_value(
            profile, "userName", "name", "nickname", "playerName", "userProfileName"
        )
        user_id = PJSKQueryPlugin._profile_value(profile, "userId", "user_id", "id")
        rank = PJSKQueryPlugin._profile_value(
            profile, "rank", "userRank", "playerRank", "currentRank"
        )
        level = PJSKQueryPlugin._profile_value(
            profile, "level", "userLevel", "playerLevel"
        )
        profile_word = PJSKQueryPlugin._profile_value(
            profile, "profileWord", "userProfileWord", "profile", "signature"
        )
        lines = [
            f"【{name or '玩家'}】",
            f"服务器：{server.upper()}  玩家ID：{user_id if user_id != '-' else player_id}",
        ]
        if rank != "-":
            lines.append(f"排名：{rank}")
        if level != "-":
            lines.append(f"等级：{level}")
        if profile_word != "-":
            lines.append(f"签名：{profile_word}")
        return "\n".join(lines)

    async def _table(self, name: str) -> list[dict[str, Any]]:
        try:
            return await self.client.table(name)
        except Exception as exc:
            logger.warning("PJSK 数据请求失败 (%s): %s", name, exc)
            raise RuntimeError(
                f"无法访问 Haruki 主数据 CDN（数据表 {name}：{exc}）。"
                "请检查服务器能否访问 sekai-master-cdn.haruki.seiunx.com，"
                "或检查插件的 data_source 配置。"
            ) from exc

    @filter.regex(_command_pattern("pjsk帮助", "pjskhelp", "世界计划帮助"))
    async def help(self, event: AstrMessageEvent):
        """显示世界计划查询指令，渲染为图片卡片。"""
        if not self._group_allowed(event):
            return
        help_commands = [
            {"name": "查卡 <关键词>", "desc": "按卡牌名、ID、角色名/角色 ID 查询并返回卡图", "example": "查卡 初音"},
            {"name": "查角色 <关键词>", "desc": "按角色姓名、英文名或 ID 查询", "example": "查角色 初音未来"},
            {"name": "查曲 <关键词>", "desc": "按歌名、ID、作词、作曲、编曲查询", "example": "查曲 千本樱"},
            {"name": "查谱面 <歌曲 ID 或关键词>", "desc": "查询各难度谱面等级与物量", "example": "查谱面 1"},
            {"name": "查活动 <关键词>", "desc": "按活动名或活动 ID 查询", "example": "查活动 177"},
            {"name": "当前活动", "desc": "查询当前正在进行的活动", "example": "当前活动"},
            {"name": "查榜线 [档位] [间隔]", "desc": "查询当前活动榜线，支持 15m/1h/6h/24h", "example": "查榜线 1000 1h"},
            {"name": "查活动榜线 <活动> [档位] [间隔]", "desc": "查询指定活动的榜线", "example": "查活动榜线 177 1000 1h"},
            {"name": "查玩家 <玩家ID> [服务器]", "desc": "查询指定玩家资料", "example": "查玩家 123456 cn"},
            {"name": "绑定玩家 <玩家ID> [服务器]", "desc": "绑定本 QQ 的玩家账号", "example": "绑定玩家 123456 cn"},
            {"name": "解除绑定 [服务器或序号]", "desc": "解除已绑定的玩家", "example": "解除绑定 cn"},
            {"name": "玩家状态 [序号或服务器]", "desc": "查看已绑定玩家的状态", "example": "玩家状态 1"},
            {"name": "随机曲 [关键词]", "desc": "随机抽取一首歌曲，可按关键词筛选", "example": "随机曲 初音"},
            {"name": "pjsk帮助", "desc": "显示本帮助图片", "example": "pjsk帮助"},
        ]
        try:
            rendered = await self.html_render(
                HELP_TEMPLATE,
                {"commands": help_commands},
                return_url=False,
                options={"full_page": True, "type": "png"},
            )
            yield event.image_result(rendered)
        except Exception as exc:
            logger.warning("PJSK 帮助图片渲染失败，回退到默认文转图: %s", exc)
            try:
                image_path = await self.text_to_image(HELP_TEXT, return_url=False)
                yield event.image_result(image_path)
            except Exception as exc2:
                logger.error("PJSK 帮助图片回退失败，发送纯文本: %s", exc2)
                yield event.plain_result(HELP_TEXT)

    @filter.regex(_command_pattern("查卡", "pjsk查卡", "查卡牌"))
    async def card(self, event: AstrMessageEvent):
        """按卡牌名、卡牌 ID、角色 ID 或角色名查询卡牌。"""
        if not self._group_allowed(event):
            return
        keyword = self._extract_arg(event, "查卡", "pjsk查卡", "查卡牌") or ""
        cards, chars = await self._table("cards"), await self._table("gameCharacters")
        character_map = {int(item["id"]): item for item in chars if item.get("id") is not None}

        # 先按卡牌自身字段匹配；再按角色名/英文名匹配，返回该角色的卡牌。
        matches = search(cards, keyword, "id", "prefix", "characterId", limit=self.limit)
        character_hits = search(
            chars,
            keyword,
            "id",
            "firstName",
            "givenName",
            "name",
            "firstNameEnglish",
            "givenNameEnglish",
            limit=len(chars),
        )

        # 兼容“初音未来”“Hatsune Miku”这类完整姓名的模糊搜索。
        needle = keyword.strip().casefold()
        seen_char_ids = {str(item["id"]) for item in character_hits if item.get("id") is not None}
        for item in chars:
            item_id = str(item.get("id"))
            if item_id in seen_char_ids:
                continue
            full_name = " ".join(
                str(item.get(key, "")) for key in ("firstName", "givenName") if item.get(key)
            ).strip()
            full_name_en = " ".join(
                str(item.get(key, ""))
                for key in ("firstNameEnglish", "givenNameEnglish")
                if item.get(key)
            ).strip()
            full_name_no_space = full_name.replace(" ", "")
            full_name_en_no_space = full_name_en.replace(" ", "")
            folded = (
                full_name.casefold(),
                full_name_no_space.casefold(),
                full_name_en.casefold(),
                full_name_en_no_space.casefold(),
            )
            if any(needle in text for text in folded):
                character_hits.append(item)
                seen_char_ids.add(item_id)

        character_ids = {str(item["id"]) for item in character_hits if item.get("id") is not None}
        if character_ids:
            seen = {str(item.get("id")) for item in matches}
            for card in cards:
                if len(matches) >= self.limit:
                    break
                if str(card.get("id")) in seen:
                    continue
                if str(card.get("characterId")) in character_ids:
                    matches.append(card)
                    seen.add(str(card.get("id")))
        if not matches:
            yield event.plain_result(f"没有找到与「{keyword}」相关的卡牌。")
            return
        region = str(self.config.get("region", "cn"))
        if len(matches) > 1:
            # 合并转发：每个卡牌作为一条 Node
            self_id = event.get_self_id() or "10000"
            self_name = "世划·PJSK查询"
            nodes = []
            for item in matches:
                content: list = [Plain(text=card_text(item, character_map))]
                image_url = card_image_url(item, region)
                if image_url:
                    content.append(Image(file=image_url, url=image_url))
                nodes.append(
                    Node(
                        uin=int(self_id) if str(self_id).isdigit() else 10000,
                        name=self_name,
                        content=content,
                    )
                )
            yield event.chain_result([Nodes(nodes=nodes)])
        else:
            chain: list = []
            for item in matches:
                chain.append(Plain(text=card_text(item, character_map)))
                image_url = card_image_url(item, region)
                if image_url:
                    chain.append(Image(file=image_url, url=image_url))
            yield event.chain_result(chain)

    @filter.regex(_command_pattern("查角色", "pjsk查角色"))
    async def character(self, event: AstrMessageEvent):
        """按姓名或角色 ID 查询角色。"""
        if not self._group_allowed(event):
            return
        keyword = self._extract_arg(event, "查角色", "pjsk查角色") or ""
        characters = await self._table("gameCharacters")
        matches = search(characters, keyword, "id", "firstName", "givenName", "name", limit=self.limit)
        if not matches:
            yield event.plain_result(f"没有找到角色「{keyword}」。")
            return
        lines = []
        for item in matches:
            name = " ".join(str(item.get(key, "")) for key in ("firstName", "givenName") if item.get(key)).strip()
            lines.append(f"【{name or value(item, 'name')}】\nID：{value(item, 'id')}  单位：{value(item, 'unit')}  性别：{value(item, 'gender')}")
        yield event.plain_result("\n\n".join(lines))

    @filter.regex(_command_pattern("查曲", "pjsk查曲", "查歌"))
    async def music(self, event: AstrMessageEvent):
        """按歌名、歌曲 ID、作词、作曲或编曲查询歌曲。"""
        if not self._group_allowed(event):
            return
        keyword = self._extract_arg(event, "查曲", "pjsk查曲", "查歌") or ""
        musics = await self._table("musics")
        matches = search(musics, keyword, "id", "title", "lyricist", "composer", "arranger", limit=self.limit)
        yield event.plain_result("\n\n".join(music_text(item) for item in matches) if matches else f"没有找到歌曲「{keyword}」。")

    @filter.regex(_command_pattern("查谱面", "pjsk查谱", "查谱"))
    async def chart(self, event: AstrMessageEvent):
        """按歌曲 ID 或歌名查询各难度谱面等级与物量。"""
        if not self._group_allowed(event):
            return
        keyword = self._extract_arg(event, "查谱面", "pjsk查谱", "查谱") or ""
        musics, charts = await self._table("musics"), await self._table("musicDifficulties")
        matched_music = search(musics, keyword, "id", "title", limit=1)
        if not matched_music:
            yield event.plain_result(f"没有找到歌曲「{keyword}」。")
            return
        music = matched_music[0]
        rows = [item for item in charts if str(item.get("musicId")) == str(music.get("id"))]
        rows.sort(key=lambda item: ("easy", "normal", "hard", "expert", "master", "append").index(item.get("musicDifficulty")) if item.get("musicDifficulty") in {"easy", "normal", "hard", "expert", "master", "append"} else 99)
        yield event.plain_result(f"【{value(music, 'title')}】\n" + ("\n".join(chart_text(row) for row in rows) or "暂无谱面数据。"))

    @filter.regex(_command_pattern("查活动", "pjsk查活动"))
    async def event(self, event: AstrMessageEvent):
        """按活动名或活动 ID 查询活动。"""
        if not self._group_allowed(event):
            return
        keyword = self._extract_arg(event, "查活动", "pjsk查活动") or ""
        events = await self._table("events")
        matches = search(events, keyword, "id", "name", limit=self.limit)
        yield event.plain_result("\n\n".join(event_text(item) for item in matches) if matches else f"没有找到活动「{keyword}」。")

    @filter.regex(_command_pattern("当前活动", "pjsk当前活动"))
    async def current_event(self, event: AstrMessageEvent):
        """查询主数据镜像中当前进行的活动。"""
        if not self._group_allowed(event):
            return
        import time
        now = int(time.time() * 1000)
        events = await self._table("events")
        current = [item for item in events if int(item.get("startAt", 0)) <= now <= int(item.get("closedAt", item.get("aggregateAt", 0)) or 0)]
        yield event.plain_result("\n\n".join(event_text(item) for item in current) if current else "主数据镜像中没有进行中的活动（通常为日服时间）。")

    async def _get_current_activity(self) -> dict[str, Any] | None:
        """Return the currently ongoing event from master data, if any."""
        import time

        events = await self._table("events")
        now = int(time.time() * 1000)
        active = [
            item
            for item in events
            if int(item.get("startAt", 0))
            <= now
            <= int(item.get("closedAt", item.get("aggregateAt", 0)) or 0)
        ]
        return active[-1] if active else None

    async def _find_activity(self, keyword: str) -> dict[str, Any] | None:
        events = await self._table("events")
        matches = search(events, keyword, "id", "name", limit=1)
        return matches[0] if matches else None

    @staticmethod
    def _parse_rank_interval(parts: list[str]) -> tuple[str, int]:
        """Parse [rank] [interval] tokens for rank-border commands."""
        interval = 3600
        rank_text = ""
        for part in parts:
            low = part.lower()
            if low in {"900", "15m", "15min", "15分钟"}:
                interval = 900
            elif low in {"3600", "1h", "1hour", "1小时"}:
                interval = 3600
            elif low in {"21600", "6h", "6hour", "6小时"}:
                interval = 21600
            elif low in {"86400", "24h", "24hour", "1d", "1day", "1天", "24小时"}:
                interval = 86400
            elif not rank_text:
                rank_text = part
            else:
                raise ValueError("参数过多：榜线命令最多接受一个档位和一个间隔。")
        return rank_text, interval

    @classmethod
    def _split_event_border_args(cls, raw: str) -> tuple[str, str, int]:
        """Split a rank-border command into (event_keyword, rank_text, interval).

        The event keyword may contain spaces, so only trailing single rank/interval
        tokens are peeled off.
        """
        parts = raw.split()
        interval = 3600
        rank_text = ""
        _interval_aliases = {
            "900", "15m", "15min", "15分钟",
            "3600", "1h", "1hour", "1小时",
            "21600", "6h", "6hour", "6小时",
            "86400", "24h", "24hour", "1d", "1day", "1天", "24小时",
        }
        if len(parts) >= 2 and parts[-1].lower() in _interval_aliases:
            low = parts[-1].lower()
            if low in {"900", "15m", "15min", "15分钟"}:
                interval = 900
            elif low in {"21600", "6h", "6hour", "6小时"}:
                interval = 21600
            elif low in {"86400", "24h", "24hour", "1d", "1day", "1天", "24小时"}:
                interval = 86400
            else:
                interval = 3600
            parts = parts[:-1]
        if len(parts) >= 2:
            candidate = parts[-1].strip().lower()
            if candidate.startswith("t"):
                candidate = candidate[1:]
            if candidate.isdigit():
                rank_text = parts[-1]
                parts = parts[:-1]
        event_keyword = " ".join(parts).strip()
        return event_keyword, rank_text, interval

    def _format_rank_border(
        self,
        activity: dict[str, Any],
        overview: dict[str, Any],
        ranks: list[int],
        interval_seconds: int,
    ) -> str:
        interval_labels = {900: "15分钟", 3600: "1小时", 21600: "6小时", 86400: "1天"}
        interval_label = interval_labels.get(interval_seconds, f"{interval_seconds}秒")
        lines = {
            int(item["rank"]): item
            for item in overview.get("borderLines", [])
            if item.get("rank") is not None
        }
        growths = {
            int(item["rank"]): item
            for item in overview.get("borderGrowths", [])
            if item.get("rank") is not None
        }
        result = [f"【{value(activity, 'name')}】活动榜线（{interval_label}）"]
        for rank in ranks:
            line = lines.get(rank)
            if not line:
                result.append(f"T{rank}：暂无数据")
                continue
            growth = growths.get(rank, {})
            hourly = "-"
            if growth.get("timeDiff"):
                hourly = (
                    f"{round(int(growth.get('growth', 0)) * 3600 / int(growth['timeDiff'])):,} pt/h"
                )
            result.append(f"T{rank}：{int(line.get('score', 0)):,} pt（时速 {hourly}）")
        return "\n".join(result)

    @filter.regex(_command_pattern("查榜线", "当前榜线", "pjsk榜线", "sk线"))
    async def rank_border(self, event: AstrMessageEvent):
        """查询当前活动榜线；可选档位与间隔，如：查榜线 1000 1h。"""
        if not self._group_allowed(event):
            return
        raw = self._extract_arg(event, "查榜线", "当前榜线", "pjsk榜线", "sk线") or ""
        try:
            rank_text, interval = self._parse_rank_interval(raw.split())
        except ValueError as exc:
            yield event.plain_result(str(exc))
            return

        activity = await self._get_current_activity()
        if not activity:
            yield event.plain_result("当前没有进行中的活动，无法查询榜线。")
            return

        requested = rank_text.strip().lower().removeprefix("t")
        try:
            ranks = [int(requested)] if requested else [200, 500, 1000, 5000, 10000]
        except ValueError:
            yield event.plain_result("档位格式应为数字，例如：查榜线 1000。")
            return

        try:
            overview = await self.client.event_overview(int(activity["id"]), interval=interval)
        except Exception as exc:
            logger.warning("PJSK 榜线请求失败: %s", exc)
            yield event.plain_result("无法取得 Haruki 当前榜线数据，请稍后重试。")
            return

        yield event.plain_result(self._format_rank_border(activity, overview, ranks, interval))

    @filter.regex(_command_pattern("查活动榜线", "活动榜线", "pjsk活动榜线"))
    async def activity_rank_border(self, event: AstrMessageEvent):
        """查询指定活动的榜线；用法：查活动榜线 <活动ID或名称> [档位] [间隔]。"""
        if not self._group_allowed(event):
            return
        raw = self._extract_arg(event, "查活动榜线", "活动榜线", "pjsk活动榜线") or ""
        event_keyword, rank_text, interval = self._split_event_border_args(raw)
        if event_keyword:
            activity = await self._find_activity(event_keyword)
            if not activity:
                yield event.plain_result(f"没有找到活动「{event_keyword}」。")
                return
        else:
            activity = await self._get_current_activity()
            if not activity:
                yield event.plain_result("当前没有进行中的活动，也无法按活动查询榜线。")
                return

        requested = rank_text.strip().lower().removeprefix("t")
        try:
            ranks = [int(requested)] if requested else [200, 500, 1000, 5000, 10000]
        except ValueError:
            yield event.plain_result("档位格式应为数字，例如：查活动榜线 123 1000。")
            return

        try:
            overview = await self.client.event_overview(int(activity["id"]), interval=interval)
        except Exception as exc:
            logger.warning("PJSK 活动榜线请求失败: %s", exc)
            yield event.plain_result("无法取得 Haruki 活动榜线数据，请稍后重试。")
            return

        yield event.plain_result(self._format_rank_border(activity, overview, ranks, interval))

    @filter.regex(_command_pattern("查玩家", "pjsk查玩家"))
    async def lookup_player(self, event: AstrMessageEvent):
        """查玩家 <玩家ID> [服务器]：查询指定玩家的资料。"""
        if not self._group_allowed(event):
            return
        if not self.enable_player_commands:
            yield event.plain_result("玩家功能未开启，请在插件配置中设置 enable_player_commands 为 true。")
            return
        raw = self._extract_arg(event, "查玩家", "pjsk查玩家") or ""
        parts = raw.split()
        if not parts:
            yield event.plain_result("用法：查玩家 <玩家ID> [服务器]，例如：查玩家 123456 cn")
            return
        player_id = parts[0]
        server = parts[1] if len(parts) > 1 else str(self.config.get("region", "cn"))
        if not player_id.isdigit():
            yield event.plain_result("玩家ID应为纯数字。")
            return
        try:
            profile = await self.client.player_profile(player_id, server)
        except Exception as exc:
            logger.warning("PJSK 查询玩家失败: %s", exc)
            yield event.plain_result(f"查询玩家失败：{exc}")
            return
        yield event.plain_result(self._format_player_profile(profile, player_id, server))

    @filter.regex(_command_pattern("绑定玩家", "pjsk绑定玩家"))
    async def bind_player(self, event: AstrMessageEvent):
        """绑定玩家 <玩家ID> [服务器]：为本 QQ 保存一个玩家绑定。"""
        if not self._group_allowed(event):
            return
        if not self.enable_player_commands:
            yield event.plain_result("玩家功能未开启，请在插件配置中设置 enable_player_commands 为 true。")
            return
        raw = self._extract_arg(event, "绑定玩家", "pjsk绑定玩家") or ""
        parts = raw.split()
        if not parts:
            yield event.plain_result("用法：绑定玩家 <玩家ID> [服务器]，例如：绑定玩家 123456 cn")
            return
        player_id = parts[0]
        server = parts[1] if len(parts) > 1 else str(self.config.get("region", "cn"))
        server = server.lower() if server.lower() in {"cn", "jp", "en", "tw", "kr"} else "cn"
        if not player_id.isdigit():
            yield event.plain_result("玩家ID应为纯数字。")
            return
        bindings = self._user_bindings(event.get_sender_id())
        if any(
            str(item.get("player_id")) == player_id
            and str(item.get("server")).lower() == server
            for item in bindings
        ):
            yield event.plain_result(f"该玩家已绑定：{server.upper()} {player_id}")
            return
        bindings.append({"player_id": player_id, "server": server})
        self._save_bindings()
        yield event.plain_result(f"绑定成功：{server.upper()} 服务器，玩家ID {player_id}")

    @filter.regex(_command_pattern("解除绑定", "解绑", "pjsk解除绑定"))
    async def unbind_player(self, event: AstrMessageEvent):
        """解除绑定 [服务器或序号]：删除本 QQ 的玩家绑定。"""
        if not self._group_allowed(event):
            return
        if not self.enable_player_commands:
            yield event.plain_result("玩家功能未开启，请在插件配置中设置 enable_player_commands 为 true。")
            return
        raw = self._extract_arg(event, "解除绑定", "解绑", "pjsk解除绑定") or ""
        bindings = self._user_bindings(event.get_sender_id())
        if not bindings:
            yield event.plain_result("你还没有绑定任何玩家。")
            return
        if raw.isdigit():
            index = int(raw)
            if index < 1 or index > len(bindings):
                yield event.plain_result(f"序号无效，当前共有 {len(bindings)} 个绑定。")
                return
            removed = bindings.pop(index - 1)
            self._save_bindings()
            yield event.plain_result(
                f"已解除绑定：{removed.get('server', '').upper()} {removed.get('player_id', '')}"
            )
            return
        if raw:
            server = raw.lower() if raw.lower() in {"cn", "jp", "en", "tw", "kr"} else raw.lower()
            before = len(bindings)
            bindings[:] = [item for item in bindings if str(item.get("server")).lower() != server]
            removed_count = before - len(bindings)
            if removed_count == 0:
                yield event.plain_result(f"没有找到 {server.upper()} 服务器的绑定。")
                return
            self._save_bindings()
            yield event.plain_result(f"已解除 {server.upper()} 服务器的 {removed_count} 个绑定。")
            return
        bindings.clear()
        self._save_bindings()
        yield event.plain_result("已解除全部玩家绑定。")

    @filter.regex(_command_pattern("玩家状态", "我的玩家", "pjsk玩家状态"))
    async def player_status(self, event: AstrMessageEvent):
        """玩家状态 [序号或服务器]：显示已绑定玩家的资料。"""
        if not self._group_allowed(event):
            return
        if not self.enable_player_commands:
            yield event.plain_result("玩家功能未开启，请在插件配置中设置 enable_player_commands 为 true。")
            return
        raw = self._extract_arg(event, "玩家状态", "我的玩家", "pjsk玩家状态") or ""
        bindings = self._user_bindings(event.get_sender_id())
        if not bindings:
            yield event.plain_result("你还没有绑定任何玩家，请先使用：绑定玩家 <玩家ID> [服务器]")
            return

        if raw.isdigit():
            index = int(raw)
            if index < 1 or index > len(bindings):
                yield event.plain_result(f"序号无效，当前共有 {len(bindings)} 个绑定。")
                return
            selected = [bindings[index - 1]]
        elif raw:
            server = raw.lower() if raw.lower() in {"cn", "jp", "en", "tw", "kr"} else raw.lower()
            selected = [item for item in bindings if str(item.get("server")).lower() == server]
            if not selected:
                yield event.plain_result(f"没有找到 {server.upper()} 服务器的绑定。")
                return
        else:
            selected = bindings

        lines = []
        for idx, item in enumerate(selected, 1):
            player_id = str(item.get("player_id", ""))
            server = str(item.get("server", "cn"))
            try:
                profile = await self.client.player_profile(player_id, server)
                text = self._format_player_profile(profile, player_id, server)
            except Exception as exc:
                logger.warning("PJSK 玩家状态查询失败 (%s %s): %s", server, player_id, exc)
                text = f"【{server.upper()} {player_id}】状态获取失败：{exc}"
            lines.append(f"[{idx}] {text}")
        yield event.plain_result("\n\n".join(lines))

    @filter.regex(_command_pattern("随机曲", "pjsk随机曲", "随机歌"))
    async def random_music(self, event: AstrMessageEvent):
        """随机抽取一首歌曲；可选关键词会筛选歌名与制作人员。"""
        if not self._group_allowed(event):
            return
        keyword = self._extract_arg(event, "随机曲", "pjsk随机曲", "随机歌") or ""
        music = choose_music(await self._table("musics"), keyword)
        yield event.plain_result(music_text(music) if music else f"没有符合「{keyword}」的歌曲。")
