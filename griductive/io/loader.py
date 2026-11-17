"""JSON puzzle loading and schema validation."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any

from griductive.model.cell import CellId, Character, Status
from griductive.model.clue import Clue, Compare, Count, Different, Fact, Parity, Same
from griductive.model.puzzle import Puzzle
from griductive.model.region import Region, RegionKind, RegionResolver


class PuzzleError(ValueError):
    """Raised when a puzzle file is malformed or internally inconsistent."""


def load_puzzle(path: str | Path) -> Puzzle:
    """Load and validate a puzzle from a JSON file.

    Args:
        path: Path to the puzzle JSON file.

    Returns:
        A validated puzzle with immutable, row-major ordered mappings.

    Raises:
        PuzzleError: If the file cannot be read, its schema is invalid, or its
            solution does not satisfy every clue.
    """
    puzzle_path = Path(path)
    try:
        with puzzle_path.open(encoding="utf-8") as puzzle_file:
            data = json.load(puzzle_file)
    except OSError as error:
        raise PuzzleError(f"{puzzle_path}: cannot read puzzle: {error}") from error
    except json.JSONDecodeError as error:
        raise PuzzleError(
            f"{puzzle_path}: invalid JSON at line {error.lineno}, "
            f"column {error.colno}: {error.msg}"
        ) from error

    root = _object(data, "$")
    n = _positive_int(_required(root, "n", "$"), "$.n")
    expected_cells = tuple(CellId(row, col) for row in range(n) for col in range(n))
    expected_set = set(expected_cells)

    characters_raw = _object(_required(root, "characters", "$"), "$.characters")
    characters: dict[CellId, Character] = {}
    for cell, raw_character in _cell_entries(
        characters_raw, "$.characters", n, expected_set
    ):
        entry_path = f"$.characters.{cell}"
        character_data = _object(raw_character, entry_path)
        name = _non_empty_string(
            _required(character_data, "name", entry_path),
            f"{entry_path}.name",
        )
        job = _non_empty_string(
            _required(character_data, "job", entry_path),
            f"{entry_path}.job",
        )
        characters[cell] = Character(cell=cell, name=name, job=job)
    _require_complete_cells(characters, expected_set, "$.characters")

    solution_raw = _object(_required(root, "solution", "$"), "$.solution")
    solution: dict[CellId, Status] = {}
    for cell, raw_status in _cell_entries(
        solution_raw, "$.solution", n, expected_set
    ):
        try:
            solution[cell] = Status(raw_status)
        except (ValueError, TypeError) as error:
            raise PuzzleError(
                f"$.solution.{cell}: expected CRIMINAL or INNOCENT"
            ) from error
    _require_complete_cells(solution, expected_set, "$.solution")

    clues_raw = _object(_required(root, "clues", "$"), "$.clues")
    clues: dict[CellId, Clue] = {}
    for cell, raw_clue in _cell_entries(clues_raw, "$.clues", n, expected_set):
        clues[cell] = _parse_clue(raw_clue, f"$.clues.{cell}", f"clue@{cell}", n)
    _require_complete_cells(clues, expected_set, "$.clues")

    initial_raw = root.get("initial_revealed", [])
    if not isinstance(initial_raw, list):
        raise PuzzleError("$.initial_revealed: expected an array of cell IDs")
    initial_revealed_list = [
        _parse_cell(cell, f"$.initial_revealed[{index}]", n)
        for index, cell in enumerate(initial_raw)
    ]
    if len(set(initial_revealed_list)) != len(initial_revealed_list):
        raise PuzzleError("$.initial_revealed: duplicate cell ID")

    for cell, clue in clues.items():
        if not _clue_holds(clue, solution, n):
            raise PuzzleError(
                f"$.clues.{cell}: clue is not satisfied by the supplied solution"
            )

    return Puzzle(
        n=n,
        characters=MappingProxyType(dict(sorted(characters.items()))),
        solution=MappingProxyType(dict(sorted(solution.items()))),
        clues=MappingProxyType(dict(sorted(clues.items()))),
        initial_revealed=frozenset(initial_revealed_list),
    )


def _object(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise PuzzleError(f"{path}: expected an object with string keys")
    return value


def _required(data: Mapping[str, Any], key: str, path: str) -> Any:
    if key not in data:
        raise PuzzleError(f"{path}.{key}: required field is missing")
    return data[key]


def _positive_int(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise PuzzleError(f"{path}: expected a positive integer")
    return value


def _non_empty_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PuzzleError(f"{path}: expected a non-empty string")
    return value


def _parse_cell(value: Any, path: str, n: int) -> CellId:
    if not isinstance(value, str):
        raise PuzzleError(f"{path}: expected a cell ID string")
    try:
        cell = CellId.parse(value)
    except ValueError as error:
        raise PuzzleError(f"{path}: invalid cell ID {value!r}") from error
    if cell.row >= n or cell.col >= n:
        raise PuzzleError(f"{path}: cell {value!r} is outside the {n}x{n} grid")
    return cell


def _cell_entries(
    data: Mapping[str, Any],
    path: str,
    n: int,
    expected_cells: set[CellId],
) -> list[tuple[CellId, Any]]:
    entries: list[tuple[CellId, Any]] = []
    seen: set[CellId] = set()
    for key, value in data.items():
        cell = _parse_cell(key, f"{path}.{key}", n)
        if cell in seen:
            raise PuzzleError(f"{path}.{key}: duplicate cell ID {key!r}")
        if cell not in expected_cells:
            raise PuzzleError(f"{path}.{key}: unknown cell {key!r}")
        seen.add(cell)
        entries.append((cell, value))
    return entries


def _require_complete_cells(
    values: Mapping[CellId, Any],
    expected_cells: set[CellId],
    path: str,
) -> None:
    missing = sorted(expected_cells - values.keys())
    if missing:
        formatted = ", ".join(str(cell) for cell in missing)
        raise PuzzleError(f"{path}: missing entries for {formatted}")


def _parse_clue(value: Any, path: str, clue_id: str, n: int) -> Clue:
    data = _object(value, path)
    clue_type = _non_empty_string(_required(data, "type", path), f"{path}.type")

    if clue_type == "FACT":
        cell = _parse_cell(_required(data, "cell", path), f"{path}.cell", n)
        raw_status = _required(data, "status", path)
        try:
            status = Status(raw_status)
        except (ValueError, TypeError) as error:
            raise PuzzleError(f"{path}.status: expected CRIMINAL or INNOCENT") from error
        return Fact(clue_id, cell, status)

    if clue_type in {"SAME", "DIFFERENT"}:
        a = _parse_cell(_required(data, "a", path), f"{path}.a", n)
        b = _parse_cell(_required(data, "b", path), f"{path}.b", n)
        if clue_type == "SAME":
            return Same(clue_id, a, b)
        return Different(clue_id, a, b)

    if clue_type in {"EXACTLY", "AT_LEAST", "AT_MOST"}:
        raw_k = _required(data, "k", path)
        if isinstance(raw_k, bool) or not isinstance(raw_k, int):
            raise PuzzleError(f"{path}.k: expected an integer")
        region = _parse_region(_required(data, "region", path), f"{path}.region", n)
        region_cells = RegionResolver.cells(region, n)
        if not region_cells:
            raise PuzzleError(f"{path}.region: region must not be empty")
        if raw_k < 0 or raw_k > len(region_cells):
            raise PuzzleError(
                f"{path}.k: expected a value between 0 and {len(region_cells)}"
            )
        operator = {
            "EXACTLY": Count.EQ,
            "AT_LEAST": Count.GE,
            "AT_MOST": Count.LE,
        }[clue_type]
        return Count(clue_id, operator, raw_k, region)

    if clue_type == "PARITY":
        parity = _non_empty_string(
            _required(data, "parity", path), f"{path}.parity"
        )
        if parity not in (Parity.EVEN, Parity.ODD):
            raise PuzzleError(f"{path}.parity: expected EVEN or ODD")
        region = _parse_region(_required(data, "region", path), f"{path}.region", n)
        if not RegionResolver.cells(region, n):
            raise PuzzleError(f"{path}.region: region must not be empty")
        return Parity(clue_id, region, parity)

    if clue_type == "COMPARE":
        left = _parse_region(_required(data, "left", path), f"{path}.left", n)
        right = _parse_region(_required(data, "right", path), f"{path}.right", n)
        operator = _non_empty_string(_required(data, "op", path), f"{path}.op")
        if operator not in {
            Compare.LT,
            Compare.LE,
            Compare.EQ,
            Compare.GE,
            Compare.GT,
        }:
            raise PuzzleError(f"{path}.op: expected LT, LE, EQ, GE, or GT")
        if not RegionResolver.cells(left, n):
            raise PuzzleError(f"{path}.left: region must not be empty")
        if not RegionResolver.cells(right, n):
            raise PuzzleError(f"{path}.right: region must not be empty")
        return Compare(clue_id, left, operator, right)

    raise PuzzleError(f"{path}.type: unsupported clue type {clue_type!r}")


def _parse_region(value: Any, path: str, n: int) -> Region:
    data = _object(value, path)
    raw_kind = _non_empty_string(_required(data, "kind", path), f"{path}.kind")
    try:
        kind = RegionKind(raw_kind)
    except ValueError as error:
        raise PuzzleError(
            f"{path}.kind: expected ROW, COL, NEIGHBORS, or CELLS"
        ) from error

    if kind is RegionKind.ROW:
        raw_row = _required(data, "row", path)
        if isinstance(raw_row, bool) or not isinstance(raw_row, int):
            raise PuzzleError(f"{path}.row: expected a 1-based integer")
        if raw_row < 1 or raw_row > n:
            raise PuzzleError(f"{path}.row: must be between 1 and {n}")
        region = Region(kind=kind, row=raw_row - 1)
    elif kind is RegionKind.COL:
        raw_col = _required(data, "col", path)
        if not isinstance(raw_col, str):
            raise PuzzleError(f"{path}.col: expected a column letter")
        try:
            col = CellId.parse(f"{raw_col}1").col
        except ValueError as error:
            raise PuzzleError(f"{path}.col: invalid column {raw_col!r}") from error
        if col >= n:
            raise PuzzleError(f"{path}.col: column {raw_col!r} is outside the grid")
        region = Region(kind=kind, col=col)
    elif kind is RegionKind.NEIGHBORS:
        center = _parse_cell(_required(data, "center", path), f"{path}.center", n)
        region = Region(kind=kind, center=center)
    else:
        raw_cells = _required(data, "cells", path)
        if not isinstance(raw_cells, list):
            raise PuzzleError(f"{path}.cells: expected an array of cell IDs")
        cells = tuple(
            _parse_cell(cell, f"{path}.cells[{index}]", n)
            for index, cell in enumerate(raw_cells)
        )
        region = Region(kind=kind, cells=cells)

    try:
        RegionResolver.cells(region, n)
    except ValueError as error:
        raise PuzzleError(f"{path}: {error}") from error
    return region


def _clue_holds(clue: Clue, solution: Mapping[CellId, Status], n: int) -> bool:
    def is_criminal(cell: CellId) -> bool:
        return solution[cell] is Status.CRIMINAL

    if isinstance(clue, Fact):
        return solution[clue.cell] is clue.status
    if isinstance(clue, Same):
        return is_criminal(clue.a) == is_criminal(clue.b)
    if isinstance(clue, Different):
        return is_criminal(clue.a) != is_criminal(clue.b)
    if isinstance(clue, Count):
        count = sum(is_criminal(cell) for cell in clue.cells(n))
        return {
            Count.EQ: count == clue.k,
            Count.GE: count >= clue.k,
            Count.LE: count <= clue.k,
        }[clue.op]
    if isinstance(clue, Parity):
        count = sum(is_criminal(cell) for cell in clue.cells(n))
        return (count % 2 == 0) == (clue.parity == Parity.EVEN)
    if isinstance(clue, Compare):
        left_count = sum(is_criminal(cell) for cell in RegionResolver.cells(clue.left, n))
        right_count = sum(is_criminal(cell) for cell in RegionResolver.cells(clue.right, n))
        return {
            Compare.LT: left_count < right_count,
            Compare.LE: left_count <= right_count,
            Compare.EQ: left_count == right_count,
            Compare.GE: left_count >= right_count,
            Compare.GT: left_count > right_count,
        }[clue.op]
    raise PuzzleError(f"unsupported clue implementation: {type(clue).__name__}")
