"""Deterministic mapping between grid cells and DIMACS variables."""

from __future__ import annotations

from griductive.model.cell import CellId


class VarMap:
    """Map row-major cells to primary variables and allocate auxiliary ones.

    Primary variables occupy ``1..n*n``. Auxiliary variables are allocated
    monotonically from ``n*n + 1`` and never map back to a cell.
    """

    __slots__ = ("_n", "_next_aux")

    def __init__(self, n: int) -> None:
        """Create a variable map for an ``n`` by ``n`` grid."""
        if isinstance(n, bool) or not isinstance(n, int) or n <= 0:
            raise ValueError("n must be a positive integer")
        self._n = n
        self._next_aux = n * n + 1

    @property
    def n(self) -> int:
        """Return the grid width."""
        return self._n

    @property
    def n_primary(self) -> int:
        """Return the number of primary variables."""
        return self._n * self._n

    @property
    def n_aux(self) -> int:
        """Return the number of auxiliary variables allocated so far."""
        return self._next_aux - self.n_primary - 1

    def var(self, cell: CellId) -> int:
        """Return the primary variable for a zero-based grid cell."""
        if not isinstance(cell, CellId):
            raise TypeError("cell must be a CellId")
        if not (0 <= cell.row < self._n and 0 <= cell.col < self._n):
            raise ValueError(f"cell is outside the {self._n}x{self._n} grid: {cell!r}")
        return cell.row * self._n + cell.col + 1

    def cell(self, var: int) -> CellId:
        """Return the cell for a primary variable; reject auxiliary variables."""
        if isinstance(var, bool) or not isinstance(var, int):
            raise TypeError("var must be an integer")
        if not 1 <= var <= self.n_primary:
            raise ValueError(f"{var} is not a primary variable")
        index = var - 1
        return CellId(index // self._n, index % self._n)

    def new_aux(self) -> int:
        """Allocate and return the next auxiliary variable."""
        result = self._next_aux
        self._next_aux += 1
        return result
