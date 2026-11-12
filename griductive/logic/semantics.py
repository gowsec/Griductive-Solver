"""Direct semantic evaluation of Griductive clues."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from griductive.model.cell import CellId, Status
from griductive.model.clue import Clue, Compare, Count, Different, Fact, Parity, Same


def holds(
    clue: Clue,
    assignment: Mapping[CellId, bool | Status] | Sequence[bool],
    n: int,
) -> bool:
    """Return whether a clue is true under a complete primary-variable model.

    ``assignment`` may map each ``CellId`` to a bool/``Status``, or be a
    row-major sequence of ``n*n`` booleans (``False`` = INNOCENT).
    This evaluator deliberately does not depend on the CNF encoder.
    """
    if isinstance(n, bool) or not isinstance(n, int) or n <= 0:
        raise ValueError("n must be a positive integer")

    def criminal(cell: CellId) -> bool:
        if not (0 <= cell.row < n and 0 <= cell.col < n):
            raise ValueError(f"cell {cell} is outside the {n}x{n} grid")
        if isinstance(assignment, Mapping):
            if cell not in assignment:
                raise ValueError(f"assignment is missing cell {cell}")
            value = assignment[cell]
        else:
            if len(assignment) != n * n:
                raise ValueError(f"assignment must contain exactly {n * n} values")
            value = assignment[cell.row * n + cell.col]
        if isinstance(value, Status):
            return value is Status.CRIMINAL
        if isinstance(value, bool):
            return value
        raise ValueError(f"assignment for {cell} must be bool or Status")

    if isinstance(clue, Fact):
        value = criminal(clue.cell)
        return value is (clue.status is Status.CRIMINAL)
    if isinstance(clue, Same):
        return criminal(clue.a) == criminal(clue.b)
    if isinstance(clue, Different):
        return criminal(clue.a) != criminal(clue.b)
    if isinstance(clue, Count):
        cells = clue.cells(n)
        total = sum(criminal(cell) for cell in cells)
        if clue.op == Count.EQ:
            return total == clue.k
        if clue.op == Count.GE:
            return total >= clue.k
        if clue.op == Count.LE:
            return total <= clue.k
        raise ValueError(f"unsupported count operator: {clue.op!r}")
    if isinstance(clue, Parity):
        if clue.parity not in (Parity.EVEN, Parity.ODD):
            raise ValueError(f"unsupported parity: {clue.parity!r}")
        is_odd = sum(criminal(cell) for cell in clue.cells(n)) % 2 == 1
        return is_odd is (clue.parity == Parity.ODD)
    if isinstance(clue, Compare):
        if clue.op not in Compare.OPS:
            raise ValueError(f"unsupported comparison operator: {clue.op!r}")
        left = sum(criminal(cell) for cell in clue.left_cells(n))
        right = sum(criminal(cell) for cell in clue.right_cells(n))
        return {
            Compare.LT: left < right,
            Compare.LE: left <= right,
            Compare.EQ: left == right,
            Compare.GE: left >= right,
            Compare.GT: left > right,
        }[clue.op]
    raise ValueError(f"unsupported clue type: {type(clue).__name__}")
