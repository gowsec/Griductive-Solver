"""Unit tests for grid cell types and region resolution."""

import unittest
from dataclasses import FrozenInstanceError

from griductive.model.cell import CellId, Character, Status
from griductive.model.region import Region, RegionKind, RegionResolver


class CellModelTests(unittest.TestCase):
    def test_cell_id_parse_and_string_round_trip(self) -> None:
        self.assertEqual(CellId.parse("C2"), CellId(row=1, col=2))
        self.assertEqual(str(CellId.parse("C2")), "C2")
        self.assertEqual(str(CellId.parse("AA10")), "AA10")
        self.assertEqual(CellId.parse("aa10"), CellId(row=9, col=26))

    def test_cell_id_order_is_row_major(self) -> None:
        cells = [CellId(1, 0), CellId(0, 2), CellId(0, 0), CellId(0, 1)]
        self.assertEqual(
            [str(cell) for cell in sorted(cells)], ["A1", "B1", "C1", "A2"]
        )

    def test_cell_id_parse_rejects_invalid_coordinates(self) -> None:
        for text in ("", "A0", "A01", "1A", "A 1", "A1!"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                CellId.parse(text)

    def test_cell_id_rejects_invalid_indices(self) -> None:
        for row, col in ((-1, 0), (0, -1), (True, 0), (0, 1.5)):
            with self.subTest(row=row, col=col), self.assertRaises(ValueError):
                CellId(row, col)

    def test_character_and_status_are_immutable_model_data(self) -> None:
        character = Character(CellId.parse("B3"), "Alex", "Detective")
        self.assertEqual(character.cell, CellId(2, 1))
        self.assertEqual(Status.CRIMINAL.value, "CRIMINAL")
        self.assertEqual(Status.INNOCENT.value, "INNOCENT")
        with self.assertRaises(FrozenInstanceError):
            character.name = "Changed"  # type: ignore[misc]


class RegionResolverTests(unittest.TestCase):
    def test_resolve_row_and_column(self) -> None:
        row = RegionResolver.cells(Region(RegionKind.ROW, row=0), 3)
        col = RegionResolver.cells(Region(RegionKind.COL, col=1), 3)
        self.assertEqual([str(cell) for cell in row], ["A1", "B1", "C1"])
        self.assertEqual([str(cell) for cell in col], ["B1", "B2", "B3"])

    def test_resolve_neighbors(self) -> None:
        cases = (
            ("B2", ["A1", "B1", "C1", "A2", "C2", "A3", "B3", "C3"]),
            ("A1", ["B1", "A2", "B2"]),
            ("B1", ["A1", "C1", "A2", "B2", "C2"]),
        )
        for center, expected in cases:
            with self.subTest(center=center):
                region = Region(
                    RegionKind.NEIGHBORS, center=CellId.parse(center)
                )
                self.assertEqual(
                    [str(cell) for cell in RegionResolver.cells(region, 3)], expected
                )

    def test_resolve_neighbors_on_larger_grid(self) -> None:
        middle = RegionResolver.cells(
            Region(RegionKind.NEIGHBORS, center=CellId.parse("C3")), 5
        )
        corner = RegionResolver.cells(
            Region(RegionKind.NEIGHBORS, center=CellId.parse("E5")), 5
        )
        self.assertEqual(len(middle), 8)
        self.assertEqual(len(corner), 3)

    def test_resolve_explicit_cells_sorts_row_major(self) -> None:
        region = Region(
            RegionKind.CELLS,
            cells=(CellId.parse("C2"), CellId.parse("A1"), CellId.parse("B1")),
        )
        self.assertEqual(
            [str(cell) for cell in RegionResolver.cells(region, 3)],
            ["A1", "B1", "C2"],
        )

    def test_resolve_explicit_cells_rejects_duplicates_and_out_of_bounds(self) -> None:
        duplicate = Region(RegionKind.CELLS, cells=(CellId(0, 0), CellId(0, 0)))
        outside = Region(RegionKind.CELLS, cells=(CellId(3, 0),))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            RegionResolver.cells(duplicate, 3)
        with self.assertRaisesRegex(ValueError, "outside"):
            RegionResolver.cells(outside, 3)

    def test_resolve_rejects_invalid_region_coordinates(self) -> None:
        cases = (
            (Region(RegionKind.ROW, row=3), 3),
            (Region(RegionKind.COL, col=-1), 3),
            (Region(RegionKind.NEIGHBORS, center=CellId(3, 0)), 3),
            (Region(RegionKind.ROW, row=0), 0),
        )
        for region, n in cases:
            with self.subTest(region=region, n=n), self.assertRaises(ValueError):
                RegionResolver.cells(region, n)


if __name__ == "__main__":
    unittest.main()
