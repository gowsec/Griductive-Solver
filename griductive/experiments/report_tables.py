"""Generate Markdown tables from repeated experiment CSV files."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any

TRIALS = (1, 2, 3, 4, 5)
METRICS = (
    "primary_vars", "aux_vars", "clauses", "clauses_peak", "sat_calls",
    "decisions", "propagations", "backtracks", "steps", "waves",
    "runtime_s", "unique_runtime_s",
)
COMPARISON_METRICS = (
    ("aux_vars", "Aux vars"), ("clauses", "Clauses"),
    ("sat_calls", "SAT calls"), ("decisions", "Decisions"),
    ("propagations", "Propagations"), ("backtracks", "Backtracks"),
    ("steps", "Steps"), ("waves", "Waves"), ("runtime_s", "Runtime (s)"),
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"puzzle", "size", "encoding", "trial", "status", *METRICS}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"{path}: missing CSV columns: {', '.join(sorted(missing))}")
        return list(reader)


def summarize(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, Any]]:
    """Return one median summary for each puzzle and encoding; require five trials."""
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[(row["puzzle"], row["encoding"])].append(row)

    result: dict[tuple[str, str], dict[str, Any]] = {}
    for key, trials in sorted(groups.items()):
        try:
            trial_ids = [int(row["trial"]) for row in trials]
        except ValueError as exc:
            raise ValueError(f"{key[0]} ({key[1]}): trial must be an integer") from exc
        if sorted(trial_ids) != list(TRIALS):
            raise ValueError(
                f"{key[0]} ({key[1]}): expected trials 1..5 exactly once; "
                f"found {sorted(trial_ids)}"
            )
        sizes = {row["size"] for row in trials}
        if len(sizes) != 1:
            raise ValueError(f"{key[0]} ({key[1]}): inconsistent size values {sizes}")

        summary: dict[str, Any] = {
            "size": next(iter(sizes)), "trials": len(trials),
            "status": ",".join(sorted({row["status"] for row in trials})),
        }
        for metric in METRICS:
            values = [float(row[metric]) for row in trials
                      if row.get(metric, "").strip() not in ("", "N/A")]
            summary[metric] = median(values) if values else ""
        result[key] = summary
    return result


def _table(title: str, headers: list[str], rows: list[list[Any]]) -> str:
    def fmt(value: Any) -> str:
        if isinstance(value, float):
            return str(int(value)) if value.is_integer() else f"{value:.6g}"
        return str(value).replace("|", "\\|").replace("\n", " ")

    lines = [f"## {title}", "", "| " + " | ".join(headers) + " |",
             "|" + "|".join("---" for _ in headers) + "|"]
    lines.extend("| " + " | ".join(fmt(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def _median_summary(summaries: list[dict[str, Any]], metric: str) -> Any:
    values = [row[metric] for row in summaries if row[metric] != ""]
    return median(values) if values else ""


def _extension_count(directory: Path, puzzle: str) -> int:
    path = directory.parent / "puzzles" / puzzle
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        clues = data.get("clues", {}).values()
        return sum(clue.get("type") in ("PARITY", "COMPARE") for clue in clues)
    except (OSError, ValueError, AttributeError):
        return 0


def render(directory: Path) -> str:
    comb = summarize(read_csv(directory / "comb.csv"))
    seq = summarize(read_csv(directory / "seq.csv"))
    for key in comb:
        if key[1] != "combinatorial":
            raise ValueError(f"comb.csv contains unexpected encoding {key[1]!r}")
    for key in seq:
        if key[1] != "sequential":
            raise ValueError(f"seq.csv contains unexpected encoding {key[1]!r}")

    # The malformed-input fixtures are reported in the failure table, not the
    # valid-puzzle experiments. The two intentional STUCK puzzles remain valid.
    comb_valid = {k: v for k, v in comb.items() if not k[0].startswith("bad_")}
    seq_valid = {k: v for k, v in seq.items() if not k[0].startswith("bad_")}
    if {puzzle for puzzle, _ in comb_valid} != {puzzle for puzzle, _ in seq_valid}:
        raise ValueError("comb.csv and seq.csv must contain the same valid puzzles")

    metric_names = [name for name, _ in COMPARISON_METRICS]
    metric_labels = [label for _, label in COMPARISON_METRICS]
    by_size: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for summary in comb_valid.values():
        by_size[summary["size"]].append(summary)
    size_rows = [
        [f"{size}×{size}", len(values),
         *(_median_summary(values, metric) for metric in metric_names)]
        for size, values in sorted(by_size.items(), key=lambda item: int(item[0]))
    ]
    per_puzzle_rows = [
        [puzzle, summary["size"], *(summary[m] for m in metric_names)]
        for (puzzle, _), summary in sorted(comb_valid.items())
    ]
    tables = [
        _table("E1 — combinatorial theo kích thước (median 5 trials)",
               ["Kích thước", "Số puzzle", *metric_labels], size_rows),
        _table("E1 — chi tiết theo puzzle (median 5 trials)",
               ["Puzzle", "N", *metric_labels], per_puzzle_rows),
    ]

    e2_rows = []
    for puzzle, _ in sorted(comb_valid):
        c = comb_valid[(puzzle, "combinatorial")]
        s = seq_valid[(puzzle, "sequential")]
        e2_rows.append([puzzle, c["size"],
                        *(value for metric in metric_names
                          for value in (c[metric], s[metric]))])
    e2_headers = ["Puzzle", "N"] + [
        f"{label} ({encoding})"
        for _, label in COMPARISON_METRICS
        for encoding in ("comb", "seq")
    ]
    tables.append(_table("E2 — combinatorial vs sequential (median 5 trials)",
                          e2_headers, e2_rows))

    e4_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (puzzle, _), summary in comb_valid.items():
        label = "Có extension" if _extension_count(directory, puzzle) else "Không extension"
        e4_groups[label].append(summary)
    e4_rows = [
        [label, len(values), *(_median_summary(values, metric)
                               for metric in ("clauses", "aux_vars", "sat_calls",
                                              "decisions", "propagations", "backtracks",
                                              "runtime_s"))]
        for label, values in sorted(e4_groups.items())
    ]
    tables.append(_table(
        "E4 — đối chứng puzzle có/không extension (median puzzle medians)",
        ["Nhóm", "Số puzzle", "Clauses", "Aux vars", "SAT calls", "Decisions",
         "Propagations", "Backtracks", "Runtime (s)"], e4_rows,
    ))

    failures: list[list[Any]] = []
    for source, summaries, raw_rows in (
        ("comb", comb, read_csv(directory / "comb.csv")),
        ("seq", seq, read_csv(directory / "seq.csv")),
    ):
        by_key: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
        for row in raw_rows:
            if row["status"] != "SOLVED":
                by_key[(row["puzzle"], row["status"], row.get("error", ""))].append(row)
        for (puzzle, status, error), rows in sorted(by_key.items()):
            ids = ", ".join(str(int(row["trial"])) for row in sorted(rows, key=lambda r: int(r["trial"])))
            summary = summaries[(puzzle, "combinatorial" if source == "comb" else "sequential")]
            metrics = "; ".join(
                f"{label}: {summary[name]}" for name, label in
                (("sat_calls", "SAT"), ("decisions", "decisions"),
                 ("propagations", "propagations"), ("backtracks", "backtracks"),
                 ("steps", "steps"), ("waves", "waves"),
                 ("runtime_s", "runtime s"))
            )
            failures.append([source, puzzle, ids, status, error or "—", metrics])
    tables.append(_table(
        "Ca lỗi / stuck / timeout (liệt kê trial thực tế; chỉ số là median)",
        ["CSV", "Puzzle", "Trial", "Status", "Error", "Chỉ số lúc dừng (median)"],
        failures or [["—", "Không có", "—", "—", "—", "—"]],
    ))
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
