"""Structured clues used by the Griductive logic encoder."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from griductive.model.cell import CellId, Status
from griductive.model.region import Region, RegionResolver


class Clue:
    """Base interface shared by all clue types."""

    id: str

    def cells(self, n: int) -> tuple[CellId, ...]:
        raise NotImplementedError

    def describe(self) -> str:
        raise NotImplementedError


@dataclass(frozen=True)
class Fact(Clue):
    id: str
    cell: CellId
    status: Status

    def cells(self, n: int) -> tuple[CellId, ...]:
        return (self.cell,)

    def describe(self) -> str:
        return f"{self.cell} is {self.status.value}"


@dataclass(frozen=True)
class Same(Clue):
    id: str
    a: CellId
    b: CellId

    def cells(self, n: int) -> tuple[CellId, ...]:
        return (self.a, self.b)

    def describe(self) -> str:
        return f"{self.a} and {self.b} have the same status"


@dataclass(frozen=True)
class Different(Clue):
    id: str
    a: CellId
    b: CellId

    def cells(self, n: int) -> tuple[CellId, ...]:
        return (self.a, self.b)

    def describe(self) -> str:
        return f"{self.a} and {self.b} have different statuses"


@dataclass(frozen=True)
class Count(Clue):
    """A cardinality clue: EQ, GE, or LE over a resolved region."""

    EQ: ClassVar[str] = "EQ"
    GE: ClassVar[str] = "GE"
    LE: ClassVar[str] = "LE"

    id: str
    op: str
    k: int
    region: Region

    def cells(self, n: int) -> tuple[CellId, ...]:
        return RegionResolver.cells(self.region, n)

    def describe(self) -> str:
        return f"{self.op} {self.k} Criminal(s) in {self.region.kind.value}"
