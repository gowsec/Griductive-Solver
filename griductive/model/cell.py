"""Immutable grid-cell and character data types."""

from dataclasses import dataclass
from enum import Enum
import re


class Status(Enum):
    """Classification assigned to a character's cell."""

    CRIMINAL = "CRIMINAL"
    INNOCENT = "INNOCENT"


@dataclass(frozen=True, order=True)
class CellId:
    """A zero-based cell coordinate, ordered in row-major order."""

    row: int
    col: int

    def __post_init__(self) -> None:
        """Validate that the coordinate is a pair of non-negative integers."""
        if (
            isinstance(self.row, bool)
            or not isinstance(self.row, int)
            or self.row < 0
        ):
            raise ValueError("row must be a non-negative integer")
        if (
            isinstance(self.col, bool)
            or not isinstance(self.col, int)
            or self.col < 0
        ):
            raise ValueError("col must be a non-negative integer")

    @staticmethod
    def parse(text: str) -> "CellId":
        """Parse a spreadsheet-style coordinate such as ``C2``.

        Args:
            text: One or more ASCII letters followed by a positive row number.

        Returns:
            The corresponding zero-based cell coordinate.

        Raises:
            ValueError: If ``text`` is not a valid cell coordinate.
        """
        if not isinstance(text, str):
            raise ValueError("cell coordinate must be a string")
        match = re.fullmatch(r"([A-Za-z]+)([1-9][0-9]*)", text)
        if match is None:
            raise ValueError(f"invalid cell coordinate: {text!r}")

        column_label, row_text = match.groups()
        col = 0
        for letter in column_label.upper():
            col = col * 26 + ord(letter) - ord("A") + 1
        return CellId(row=int(row_text) - 1, col=col - 1)

    def __str__(self) -> str:
        """Return the spreadsheet-style coordinate, such as ``C2``."""
        col = self.col + 1
        column_label = ""
        while col:
            col, remainder = divmod(col - 1, 26)
            column_label = chr(ord("A") + remainder) + column_label
        return f"{column_label}{self.row + 1}"


@dataclass(frozen=True)
class Character:
    """Display information associated with a cell."""

    cell: CellId
    name: str
    job: str
