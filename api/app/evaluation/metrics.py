"""Metric maths for the evaluation (plan.md Section 9.3). Pure functions, no database, no network.

Matching, per call and rule:
1. Strict pass. An expected violation with a labelled time (any rule except V1 and V8) pairs with the nearest unused
   predicted flag of the same rule within TOLERANCE_S seconds. V1, V8 and unlabelled expectations pair with any
   unused predicted flag of the rule. Each pair is a strict true positive.
2. Rule pass. What is left over pairs by rule alone. Those pairs are rule-level true positives only: the rule was
   found, but at the wrong moment.
Unpaired expected violations are false negatives and unpaired predictions false positives, in the strict sense.
Undefined ratios (no predictions, no expected violations) are 0.0; the report shows them as "n/a".
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from app.evaluation.keys import AnswerKey, Expected

TOLERANCE_S = 5.0
RULE_ONLY = {"V1", "V8"}  # no quotable moment: V1 comes from the call time, V8 is the absence of something


@dataclass(frozen=True)
class Predicted:
    rule_code: str
    start_s: float | None
    quote: str | None = None


@dataclass
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def add(self, other: Counts) -> None:
        self.tp += other.tp
        self.fp += other.fp
        self.fn += other.fn


@dataclass(frozen=True)
class Failure:
    test_key: str
    rule_code: str
    kind: str  # fp | fn
    note: str


@dataclass
class CallMatch:
    test_key: str
    per_rule: dict[str, Counts] = field(default_factory=dict)
    rule_level_tp: int = 0
    expected_count: int = 0
    unlabelled: int = 0  # expected violations matched on rule alone because no time was labelled
    failures: list[Failure] = field(default_factory=list)

    @property
    def strict(self) -> Counts:
        total = Counts()
        for c in self.per_rule.values():
            total.add(c)
        return total


def _is_rule_only(e: Expected) -> bool:
    return e.rule_code in RULE_ONLY or e.approx_time_s is None


def _describe(p: Predicted) -> str:
    where = f" at {p.start_s:.0f} s" if p.start_s is not None else ""
    quote = f": “{p.quote[:90]}”" if p.quote else ""
    return f"flagged{where}{quote}"


def match_call(key: AnswerKey, predicted: Iterable[Predicted], tolerance: float = TOLERANCE_S) -> CallMatch:
    result = CallMatch(key.test_key, expected_count=len(key.expected))
    by_rule_pred: dict[str, list[Predicted]] = defaultdict(list)
    for p in predicted:
        by_rule_pred[p.rule_code].append(p)
    by_rule_exp: dict[str, list[Expected]] = defaultdict(list)
    for e in key.expected:
        by_rule_exp[e.rule_code].append(e)

    for rule in sorted(set(by_rule_pred) | set(by_rule_exp)):
        exps, preds = by_rule_exp[rule], by_rule_pred[rule]
        used_e: set[int] = set()
        used_p: set[int] = set()

        # strict pass: nearest pairs first, so one flag is never claimed by a farther expectation
        candidates = []
        for i, e in enumerate(exps):
            for j, p in enumerate(preds):
                if _is_rule_only(e):
                    candidates.append((1, 0.0, i, j))  # after the timed pairs, so timed ones win a shared flag
                elif p.start_s is not None and abs(p.start_s - e.approx_time_s) <= tolerance:  # type: ignore[operator]
                    candidates.append((0, abs(p.start_s - e.approx_time_s), i, j))  # type: ignore[operator]
        for _, _, i, j in sorted(candidates):
            if i in used_e or j in used_p:
                continue
            used_e.add(i)
            used_p.add(j)
            if exps[i].approx_time_s is None and rule not in RULE_ONLY:
                result.unlabelled += 1
        strict = Counts(tp=len(used_e))

        # rule pass: right rule, wrong moment
        rest_e = [i for i in range(len(exps)) if i not in used_e]
        rest_p = [j for j in range(len(preds)) if j not in used_p]
        late = min(len(rest_e), len(rest_p))
        rest_pairs = list(zip(sorted(rest_e), sorted(rest_p), strict=False))[:late]
        result.rule_level_tp += strict.tp + late

        paired_e = {i for i, _ in rest_pairs}
        paired_p = {j for _, j in rest_pairs}
        for i in rest_e:
            e = exps[i]
            hint = f" (“{e.quote_hint}”)" if e.quote_hint else ""
            if i in paired_e:
                j = dict(rest_pairs)[i]
                note = f"Found the rule but {_describe(preds[j])}; expected near {e.approx_time_s:.0f} s{hint}."
            else:
                note = f"Missed{hint}." + (f" Expected near {e.approx_time_s:.0f} s." if e.approx_time_s else "")
            result.failures.append(Failure(key.test_key, rule, "fn", note))
            strict.fn += 1
        for j in rest_p:
            p = preds[j]
            note = (
                "Flagged on a call that should be clean."
                if key.is_clean
                else ("Flagged at the wrong moment." if j in paired_p else "Not in the answer key.")
            )
            result.failures.append(Failure(key.test_key, rule, "fp", f"{note} {_describe(p).capitalize()}.".strip()))
            strict.fp += 1
        result.per_rule[rule] = strict
    return result


@dataclass(frozen=True)
class PRF:
    precision: float
    recall: float
    f1: float


def prf(c: Counts) -> PRF:
    precision = c.tp / (c.tp + c.fp) if c.tp + c.fp else 0.0
    recall = c.tp / (c.tp + c.fn) if c.tp + c.fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return PRF(precision, recall, f1)


@dataclass
class Summary:
    n_calls: int
    overall: PRF
    rule_level_recall: float
    timestamp_accuracy: float
    clean_calls_flagged: int
    clean_calls_total: int
    per_rule: dict[str, Counts]
    unlabelled: int


def slices(keys: dict[str, AnswerKey]) -> dict[str, list[str]]:
    """Slice name -> the test keys in it (plan.md Section 9.3)."""
    sel = {
        "all": lambda k: True,
        "dev": lambda k: k.split == "dev",
        "test": lambda k: k.split == "test",
        "hinglish": lambda k: k.language == "hinglish",
        "marathi": lambda k: k.language == "marathi",
        "noisy": lambda k: k.noisy,
        "not_noisy": lambda k: not k.noisy,
    }
    return {name: [t for t, k in keys.items() if f(k)] for name, f in sel.items()}


def summarise(matches: list[CallMatch], keys: dict[str, AnswerKey]) -> Summary:
    total = Counts()
    per_rule: dict[str, Counts] = defaultdict(Counts)
    rule_tp = expected = unlabelled = 0
    clean_total = clean_flagged = 0
    for m in matches:
        total.add(m.strict)
        for rule, c in m.per_rule.items():
            per_rule[rule].add(c)
        rule_tp += m.rule_level_tp
        expected += m.expected_count
        unlabelled += m.unlabelled
        if keys[m.test_key].is_clean:
            clean_total += 1
            clean_flagged += m.strict.fp > 0
    strict_tp = total.tp
    return Summary(
        n_calls=len(matches),
        overall=prf(total),
        rule_level_recall=rule_tp / expected if expected else 0.0,
        timestamp_accuracy=strict_tp / rule_tp if rule_tp else 0.0,
        clean_calls_flagged=clean_flagged,
        clean_calls_total=clean_total,
        per_rule=dict(sorted(per_rule.items())),
        unlabelled=unlabelled,
    )


def role_mapping_accuracy(results: Iterable[tuple[int | None, int | None]]) -> float:
    """Each item is (predicted agent speaker id, true agent speaker id). A call with no prediction is wrong."""
    items = list(results)
    return sum(1 for pred, truth in items if pred is not None and pred == truth) / len(items) if items else 0.0
