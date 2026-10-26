
import argparse
import csv
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

PLANNED_CASES = [f"M{m}-0{c}" for m in range(1, 5) for c in range(1, 5)]
VALID_RESULTS = ["Pass", "Fail", "Error", "Inconclusive", "Not run"]
COLUMNS = [
    "case_id", "owner", "feature", "description",
    "manual_result", "manual_time_s",
    "automated_result", "automated_time_s",
    "notes",
]

CASE_IN_NAME = re.compile(r"m([1-4])_0([1-4])", re.IGNORECASE)
FAIL_HEADER = re.compile(r"^(FAIL|ERROR): (test\w+) \(")
DURATION_LINE = re.compile(r"^\s*([\d.]+)s\s+(test\w+)\s+\(")
TEST_NAME = re.compile(r"\b(test\w+) \([\w.]+\)")


def normalise_result(value):
    """Map free text to one of VALID_RESULTS; blank stays blank."""
    v = (value or "").strip().lower()
    if not v:
        return ""
    for r in VALID_RESULTS:
        if v == r.lower():
            return r
    aliases = {"ok": "Pass", "passed": "Pass", "failed": "Fail",
               "failure": "Fail", "errored": "Error", "skipped": "Not run",
               "not executed": "Not run"}
    if v in aliases:
        return aliases[v]
    raise ValueError(f"Unknown result '{value}'. Use one of: {', '.join(VALID_RESULTS)}")


def case_id_from_test(test_name):
    m = CASE_IN_NAME.search(test_name)
    return f"M{m.group(1)}-0{m.group(2)}" if m else None


def parse_django_log(path):
    """Return ({case_id: (result, seconds)}, [unmapped test names])."""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    seen, failed, errored, durations = set(), set(), set(), {}

    for line in text.splitlines():
        for name in TEST_NAME.findall(line):
            seen.add(name)
        header = FAIL_HEADER.match(line)
        if header:
            (failed if header.group(1) == "FAIL" else errored).add(header.group(2))
        dur = DURATION_LINE.match(line)
        if dur:
            durations[dur.group(2)] = float(dur.group(1))

    results, unmapped = {}, []
    for name in sorted(seen | set(durations)):
        cid = case_id_from_test(name)
        if cid is None:
            unmapped.append(name)
            continue
        # A failing subTest makes the whole case Fail; any exception makes it Error.
        status = "Error" if name in errored else "Fail" if name in failed else "Pass"
        seconds = durations.get(name)
        prev = results.get(cid)
        if prev:  # more than one method for one case: worst result, summed time
            rank = {"Pass": 0, "Fail": 1, "Error": 2}
            status = max(prev[0], status, key=rank.get)
            if prev[1] is not None and seconds is not None:
                seconds = prev[1] + seconds
        results[cid] = (status, seconds)
    return results, unmapped


def load_rows(csv_path):
    rows = OrderedDict((cid, {c: "" for c in COLUMNS} | {"case_id": cid}) for cid in PLANNED_CASES)
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for raw in csv.DictReader(f):
            cid = (raw.get("case_id") or "").strip().upper()
            if cid not in rows:
                print(f"WARNING: ignoring unknown case id '{cid}' (only the 16 planned cases are counted)")
                continue
            for c in COLUMNS[1:]:
                rows[cid][c] = (raw.get(c) or "").strip()
            rows[cid]["manual_result"] = normalise_result(rows[cid]["manual_result"])
            rows[cid]["automated_result"] = normalise_result(rows[cid]["automated_result"])
    return rows


def to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def summarise(rows, method):
    key = f"{method}_result"
    counts = Counter(r[key] or "Not run" for r in rows.values())
    executed = sum(counts[r] for r in ("Pass", "Fail", "Error", "Inconclusive"))
    times = [to_float(r[f"{method}_time_s"]) for r in rows.values()]
    times = [t for t in times if t is not None]
    return {
        "counts": counts,
        "executed": executed,
        "pass_rate": (counts["Pass"] / executed * 100) if executed else 0.0,
        "timed": len(times),
        "total_time": sum(times),
        "mean_time": (sum(times) / len(times)) if times else None,
    }


def fmt_time(v):
    t = to_float(v)
    return f"{t:.3f}" if t is not None else "-"


def build_markdown(rows, unmapped):
    out = ["# Consolidated Test Results (16 planned cases)", "",
           "| Case | Owner | Feature | Manual result | Manual time (s) | "
           "Automated result | Automated time (s) | Notes |",
           "|---|---|---|---|---|---|---|---|"]
    for r in rows.values():
        out.append(
            f"| {r['case_id']} | {r['owner'] or '-'} | {r['feature'] or '-'} | "
            f"{r['manual_result'] or 'Not run'} | {fmt_time(r['manual_time_s'])} | "
            f"{r['automated_result'] or 'Not run'} | {fmt_time(r['automated_time_s'])} | "
            f"{r['notes'] or ''} |"
        )
    out += ["", "## Summary by execution method", "",
            "| Method | Executed | Pass | Fail | Error | Inconclusive | Not run | "
            "Pass rate | Cases timed | Total time (s) | Mean time (s) |",
            "|---|---|---|---|---|---|---|---|---|---|---|"]
    for method in ("manual", "automated"):
        s = summarise(rows, method)
        c = s["counts"]
        mean = f"{s['mean_time']:.3f}" if s["mean_time"] is not None else "-"
        out.append(
            f"| {method.capitalize()} | {s['executed']}/16 | {c['Pass']} | {c['Fail']} | "
            f"{c['Error']} | {c['Inconclusive']} | {c['Not run']} | {s['pass_rate']:.1f}% | "
            f"{s['timed']}/16 | {s['total_time']:.3f} | {mean} |"
        )
    out += ["",
            "Notes for interpretation:",
            "- Pass rate = Pass / executed cases for that method; it is NOT code coverage.",
            "- Manual times include human reading, typing and navigation; automated times "
            "measure only the test run, so the two must not be compared directly.",
            "- Django prints one failure per failing subTest, so its 'failures=N' line can "
            "exceed the number of failed cases. This table counts cases."]
    missing = [r["case_id"] for r in rows.values()
               if not r["manual_result"] or not r["automated_result"]]
    if missing:
        out += ["", f"Still missing a manual or automated result: {', '.join(missing)}"]
    if unmapped:
        out += ["", "Tests in the logs that are not one of the 16 planned cases "
                "(report separately, e.g. exploratory checks): " + ", ".join(unmapped)]
    return "\n".join(out) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--csv", default="team_results.csv")
    p.add_argument("--log", action="append", default=[])
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--out", default="consolidated_results")
    args = p.parse_args()

    if not Path(args.csv).exists():
        sys.exit(f"Cannot find {args.csv}")
    rows = load_rows(args.csv)

    unmapped_all = []
    for log in args.log:
        parsed, unmapped = parse_django_log(log)
        unmapped_all += unmapped
        for cid, (status, seconds) in parsed.items():
            row = rows[cid]
            if args.overwrite or not row["automated_result"]:
                row["automated_result"] = status
            if seconds is not None and (args.overwrite or not row["automated_time_s"]):
                row["automated_time_s"] = f"{seconds:.4f}"
        print(f"Read {len(parsed)} planned case(s) from {log}")

    md = build_markdown(rows, sorted(set(unmapped_all)))
    Path(f"{args.out}.md").write_text(md, encoding="utf-8")
    with open(f"{args.out}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows.values())
    print(md)
    print(f"Wrote {args.out}.md and {args.out}.csv")


if __name__ == "__main__":
    main()
