"""Search and presentation helpers kept independent from AstrBot."""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Any, Iterable


DIFFICULTY_NAMES = {
    "easy": "EASY", "normal": "NORMAL", "hard": "HARD",
    "expert": "EXPERT", "master": "MASTER", "append": "APPEND",
}
ATTRIBUTE_NAMES = {
    "cool": "神秘", "cute": "可爱", "happy": "快乐", "mysterious": "神秘", "pure": "纯真",
}
CARD_IMAGE_BASE = "https://sekai-assets.haruki.seiunx.com"


def card_image_url(card: dict[str, Any], region: str = "cn") -> str | None:
    """Generate the normal card thumbnail URL from Haruki's Sekai asset CDN."""
    assetbundle = str(card.get("assetbundleName") or "").strip()
    if not assetbundle:
        return None
    region = region if region in {"jp", "en", "tw", "kr", "cn"} else "cn"
    return (
        f"{CARD_IMAGE_BASE}/{region}-assets/"
        f"startapp/thumbnail/chara/{assetbundle}_normal.png"
    )


def value(item: dict[str, Any], *keys: str, default: Any = "-") -> Any:
    for key in keys:
        result = item.get(key)
        if result not in (None, ""):
            return result
    return default


def search(items: Iterable[dict[str, Any]], keyword: str, *keys: str, limit: int = 5) -> list[dict[str, Any]]:
    needle = keyword.strip().casefold()
    if not needle:
        return []
    exact, partial = [], []
    for item in items:
        haystacks = [str(item.get(key, "")) for key in keys]
        if any(text.casefold() == needle for text in haystacks):
            exact.append(item)
        elif any(needle in text.casefold() for text in haystacks):
            partial.append(item)
    return (exact + partial)[:limit]


def card_text(card: dict[str, Any], characters: dict[int, dict[str, Any]]) -> str:
    character = characters.get(int(card.get("characterId", 0)), {})
    character_name = value(character, "givenName", "firstName", "name")
    rarity = str(value(card, "cardRarityType")).replace("rarity_", "")
    attribute = ATTRIBUTE_NAMES.get(str(card.get("attr")), value(card, "attr"))
    return "\n".join((
        f"【{value(card, 'prefix', 'name')}】",
        f"ID：{value(card, 'id')}  稀有度：{rarity}  属性：{attribute}",
        f"角色：{character_name}  发布时间：{value(card, 'releaseAt')}",
    ))


def music_text(music: dict[str, Any]) -> str:
    return "\n".join((
        f"【{value(music, 'title')}】",
        f"ID：{value(music, 'id')}  作词：{value(music, 'lyricist')}  作曲：{value(music, 'composer')}",
        f"编曲：{value(music, 'arranger')}  分类：{value(music, 'musicType')}",
    ))


def chart_text(chart: dict[str, Any]) -> str:
    difficulty = DIFFICULTY_NAMES.get(str(chart.get("musicDifficulty")), value(chart, "musicDifficulty"))
    return f"{difficulty}：等级 {value(chart, 'playLevel')}，物量 {value(chart, 'totalNoteCount')}"


def event_text(event: dict[str, Any]) -> str:
    return "\n".join((
        f"【{value(event, 'name')}】",
        f"ID：{value(event, 'id')}  类型：{value(event, 'eventType')}",
        f"开始：{format_timestamp(event.get('startAt'))}",
        f"结束：{format_timestamp(event.get('closedAt', event.get('aggregateAt')))}",
    ))


def format_timestamp(timestamp: Any) -> str:
    try:
        return datetime.fromtimestamp(int(timestamp) / 1000, tz=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError, OSError):
        return "-"


def choose_music(musics: list[dict[str, Any]], keyword: str = "") -> dict[str, Any] | None:
    candidates = search(musics, keyword, "title", "lyricist", "composer", "arranger", limit=len(musics)) if keyword else musics
    return random.choice(candidates) if candidates else None

