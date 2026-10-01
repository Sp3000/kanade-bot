"""Shared data models."""

from typing import TypedDict

from .utils import OrderedEnum


class Difficulty(OrderedEnum):
    """Difficulty of a song's chart, e.g. EXH or MXM."""

    NOV = NOVICE = 0
    ADV = ADVANCED = 1
    EXH = EXHAUST = 2
    MXM = MAXIMUM = 3
    INF = INFINITE = 4
    GRV = GRAVITY = 5
    HVN = HEAVENLY = 6
    VVD = VIVID = 7
    XCD = EXCEED = 8
    NBL = NABLA = 9
    # Should always be displayed after all the 4th difficulties.
    ULT = ULTIMATE = 99

    @property
    def sdvxin_letter(self) -> str:
        """Return the letter suffix used in sdvx.in."""
        mapping = {
            Difficulty.NOV: "n",
            Difficulty.ADV: "a",
            Difficulty.EXH: "e",
            Difficulty.ULT: "u",
        }
        # sdvx.in defaults to "m" for 4th difficulties.
        return mapping.get(self, "m")

    def to_color(self) -> str:
        """Get the colour associated with a song difficulty type."""
        return DIFFICULTY_TO_COLOR[self]

    def __repr__(self) -> str:
        """Return the 3-letter difficulty code, e.g. "NOV"."""
        return self.name

    __str__ = __repr__


DIFFICULTY_TO_COLOR: dict[Difficulty, str] = {
    Difficulty.NOV: "#d248ff",
    Difficulty.ADV: "#f9f049",
    Difficulty.EXH: "#fe4a79",
    Difficulty.MXM: "#e2e2e2",
    Difficulty.INF: "#ff00ff",
    Difficulty.GRV: "#e5720a",
    Difficulty.HVN: "#009aff",
    Difficulty.VVD: "#f82374",
    Difficulty.XCD: "#3568aa",
    Difficulty.NBL: "#95dd03",
    Difficulty.ULT: "#ffdd57",
}


class Chart(TypedDict):
    """A single difficulty's chart for a song."""

    difficulty: Difficulty
    level: str


class Song(TypedDict):
    """A single song in the game."""

    title: str
    artist: str
    charts: list[Chart]
