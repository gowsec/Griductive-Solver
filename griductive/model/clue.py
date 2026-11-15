"""Immutable clue types used by the puzzle model and logic layer."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

from griductive.model.cell import CellId, Status
from griductive.model.region import Region, RegionResolver


class Clue(ABC):
    """Abstract interface shared by all clue types."""

    id: str

    @abstractmethod
    def cells(self, n: int) -> tuple[CellId, ...]:
        """Return the cells referenced by this clue for highlighting."""

    @abstractmethod
    def describe(self) -> str:
        """Return a human-readable description of this clue."""


@dataclass(frozen=True)
class Fact(Clue):
    """A clue assigning a status to one cell."""

    id: str
    cell: CellId
    status: Status

    def cells(self, n: int) -> tuple[CellId, ...]:
        """Return the single cell referenced by this fact."""
        return (self.cell,)

    def describe(self) -> str:
        """Describe the status asserted by this fact."""
        return f"{self.cell} is {self.status.value}"


@dataclass(frozen=True)
class Same(Clue):
    """A clue asserting that two cells have the same status."""

    id: str
    a: CellId
    b: CellId

    def cells(self, n: int) -> tuple[CellId, ...]:
        """Return the two cells referenced by this clue."""
        return (self.a, self.b)

    def describe(self) -> str:
        """Describe the equality relation between the two cells."""
        return f"{self.a} and {self.b} have the same status"


@dataclass(frozen=True)
class Different(Clue):
    """A clue asserting that two cells have different statuses."""

    id: str
    a: CellId
    b: CellId

    def cells(self, n: int) -> tuple[CellId, ...]:
        """Return the two cells referenced by this clue."""
        return (self.a, self.b)

    def describe(self) -> str:
        """Describe the inequality relation between the two cells."""
        return f"{self.a} and {self.b} have different statuses"


@dataclass(frozen=True)
class Count(Clue):
    """A cardinality clue over a resolved region."""

    EQ: ClassVar[str] = "EQ"
    GE: ClassVar[str] = "GE"
    LE: ClassVar[str] = "LE"

    id: str
    op: str
    k: int
    region: Region

    def cells(self, n: int) -> tuple[CellId, ...]:
        """Return all cells counted by this clue."""
        return RegionResolver.cells(self.region, n)

    def describe(self) -> str:
        """Describe the required criminal count in the region."""
        wording = {
            self.EQ: f"exactly {self.k}",
            self.GE: f"at least {self.k}",
            self.LE: f"at most {self.k}",
        }.get(self.op, f"{self.op} {self.k}")
        return f"{wording} criminal(s) in {self.region.kind.value}"


@dataclass(frozen=True)
class Parity(Clue):
    """A clue constraining the parity of criminal cells in a region."""

    EVEN: ClassVar[str] = "EVEN"
    ODD: ClassVar[str] = "ODD"

    id: str
    region: Region
    parity: str

    def cells(self, n: int) -> tuple[CellId, ...]:
        """Return all cells counted by this parity clue."""
        return RegionResolver.cells(self.region, n)

    def describe(self) -> str:
        """Describe the required parity in the region."""
        return f"An {self.parity.lower()} number of criminals in {self.region.kind.value}"


@dataclass(frozen=True)
class Compare(Clue):
    """A clue comparing criminal counts in two regions."""

    LT: ClassVar[str] = "LT"
    LE: ClassVar[str] = "LE"
    EQ: ClassVar[str] = "EQ"
    GE: ClassVar[str] = "GE"
    GT: ClassVar[str] = "GT"

    id: str
    left: Region
    op: str
    right: Region

    def cells(self, n: int) -> tuple[CellId, ...]:
        """Return the unique cells in both compared regions, row-major."""
        return tuple(sorted(set(
            RegionResolver.cells(self.left, n)
            + RegionResolver.cells(self.right, n)
        )))

    def describe(self) -> str:
        """Describe the comparison between criminal counts."""
        symbol = {
            self.LT: "<",
            self.LE: "<=",
            self.EQ: "=",
            self.GE: ">=",
            self.GT: ">",
        }.get(self.op, self.op)
        return (
            f"Criminal count in {self.left.kind.value} {symbol} "
            f"criminal count in {self.right.kind.value}"
        )
