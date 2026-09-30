"""General-purpose utils."""

from enum import Enum
from functools import total_ordering


@total_ordering
class OrderedEnum(Enum):
    """An Enum whose members compare by value."""

    def __lt__(self, other: object) -> bool:
        """Compare members of the same OrderedEnum subclass by value."""
        if self.__class__ is other.__class__:
            return bool(self.value < other.value)
        return NotImplemented
