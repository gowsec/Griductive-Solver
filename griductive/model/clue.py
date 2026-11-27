"""Immutable clue types used by the puzzle model and logic layer."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar

from griductive.model.cell import CellId, Status
from griductive.model.region import Region, RegionKind, RegionResolver


class Clue(ABC):
    """Abstract interface shared by all clue types."""

    id: str

    @abstractmethod
    def cells(self, n: int) -> tuple[CellId, ...]:
        """Return the cells referenced by this clue for highlighting."""

    @abstractmethod
    def describe(self, names: Mapping[CellId, str] | None = None) -> str:
        """Return a human-readable description, using cell names when provided."""


def _cell_name(cell: CellId, names: Mapping[CellId, str] | None) -> str:
    if names is not None:
        name = names.get(cell)
        if isinstance(name, str) and name.strip():
            return f"{name} ({cell})"
    return str(cell)


def _region_name(region: Region, names: Mapping[CellId, str] | None) -> str:
    if region.kind is RegionKind.ROW and region.row is not None:
        label = f"row {region.row + 1}"
        members = sorted(cell for cell in (names or {}) if cell.row == region.row)
    elif region.kind is RegionKind.COL and region.col is not None:
        label = f"column {str(CellId(0, region.col))[:-1]}"
        members = sorted(cell for cell in (names or {}) if cell.col == region.col)
    elif region.kind is RegionKind.NEIGHBORS and region.center is not None:
        label = f"neighbors of {_cell_name(region.center, names)}"
        members = sorted(
            cell
            for cell in (names or {})
            if abs(cell.row - region.center.row) <= 1
            and abs(cell.col - region.center.col) <= 1
            and cell != region.center
        )
    elif region.kind is RegionKind.CELLS:
        members = sorted(region.cells)
        label = (
            "cells"
            if names is not None
            else "cells " + ", ".join(str(cell) for cell in region.cells)
        )
    else:
        label = region.kind.value.lower()
        members = []

    if names is not None and members:
        labels = ", ".join(_cell_name(cell, names) for cell in members)
        return f"{label} ({labels})"
    return label


@dataclass(frozen=True)
class Fact(Clue):
    """A clue assigning a status to one cell."""

    id: str
    cell: CellId
    status: Status

    def cells(self, n: int) -> tuple[CellId, ...]:
        """Return the single cell referenced by this fact."""
        return (self.cell,)

    def describe(self, names: Mapping[CellId, str] | None = None) -> str:
        """Describe the status asserted by this fact."""
        return f"{_cell_name(self.cell, names)} is {self.status.value}"


@dataclass(frozen=True)
class Same(Clue):
    """A clue asserting that two cells have the same status."""

    id: str
    a: CellId
    b: CellId

    def cells(self, n: int) -> tuple[CellId, ...]:
        """Return the two cells referenced by this clue."""
        return (self.a, self.b)

    def describe(self, names: Mapping[CellId, str] | None = None) -> str:
        """Describe the equality relation between the two cells."""
        return (
            f"{_cell_name(self.a, names)} and {_cell_name(self.b, names)} "
            "have the same status"
        )


@dataclass(frozen=True)
class Different(Clue):
    """A clue asserting that two cells have different statuses."""

    id: str
    a: CellId
    b: CellId

    def cells(self, n: int) -> tuple[CellId, ...]:
        """Return the two cells referenced by this clue."""
        return (self.a, self.b)

    def describe(self, names: Mapping[CellId, str] | None = None) -> str:
        """Describe the inequality relation between the two cells."""
        return (
            f"{_cell_name(self.a, names)} and {_cell_name(self.b, names)} "
            "have different statuses"
        )


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

    def describe(self, names: Mapping[CellId, str] | None = None) -> str:
        """Describe the required criminal count in the region."""
        noun = "criminal" if self.k == 1 else "criminals"
        wording = {
            self.EQ: f"exactly {self.k} {noun}",
            self.GE: f"at least {self.k} {noun}",
            self.LE: f"at most {self.k} {noun}",
        }.get(self.op, f"{self.op} {self.k}")
        return f"{wording} in {_region_name(self.region, names)}"


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

    def describe(self, names: Mapping[CellId, str] | None = None) -> str:
        """Describe the required parity in the region."""
        return (
            f"An {self.parity.lower()} number of criminals in "
            f"{_region_name(self.region, names)}"
        )


@dataclass(frozen=True)
class Compare(Clue):
    """A clue comparing criminal counts in two regions."""

    LT: ClassVar[str] = "LT"
    LE: ClassVar[str] = "LE"
    EQ: ClassVar[str] = "EQ"
    GE: ClassVar[str] = "GE"
    GT: ClassVar[str] = "GT"
    OPS: ClassVar[frozenset[str]] = frozenset({LT, LE, EQ, GE, GT})

    id: str
    left: Region
    op: str
    right: Region

    def left_cells(self, n: int) -> tuple[CellId, ...]:
        """Return the cells counted on the left side of the comparison."""
        return RegionResolver.cells(self.left, n)

    def right_cells(self, n: int) -> tuple[CellId, ...]:
        """Return the cells counted on the right side of the comparison."""
        return RegionResolver.cells(self.right, n)

    def cells(self, n: int) -> tuple[CellId, ...]:
        """Return the unique cells in both compared regions, row-major."""
        return tuple(sorted(set(self.left_cells(n)) | set(self.right_cells(n))))

    def describe(self, names: Mapping[CellId, str] | None = None) -> str:
        """Describe the comparison between criminal counts."""
        symbol = {
            self.LT: "<",
            self.LE: "<=",
            self.EQ: "=",
            self.GE: ">=",
            self.GT: ">",
        }.get(self.op, self.op)
        return (
            f"Criminal count in {_region_name(self.left, names)} {symbol} "
            f"criminal count in {_region_name(self.right, names)}"
        )
