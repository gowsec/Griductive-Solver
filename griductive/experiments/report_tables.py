"""Generate Markdown summary tables from repeated experiment CSV files."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any

METRICS = (
    "primary_vars", "aux_vars", "clauses", "clauses_peak", "sat_calls",
    "decisions", "propagations", "backtracks", "steps", "waves",
    "runtime_s", "unique_runtime_s",
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def summarize(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[(row["puzzle"], row["encoding"])].append(row)
    result = {}
    for key, trials in sorted(groups.items()):
        summary: dict[str, Any] = {"size": trials[0]["size"], "trials": len(trials)}
        summary["status"] = ",".join(sorted({row["status"] for row in trials}))
        for metric in METRICS:
            values = [float(row[metric]) for row in trials if row.get(metric, "") not in ("", "N/A")]
            summary[metric] = median(values) if values else ""
        result[key] = summary
    return result


def _table(title: str, headers: list[str], rows: list[list[Any]]) -> str:
    def fmt(value: Any) -> str:
        if isinstance(value, float):
            return str(int(value)) if value.is_integer() else f"{value:.6g}"
        return str(value)
    lines = [f"## {title}", "", "| " + " | ".join(headers) + " |",
             "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(fmt(value) for value in row) + " |")
    return "\n".join(lines)


def render(directory: Path) -> str:
    comb_rows = read_csv(directory / "comb.csv")
    seq_rows = read_csv(directory / "seq.csv")
    comb = {k: v for k, v in summarize(comb_rows).items() if not k[0].startswith("bad_")}
    seq = {k: v for k, v in summarize(seq_rows).items() if not k[0].startswith("bad_")}
    tables = []
    metric_cols = ["aux_vars", "clauses", "sat_calls", "decisions", "runtime_s"]
    tables.append(_table("E1 — combinatorial theo kích thước (median)",
        ["Puzzle", "N", *metric_cols],
        [[puzzle, s["size"], *(s[m] for m in metric_cols)] for (puzzle, _), s in comb.items()]))
    tables.append(_table("E2 — combinatorial vs sequential (median)",
        ["Puzzle", "Encoding", "Aux", "Clauses", "SAT calls", "Runtime (s)"],
        [[puzzle, enc, s["aux_vars"], s["clauses"], s["sat_calls"], s["runtime_s"]]
         for (puzzle, enc), s in sorted({**comb, **seq}.items())]))

    e4_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (puzzle, _), summary in comb.items():
        puzzle_path = directory.parent / "puzzles" / puzzle
        try:
            data = json.loads(puzzle_path.read_text(encoding="utf-8"))
            clues = data.get("clues", {}).values()
            ext_count = sum(clue.get("type") in ("PARITY", "COMPARE") for clue in clues)
        except (OSError, ValueError, AttributeError):
            ext_count = 0
        e4_groups["With extension" if ext_count else "Without extension"].append(summary)
    e4_rows = []
    for label, values in sorted(e4_groups.items()):
        e4_rows.append([label, len(values), *(median([float(v[m]) for v in values if v[m] != ""]) if any(v[m] != "" for v in values) else "" for m in ("clauses", "sat_calls", "runtime_s"))])
    tables.append(_table("E4 — đối chứng extension", ["Nhóm", "Puzzles", "Clauses", "SAT calls", "Runtime (s)"], e4_rows))

    failures = []
    for source, rows in (("comb", comb_rows), ("seq", seq_rows)):
        grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            if row["status"] != "SOLVED":
                grouped[(row["puzzle"], row["status"], row["error"])].append(row)
        failures.extend([[source, puzzle, f"1–{len(trials)}", status, error or "—"]
                         for (puzzle, status, error), trials in sorted(grouped.items())])
    tables.append(_table("Ca lỗi / stuck / timeout", ["CSV", "Puzzle", "Trial", "Status", "Error"], failures or [["—", "Không có", "—", "—", "—"]]))
    return "\n\n".join(tables) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in", dest="directory", type=Path, default=Path("results"))
    parser.add_argument("--out", type=Path, help="ghi Markdown vào file; mặc định in stdout")
    args = parser.parse_args()
    output = render(args.directory)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(output, encoding="utf-8")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
