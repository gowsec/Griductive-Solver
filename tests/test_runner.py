"""Suite runner status, encoding, uniqueness and CSV contract tests."""

import csv
from pathlib import Path

from griductive.experiments.runner import CSV_FIELDS, run_puzzle, run_suite


ROOT = Path(__file__).resolve().parents[1]


def test_runner_records_unique_and_stuck_distinctions() -> None:
    not_unique, _ = run_puzzle(ROOT / "puzzles" / "bad_not_unique.json")
    stuck, _ = run_puzzle(ROOT / "puzzles" / "bad_stuck.json")
    assert (not_unique["status"], not_unique["unique"]) == ("STUCK", "NOT_UNIQUE")
    assert (stuck["status"], stuck["unique"]) == ("STUCK", "UNIQUE")


def test_runner_schema_error_and_csv_have_complete_fields(tmp_path: Path) -> None:
    row, _ = run_puzzle(ROOT / "puzzles" / "bad_schema.json")
    assert row["status"] == "ERROR"
    assert row["size"] == "N/A"

    suite = tmp_path / "suite"
    suite.mkdir()
    (suite / "bad_schema.json").write_bytes((ROOT / "puzzles" / "bad_schema.json").read_bytes())
    output = tmp_path / "metrics.csv"
    rows = run_suite(suite, output=output, timeout=1, encoding="sequential")
    assert rows[0]["encoding"] == "sequential"
    with output.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        assert tuple(reader.fieldnames or ()) == CSV_FIELDS
        assert len(list(reader)) == 1


def test_runner_solves_sample_with_selected_encoding() -> None:
    row, trace = run_puzzle(ROOT / "puzzles" / "3x3_01.json", encoding="sequential")
    assert row["encoding"] == "sequential"
    assert row["unique"] == "UNIQUE"
    assert row["status"] == trace.terminal == "SOLVED"
    assert row["sat_calls"] > 0
