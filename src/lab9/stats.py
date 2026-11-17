"""Statistics students implement (M2 judge calibration, M4 paired bootstrap).

Rules: a judge is a classifier -- measure it like one. A higher mean is not
"better" until the paired CI of the difference excludes 0.
Reference values to self-check are in tests/test_lab9_stats.py.
"""

from __future__ import annotations

from collections.abc import Sequence

POS = "FAIL"   # the judge's job is to FIND failures, so FAIL is the positive class


def confusion(human: Sequence[str], judge: Sequence[str]) -> dict[str, int]:
    """tp/fp/fn/tn with FAIL as positive."""
    if len(human) != len(judge):
        raise ValueError("human and judge must have the same length")
    h = [str(x).strip().upper() for x in human]
    j = [str(x).strip().upper() for x in judge]
    allowed = {"PASS", POS}
    invalid = sorted((set(h) | set(j)) - allowed)
    if invalid:
        raise ValueError(f"labels must be PASS or {POS}: {invalid}")
    return {
        "tp": sum(a == POS and b == POS for a, b in zip(h, j)),
        "fp": sum(a != POS and b == POS for a, b in zip(h, j)),
        "fn": sum(a == POS and b != POS for a, b in zip(h, j)),
        "tn": sum(a != POS and b != POS for a, b in zip(h, j)),
    }


def precision_recall(human: Sequence[str], judge: Sequence[str]) -> tuple[float, float]:
    cm = confusion(human, judge)
    precision_den = cm["tp"] + cm["fp"]
    recall_den = cm["tp"] + cm["fn"]
    precision = cm["tp"] / precision_den if precision_den else 0.0
    recall = cm["tp"] / recall_den if recall_den else 0.0
    return precision, recall


def cohen_kappa(human: Sequence[str], judge: Sequence[str]) -> float:
    """kappa = (p_o - p_e) / (1 - p_e). Raise ValueError when undefined (p_e == 1):
    a constant judge has no signal and must FAIL calibration, not pass on a technicality."""
    cm = confusion(human, judge)
    n = sum(cm.values())
    if n == 0:
        raise ValueError("kappa is undefined for empty labels")
    p_observed = (cm["tp"] + cm["tn"]) / n
    human_fail = (cm["tp"] + cm["fn"]) / n
    judge_fail = (cm["tp"] + cm["fp"]) / n
    p_expected = human_fail * judge_fail + (1 - human_fail) * (1 - judge_fail)
    denominator = 1 - p_expected
    if abs(denominator) < 1e-12:
        raise ValueError("kappa is undefined when expected agreement is 1")
    return (p_observed - p_expected) / denominator


def rogan_gladen(observed_rate: float, sensitivity: float, specificity: float) -> float:
    """Correct an observed failure rate for judge error; clip to [0, 1]."""
    rates = {
        "observed_rate": observed_rate,
        "sensitivity": sensitivity,
        "specificity": specificity,
    }
    for name, value in rates.items():
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be in [0, 1]")
    denominator = sensitivity + specificity - 1
    if abs(denominator) < 1e-12:
        raise ValueError("Rogan-Gladen is undefined when sensitivity + specificity = 1")
    corrected = (observed_rate + specificity - 1) / denominator
    return min(1.0, max(0.0, corrected))


def paired_bootstrap(a: Sequence[float], b: Sequence[float], *, n_resamples: int = 1000,
                     rng: int = 2027, confidence: float = 0.95) -> tuple[float, float, float]:
    """a[i], b[i] = per-item mean over seeds, SAME items, SAME order.
    Return (mean(a)-mean(b), lo, hi) with scipy.stats.bootstrap(paired=True, method="percentile",
    rng=numpy.random.default_rng(rng)). If a == b everywhere return (0.0, 0.0, 0.0)."""
    # TODO M4
    raise NotImplementedError


def pass_at_k(n: int, c: int, k: int) -> float:
    """Probability that AT LEAST ONE of k trials drawn from n (c of them passing) passes.
    Unbiased estimator (Chen et al. 2021): 1 - C(n-c, k) / C(n, k). Raise ValueError if k > n."""
    # TODO M6
    raise NotImplementedError


def pass_hat_k(n: int, c: int, k: int) -> float:
    """pass^k (tau-bench, Yao et al. 2024): probability that ALL k trials drawn from n pass.
    Unbiased estimator: C(c, k) / C(n, k). Raise ValueError if k > n.
    pass^k <= pass@1 <= pass@k; a reliable agent keeps pass^k close to pass@1."""
    # TODO M6
    raise NotImplementedError
