"""CI gate: compare a PR eval report with the main-branch baseline using the metric spec.

    python -m lab9.gate --pr reports/eval_workflow.json --baseline reports/baseline_v1.json

exit 0 = merge, exit 1 = blocked. Safety metrics: max 0, no averaging away.
Capability metrics: meet the floor AND the paired CI of (PR - main) is not entirely below 0.
Thresholds may only get stricter on the same eval-set version (ratchet).
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from lab8.console import utf8_stdio
from lab9 import stats
from lab9.eval import SPEC, load_spec, per_item


def integrity_check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> list[str]:
    """M7 (Expert): refuse to compare reports that cannot be trusted. Return a list of problems
    (empty = trustworthy). A gate that passes a broken report is worse than no gate.
    Must catch at least:
      - any metric value in pr["metrics"] that is NaN or inf
      - len(pr["rows"]) != manifest items x len(manifest seeds)   (dropped / duplicated rows)
      - the (item_id, seed) set of PR differs from the baseline's (cherry-picked seeds/items)
      - pr["evaluator_failures"] non-empty, or a row whose value for a graded spec metric is
        None (a crashed grader silently scores as "missing" and drops out of the mean)
      - base_spec given and a threshold in spec is LOOSER than in base_spec for the same
        eval-set version (ratchet: max may not rise, min may not fall, a blocking metric may
        not become non-blocking, a metric may not disappear; the same for spec["slices"],
        including dropping no_significant_drop)
      - an item's slice tags in PR rows differ from the baseline's (relabelling an item out of a
        slice hides its regression from the slice gate)"""
    problems: list[str] = []

    # 1. NaN or inf in pr["metrics"]
    for m, v in pr.get("metrics", {}).items():
        if v is None:
            problems.append(f"metric {m} is None")
        elif isinstance(v, (int, float)) and (math.isnan(v) or math.isinf(v)):
            problems.append(f"metric {m} is not finite ({v})")

    # 2. Row count matching manifest
    manifest = pr.get("manifest") or {}
    items_count = manifest.get("items")
    seeds = manifest.get("seeds") or []
    if items_count is not None and len(pr.get("rows", [])) != items_count * len(seeds):
        problems.append(f"row count {len(pr.get('rows', []))} != manifest items ({items_count}) x seeds ({len(seeds)})")

    # 3. (item_id, seed) set match with baseline
    pr_rows = pr.get("rows", [])
    base_rows = base.get("rows", [])
    pr_pairs = [(r.get("item_id"), r.get("seed")) for r in pr_rows]
    base_pairs = [(r.get("item_id"), r.get("seed")) for r in base_rows]
    if len(pr_pairs) != len(set(pr_pairs)):
        problems.append("duplicate (item_id, seed) rows in PR")
    if set(pr_pairs) != set(base_pairs):
        problems.append(f"(item_id, seed) set differs from baseline (pr={len(set(pr_pairs))}, base={len(set(base_pairs))})")

    # 4. evaluator_failures or None values for graded spec metrics
    if pr.get("evaluator_failures"):
        problems.append(f"evaluator_failures is non-empty ({len(pr['evaluator_failures'])} failures)")
    spec_metric_ids = {m["id"] for m in spec.get("metrics", [])}
    for r in pr_rows:
        for mid in spec_metric_ids:
            if mid in r and r[mid] is None:
                problems.append(f"row {r.get('item_id')}@{r.get('seed')} has None for spec metric {mid}")
                break
        if any("has None for spec metric" in p for p in problems):
            break

    # 5. Item slice tags match baseline
    base_slices = {(r.get("item_id"), r.get("seed")): sorted(r.get("slices") or []) for r in base_rows}
    for r in pr_rows:
        key = (r.get("item_id"), r.get("seed"))
        if key in base_slices and sorted(r.get("slices") or []) != base_slices[key]:
            problems.append(f"slice tags for {key} differ from baseline ({r.get('slices')} != {base_slices[key]})")
            break

    # 6. Ratchet check when base_spec is provided
    if base_spec is not None and spec.get("eval_set_version") == base_spec.get("eval_set_version"):
        base_metrics = {m["id"]: m for m in base_spec.get("metrics", [])}
        pr_metrics = {m["id"]: m for m in spec.get("metrics", [])}
        for mid, bm in base_metrics.items():
            if mid not in pr_metrics:
                problems.append(f"metric {mid} removed from spec (ratchet)")
                continue
            pm = pr_metrics[mid]
            if bm.get("blocking") and not pm.get("blocking"):
                problems.append(f"metric {mid} became non-blocking (ratchet)")
            bth, pth = bm.get("threshold", {}), pm.get("threshold", {})
            if "min" in bth and ("min" not in pth or pth["min"] < bth["min"]):
                problems.append(f"metric {mid} min threshold lowered ({pth.get('min')} < {bth['min']}) (ratchet)")
            if "max" in bth and ("max" not in pth or pth["max"] > bth["max"]):
                problems.append(f"metric {mid} max threshold raised ({pth.get('max')} > {bth['max']}) (ratchet)")
            if "max_increase" in bth and ("max_increase" not in pth or pth["max_increase"] > bth["max_increase"]):
                problems.append(f"metric {mid} max_increase raised ({pth.get('max_increase')} > {bth['max_increase']}) (ratchet)")
            if bth.get("no_significant_drop") and not pth.get("no_significant_drop"):
                problems.append(f"metric {mid} dropped no_significant_drop (ratchet)")

        base_slices_spec = {(s["name"], s.get("metric")): s for s in base_spec.get("slices", [])}
        pr_slices_spec = {(s["name"], s.get("metric")): s for s in spec.get("slices", [])}
        for skey, bs_sl in base_slices_spec.items():
            if skey not in pr_slices_spec:
                problems.append(f"slice {skey[0]}/{skey[1]} removed from spec (ratchet)")
                continue
            ps_sl = pr_slices_spec[skey]
            if bs_sl.get("blocking") and not ps_sl.get("blocking"):
                problems.append(f"slice {skey[0]}/{skey[1]} became non-blocking (ratchet)")
            if "min" in bs_sl and ("min" not in ps_sl or ps_sl["min"] < bs_sl["min"]):
                problems.append(f"slice {skey[0]}/{skey[1]} min threshold lowered (ratchet)")
            if "max" in bs_sl and ("max" not in ps_sl or ps_sl["max"] > bs_sl["max"]):
                problems.append(f"slice {skey[0]}/{skey[1]} max threshold raised (ratchet)")
            if bs_sl.get("no_significant_drop") and not ps_sl.get("no_significant_drop"):
                problems.append(f"slice {skey[0]}/{skey[1]} dropped no_significant_drop (ratchet)")

    return problems


def slice_check(pr: dict, base: dict, spec: dict) -> tuple[list[str], list[str]]:
    """M5 (Advanced): an average can hide a regression on a small, important slice.
    For each entry of spec["slices"] ({"name", "metric", "min"?, "no_significant_drop"?, "blocking"}):
      - value = mean of per_item(pr, metric, slice_name=name)
      - fail if below "min", or if no_significant_drop and the paired CI over the slice's items
        lies entirely below 0
    Return (blocked ids like "slice:money_movement/pass_rate", report lines)."""
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for s in spec.get("slices", []):
        name, metric = s["name"], s["metric"]
        mid = f"slice:{name}/{metric}"
        pr_items = per_item(pr, metric, slice_name=name)
        base_items = per_item(base, metric, slice_name=name)
        if not pr_items:
            continue
        val = sum(pr_items.values()) / len(pr_items)
        verdict, note = "ok", ""
        if "min" in s and val < s["min"]:
            verdict = "fail"
        if "max" in s and val > s["max"]:
            verdict = "fail"
        if s.get("no_significant_drop"):
            keys = sorted(set(pr_items) & set(base_items))
            if keys:
                d, lo, hi = stats.paired_bootstrap(
                    [pr_items[k] for k in keys],
                    [base_items[k] for k in keys],
                    n_resamples=bs.get("n_resamples", 1000),
                    rng=bs.get("rng", 2027),
                )
                note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
                if hi < 0:
                    verdict = "fail"
        blocking = s.get("blocking", True)
        if verdict != "ok" and blocking:
            blocked.append(mid)
        label = {"ok": "ok", "fail": "BLOCK" if blocking else "warn"}.get(verdict, verdict)
        th_desc = {k: v for k, v in s.items() if k in ("min", "max", "no_significant_drop", "blocking")}
        lines.append(f"  {mid:<22} {val:.4f}   {json.dumps(th_desc):<40} {note:<28} {label}")
    return blocked, lines


def check(pr: dict, base: dict, spec: dict, base_spec: dict | None = None) -> tuple[list[str], list[str]]:
    if pr["manifest"]["eval_set_sha"] != base["manifest"]["eval_set_sha"]:
        return ["eval_set_sha"], ["  EVAL SET differs from the baseline's: re-run the baseline on the same eval set"]
    problems = integrity_check(pr, base, spec, base_spec)
    if problems:
        return ["integrity"], [f"  INTEGRITY {p}" for p in problems]
    blocked, lines = [], []
    bs = spec.get("bootstrap", {})
    for m in spec["metrics"]:
        mid, th, val = m["id"], m.get("threshold", {}), pr["metrics"].get(m["id"])
        verdict, note = "ok", ""
        if val is None:
            verdict = "missing"
        elif "max" in th and val > th["max"]:
            verdict = "fail"
        elif "min" in th and val < th["min"]:
            verdict = "fail"
        elif "max_increase" in th and base["metrics"].get(mid):
            if val > base["metrics"][mid] * (1 + th["max_increase"]):
                verdict = "fail"
        if th.get("no_significant_drop") and val is not None:
            a, b = per_item(pr, mid), per_item(base, mid)
            keys = sorted(set(a) & set(b))
            d, lo, hi = stats.paired_bootstrap([a[k] for k in keys], [b[k] for k in keys],
                                               n_resamples=bs.get("n_resamples", 1000), rng=bs.get("rng", 2027))
            note = f"Δ {d:+.3f} CI [{lo:+.3f}, {hi:+.3f}]"
            if hi < 0:
                verdict = "fail"
        if verdict != "ok" and m.get("blocking"):
            blocked.append(mid)
        label = {"ok": "ok", "missing": "MISSING"}.get(verdict, "BLOCK" if m.get("blocking") else "warn")
        lines.append(f"  {mid:<22} {val!s:<8} {json.dumps(th):<40} {note:<28} {label}")
    if spec.get("slices"):
        sb, sl = slice_check(pr, base, spec)
        blocked += sb
        lines += sl
    return blocked, lines


def main(argv: list[str] | None = None) -> int:
    utf8_stdio()
    ap = argparse.ArgumentParser(prog="lab9.gate")
    ap.add_argument("--pr", required=True)
    ap.add_argument("--baseline", required=True)
    ap.add_argument("--spec", default=str(SPEC))
    ap.add_argument("--base-spec", help="metric spec on main, for the ratchet check (M7)")
    args = ap.parse_args(argv)
    pr = json.loads(Path(args.pr).read_text(encoding="utf-8"))
    base = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    base_spec = load_spec(Path(args.base_spec)) if args.base_spec else None
    blocked, lines = check(pr, base, load_spec(Path(args.spec)), base_spec)
    print(f"gate: PR {pr['run_id']} vs main {base['run_id']} · eval set {pr['manifest']['eval_set_sha']}")
    print("\n".join(lines))
    if blocked:
        print(f"exit 1 — blocked: {', '.join(blocked)}")
        return 1
    print("exit 0 — merge")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
