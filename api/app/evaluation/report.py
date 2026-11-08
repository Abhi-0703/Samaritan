"""The Markdown report written to eval/reports/<timestamp>.md."""

from __future__ import annotations

from datetime import datetime

from app.evaluation.keys import REPORTS_DIR
from app.evaluation.metrics import Counts, prf, slices
from app.evaluation.runner import CONFIGS, ConfigResult, Evaluation, summary_for

TARGETS = "overall precision at least 85%, recall at least 80%, at most 1 of 12 clean calls wrongly flagged"
SLICES = ("all", "dev", "test", "hinglish", "marathi", "noisy", "not_noisy")


def pct(x: float, defined: bool = True) -> str:
    return f"{x * 100:.0f}%" if defined else "n/a"


def _slice_row(result: ConfigResult, name: str, members: list[str]) -> str:
    s, _ = summary_for(result, members)
    c = Counts(sum(v.tp for v in s.per_rule.values()), sum(v.fp for v in s.per_rule.values()),
               sum(v.fn for v in s.per_rule.values()))  # fmt: skip
    p = prf(c)
    return (
        f"| {name} | {s.n_calls} | {pct(p.precision, c.tp + c.fp > 0)} | {pct(p.recall, c.tp + c.fn > 0)} "
        f"| {pct(p.f1, c.tp > 0)} | {c.tp} / {c.fp} / {c.fn} |"
    )


def render(ev: Evaluation, when: datetime, provenance: dict[str, dict] | None = None) -> str:
    out = [f"# Evaluation report, {when:%Y-%m-%d %H:%M} IST", ""]
    out += [
        "Tuning used the `dev` calls only. The `test` rows are the held-out result.",
        f"Targets: {TARGETS}.",
        "Matching: strict means the same rule and a start time within 5 s of the labelled moment "
        "(V1 and V8 match on rule only; a violation with no labelled time matches on rule only).",
        "",
    ]
    evaluated = sorted({o.key.test_key for r in ev.results.values() for o in r.outcomes})
    synthetic = [k for k in evaluated if (provenance or {}).get(k, {}).get("borrower") == "synthetic"]
    if synthetic:
        out += [
            f"**Synthetic borrower voice ({len(synthetic)} of {len(evaluated)} calls):** {', '.join(synthetic)}. "
            "The agent is a real person on a microphone and the borrower is a computer voice, so speaker separation "
            "on these calls is easier than on a real two-person call. Read their numbers with that in mind.",
            "",
        ]
    for w in ev.warnings:
        out.append(f"> **Warning:** {w}")
    if ev.warnings:
        out.append("")
    if ev.not_evaluated:
        out += [
            f"**Not evaluated ({len(ev.not_evaluated)}):** " + "; ".join(f"{k} ({why})" for k, why in ev.not_evaluated),
            "",
        ]

    for config in CONFIGS:
        result = ev.results.get(config)
        if result is None or not result.outcomes:
            out += [f"## {config}", "", "Not run.", ""]
            continue
        summary, roles = summary_for(result)
        keys = {o.key.test_key: o.key for o in result.outcomes}
        bases = {o.role_truth for o in result.outcomes}
        out += [
            f"## {config}",
            "",
            f"Models: STT {result.models['stt']}; LLM {result.models['llm']}. Prompt version {result.prompt_version}. "
            f"{summary.n_calls} calls.",
            "",
            f"- Overall (strict): precision {pct(summary.overall.precision)}, recall {pct(summary.overall.recall)}, "
            f"F1 {pct(summary.overall.f1)}",
            f"- Rule-level recall (ignoring time): {pct(summary.rule_level_recall)}",
            f"- Timestamp accuracy (strict hits among rule-level hits): {pct(summary.timestamp_accuracy)}",
            f"- Clean calls wrongly flagged: {summary.clean_calls_flagged} of {summary.clean_calls_total}",
            f"- Speaker-role mapping accuracy: {pct(roles)} (truth: {', '.join(sorted(bases))})",
        ]
        if summary.unlabelled:
            out.append(f"- Timestamp unlabelled for {summary.unlabelled} matched violation(s): matched on rule only.")
        out += ["", "| Slice | Calls | Precision | Recall | F1 | TP / FP / FN |", "|---|---|---|---|---|---|"]
        out += [_slice_row(result, name, members) for name, members in slices(keys).items() if members]
        out += ["", "| Rule | TP | FP | FN | Precision | Recall |", "|---|---|---|---|---|---|"]
        for rule, c in summary.per_rule.items():
            p = prf(c)
            out.append(
                f"| {rule} | {c.tp} | {c.fp} | {c.fn} | {pct(p.precision, c.tp + c.fp > 0)} "
                f"| {pct(p.recall, c.tp + c.fn > 0)} |"
            )
        failures = [(o.key, f) for o in result.outcomes for f in o.match.failures]
        out += ["", "### Known failure cases", ""]
        if not failures:
            out.append("None.")
        for key, f in failures:
            out.append(f"- `{key.test_key}` ({key.split}) {f.rule_code} {f.kind.upper()}: {f.note}")
        out.append("")
    return "\n".join(out)


def write_report(ev: Evaluation, when: datetime, directory=REPORTS_DIR, provenance: dict[str, dict] | None = None):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{when:%Y%m%d-%H%M%S}.md"
    path.write_text(render(ev, when, provenance), encoding="utf-8")
    return path
