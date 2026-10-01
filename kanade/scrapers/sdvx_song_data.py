"""SOUND VOLTEX song list scraper.

Pulls song data from the official site for the current game version.
"""

import logging
import time
from collections.abc import Iterator
from typing import Any

import requests
from bs4 import BeautifulSoup, Tag

from .. import storage
from ..models import Chart, Difficulty, Song

logger = logging.getLogger(__name__)

SONG_LIST_URL = "https://p.eagate.573.jp/game/sdvx/vii/music/index.html"


def _iter_song_elements() -> Iterator[Tag]:
    """Yield every song entry from the paginated song list, oldest first.

    The site lists newest songs first (both across and within pages), so all
    pages are fetched before replaying them in reverse.
    """
    all_elements: list[Tag] = []
    page = 1
    while True:
        logger.info("Fetching song list page %d", page)
        response = requests.get(SONG_LIST_URL, params={"page": page}, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        page_elements = soup.find_all(class_="music")
        if not page_elements:
            break

        all_elements.extend(page_elements)
        page += 1
        time.sleep(1)

    yield from reversed(all_elements)


def _parse_song(song_element: Tag) -> Song:
    """Extract song details from the HTML element."""
    info = song_element.find(class_="info")
    assert isinstance(info, Tag)
    # For some reason, since Nabla the site's been using non-breaking spaces.
    title, artist = (p.text.replace("\xa0", " ") for p in info.find_all("p"))

    charts: list[Chart] = []
    level_div = song_element.find(class_="level")
    assert isinstance(level_div, Tag)
    for level_p in level_div.find_all("p"):
        level = level_p.text.strip()
        if not level:
            # No chart at this difficulty for this song.
            continue
        classes = [c for c in (level_p.get("class") or []) if c != "none"]
        charts.append(Chart(difficulty=Difficulty[classes[0].upper()], level=level))

    return Song(title=title, artist=artist, charts=charts)


def scrape() -> Iterator[str]:
    """Scrape the song list, update the stored snapshot and report each change."""
    songs_by_key = {(s["title"], s["artist"]): s for s in storage.load_songs()}
    change_events: list[dict[str, Any]] = []

    for song_element in _iter_song_elements():
        song = _parse_song(song_element)
        key = (song["title"], song["artist"])
        charts = [
            {"difficulty": chart["difficulty"].name, "level": chart["level"]}
            for chart in song["charts"]
        ]
        record: dict[str, Any] = {
            "title": song["title"],
            "artist": song["artist"],
            "charts": charts,
        }

        prev = songs_by_key.get(key)
        if prev is None:
            songs_by_key[key] = record
            change_events.append({"type": "added", **record})
            yield f"Added song: `{song['title']}` by `{song['artist']}`"
            continue

        prev_levels = {c["difficulty"]: c["level"] for c in prev["charts"]}
        diffs = [
            (c["difficulty"], prev_levels.get(c["difficulty"]), c["level"])
            for c in charts
            if prev_levels.get(c["difficulty"]) != c["level"]
        ]
        if not diffs:
            continue

        songs_by_key[key] = record
        change_events.append(
            {
                "type": "updated",
                "title": song["title"],
                "artist": song["artist"],
                "changes": diffs,
            }
        )
        changes_text = ", ".join(
            f"`{name}` ({f'`{old}`' if old is not None else 'none'} → `{new}`)"
            for name, old, new in diffs
        )
        yield f"Updated `{song['title']}` by `{song['artist']}`: {changes_text}"

    storage.save_songs(list(songs_by_key.values()))
    storage.append_changes(change_events)
