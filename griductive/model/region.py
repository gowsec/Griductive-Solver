"""Grid regions and their canonical cell resolution."""

from dataclasses import dataclass
from enum import Enum

from griductive.model.cell import CellId


class RegionKind(Enum):
    """Kinds of grid regions supported by the model."""

    ROW = "ROW"
    COL = "COL"
    NEIGHBORS = "NEIGHBORS"
    CELLS = "CELLS"


@dataclass(frozen=True)
class Region:
    """Immutable description of a row, column, neighborhood, or cell set."""

    kind: RegionKind
    row: int | None = None
    col: int | None = None
    center: CellId | None = None
    cells: tuple[CellId, ...] = ()


class RegionResolver:
    """Resolve region descriptions to deterministically ordered cells."""

    @staticmethod
    def cells(region: Region, n: int) -> tuple[CellId, ...]:
        """Return the unique cells in a region, sorted in row-major order.

        ``NEIGHBORS`` includes the eight surrounding positions that fall
        within the grid and excludes the center cell.

        Args:
            region: Region description to resolve.
            n: Width and height of the square grid; must be positive.

        Returns:
            A tuple of unique cell coordinates in row-major order.

        Raises:
            ValueError: If the grid size or region coordinates are invalid,
                or if an explicit cell region contains duplicates.
        """
        if isinstance(n, bool) or not isinstance(n, int) or n <= 0:
            raise ValueError("grid size n must be a positive integer")
        if not isinstance(region, Region):
            raise ValueError("region must be a Region")

        if region.kind is RegionKind.ROW:
            if not RegionResolver._is_in_bounds(region.row, n):
                raise ValueError(f"row must be between 0 and {n - 1}")
            return tuple(CellId(region.row, col) for col in range(n))

        if region.kind is RegionKind.COL:
            if not RegionResolver._is_in_bounds(region.col, n):
                raise ValueError(f"col must be between 0 and {n - 1}")
            return tuple(CellId(row, region.col) for row in range(n))

        if region.kind is RegionKind.NEIGHBORS:
            center = region.center
            if not isinstance(center, CellId) or not RegionResolver._cell_in_bounds(
                center, n
            ):
                raise ValueError("center must be a cell within the grid")
            return tuple(
                CellId(row, col)
                for row in range(max(0, center.row - 1), min(n, center.row + 2))
                for col in range(max(0, center.col - 1), min(n, center.col + 2))
                if (row, col) != (center.row, center.col)
            )

        if region.kind is RegionKind.CELLS:
            if len(set(region.cells)) != len(region.cells):
                raise ValueError("CELLS region cannot contain duplicate cells")
            if any(not RegionResolver._cell_in_bounds(cell, n) for cell in region.cells):
                raise ValueError("CELLS region contains a cell outside the grid")
            return tuple(sorted(region.cells))

        raise ValueError(f"unsupported region kind: {region.kind!r}")

    @staticmethod
    def _is_in_bounds(value: int | None, n: int) -> bool:
        return (
            isinstance(value, int)
            and not isinstance(value, bool)
            and 0 <= value < n
        )

    @staticmethod
    def _cell_in_bounds(cell: CellId, n: int) -> bool:
        return 0 <= cell.row < n and 0 <= cell.col < n
