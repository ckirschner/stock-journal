"""The metric bank — what every value *is*.

The bank (config/metric-bank.yaml) defines each measure: its label, unit,
format, how it is derived, and the plain-language explanation that must
accompany it. It holds no thresholds and no decision power, because deciding
is a strategy's job and the same host has to serve strategies that contradict
each other.

This module is the only reader of that file. It ships with the program rather
than living in the user's data directory: the bank is part of what the
program *is*, and a measure's definition is not a user setting.

**A measure definition is a rule, so a change to one is recorded.** It ships
with the program and is a file on the user's machine that this program re-reads
whenever its mtime moves; changing a formula is exactly as easy as changing a
threshold, and only one of those was on any record. What a measure computes,
what it refuses on, how it is estimated and which industries it declines all
decide what every exit demands, in every journal.

So the file carries a `version` and a `changelog`, the way a strategy's
values.yaml does, and `definitions` below hands a journal the state it stamps
and compares against. The version is not what makes a change detectable — the
stamp holds the definitions themselves, so an edit with no bump is caught
anyway, which is the case this exists for. It decides who owes the sentence:
an author who bumps it has already written one, and an edit made in place
leaves the person who made it to say what it was for.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from ruamel.yaml import YAML

APP_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = APP_DIR / "config"

_yaml = YAML()  # round-trip: keeps comments and key order for anyone reading
_yaml.preserve_quotes = True


def bank_path(name: str) -> Path:
    return CONFIG_DIR / (name + ".yaml")


def load_yaml(path):
    with open(path, encoding="utf-8") as f:
        return _yaml.load(f)


def to_plain(node):
    """Strip ruamel types so nothing framework-shaped crosses a boundary."""
    if isinstance(node, dict):
        return {str(k): to_plain(v) for k, v in node.items()}
    if isinstance(node, (list, tuple)):
        return [to_plain(v) for v in node]
    if node is None or isinstance(node, bool):
        return node
    if isinstance(node, int):
        return int(node)
    if isinstance(node, float):
        return float(node)
    return str(node)


_bank_cache: dict = {}

# The version on disk that this program refused, per bank name, and why. Kept
# beside the cache above rather than raised through every caller, because the
# two facts a reader needs — what is wrong, and what the program is doing
# meanwhile — are one answer and used to be neither.
#
# A strategy that fails to load is skipped with a legible message and the
# others still load; that is engine/strategy_loader.py and it has always been
# the rule for the other file a user edits. This one raised. It raised through
# `meta()`, which app.get_state calls with nothing around it, so a single
# malformed line took the window down to its boot placeholder — no journal
# list, no tabs, no way back except finding the file and fixing it blind, with
# no message naming where. There is no "skip" available for the bank, so the
# equivalent is this: refuse the new version, say which entry and which line,
# and go on serving the last one that loaded.
_bank_refused: dict = {}

# Kinds whose estimator reads a fixed-length window of annual observations, so
# `observations` says something and its absence is a hole. A streak has no
# fixed window and may leave it out; a reading at one date or over a trailing
# window has no annual observations to count, and stating one would be noise.
_WINDOWED = ("averaged", "median", "range", "cumulative")
_UNWINDOWED = ("instant", "trailing", "assessed")


# ---------------------------------------------------------------------------
# What answers a measure, and how the answer renders.
#
# `kind` says which of two surfaces an entry belongs to: a formula in
# engine/compute.py, or a question the user answers on their own security's
# page. Everything downstream branches on it — engine/context.py serves a
# qualitative entry from the dated judgement record and never from the
# computed layer, engine/judgements.py decides what is even storable from it,
# and the interface asks the question. It was the one word in an entry that
# nothing checked, while `estimator.kind` beside it was checked by name: a
# typo made a judgement look computable, and the measure came back "this host
# has no computation for it" — an absence pointing at a missing formula for a
# question nobody was ever asked.
#
# The two surfaces, and the estimator each one can be read by — because
# `qualitative` and `estimator: assessed` are the same fact said twice, and
# two ways of saying one thing is how they come apart. Declaring one without
# the other now fails to load.
#
# `assessed` is the reserved word and the rest is derived, so a kind of
# estimator added to engine/contract.py is available to a computed measure
# without being listed again here. A second copy of that list is the thing
# this check exists to refuse.
_ASSESSED = "assessed"
_KINDS = ("computed", "qualitative")


def _reads(kind: str) -> frozenset:
    """The estimator kinds one sort of entry can honestly be read by."""
    from .contract import ESTIMATORS               # local: bank loads first
    if kind == "qualitative":
        return frozenset({_ASSESSED})
    return frozenset(ESTIMATORS) - {_ASSESSED}


def _check_rendering(entry) -> list:
    """Everything wrong with one entry's `kind`, `unit` and `format`.

    Three words that decide what a reader is shown, none of which was read at
    load. The bank states the rule for the third of them in its own header —
    a qualitative entry carries a yes/no — and nothing enforced it, so a
    fourth judgement declaring `unit: percent` would have rendered a moat
    assessment as "100.0%" and a `format` over it would have printed a 1.
    That is the failure this file exists to refuse, sitting in this file.
    """
    from .contract import EVIDENCE_UNITS           # local: bank loads first
    from . import judgements                       # local: reads the bank
    eid = str(entry.get("id"))
    kind = str(entry.get("kind") or "")
    problems = []

    if kind not in _KINDS:
        return [f'{eid} declares kind "{kind or "nothing"}", which is not one '
                f'of {", ".join(_KINDS)}. A measure is worked out from the '
                "filings or it is a question you answer; there is no third "
                "surface, and adding one is a host change in engine/bank.py."]
    est = str((entry.get("estimator") or {}).get("kind") or "")
    if est and est not in _reads(kind):
        problems.append(
            f'{eid} is declared `{kind}` and read by a "{est}" estimator, '
            "which cannot answer it. "
            + (f'A judgement is `{_ASSESSED}` — nothing here reads a window '
               "of one." if kind == "qualitative" else
               f'`{_ASSESSED}` means the reader recorded it, which is what '
               "`kind: qualitative` says. One of the two is wrong."))

    unit = entry.get("unit")
    if unit is None:
        problems.append(
            f"{eid} declares no `unit`. A unit is how a screen renders the "
            "figure, and without one it falls back to printing the raw "
            "value — which reads `True` for an assessment and a bare number "
            "for everything else.")
        return problems
    if str(unit) not in EVIDENCE_UNITS:
        return problems + [
            f'{eid} declares unit "{unit}", which is not one of '
            + ", ".join(EVIDENCE_UNITS) + ". Adding a unit is a host change "
            "in engine/contract.py, never a new word here."]
    if kind == "qualitative" and str(unit) != judgements.UNIT:
        problems.append(
            f"{eid} is answered rather than computed, so what it carries is "
            f'a mark — unit `{judgements.UNIT}`, never "{unit}".')
    if str(unit) == judgements.UNIT and entry.get("format") is not None:
        problems.append(
            f"{eid}: a format is for numbers, and running a yes/no through "
            "one prints a 1.")
    return problems


def _check_window(eid, kind, window) -> list:
    """Everything wrong with one entry's `window`.

    `window` says what a measure's reading is JUDGED AGAINST, where that is a
    window of fiscal years and the kind names something else. It exists
    because `kind` answers "what can one more reading do" and robustness
    answers "could one fiscal year be carrying this", and on a measure whose
    legs run at different speeds those are different questions — see
    contract.WINDOW_STATISTICS.

    Refused on a kind that already names a window, because then there would
    be two places to say one thing and they would come apart. That is the
    failure this file exists to refuse, and it has happened here before.
    """
    from .contract import WINDOW_STATISTICS       # local: bank loads first
    if kind in WINDOW_STATISTICS:
        return [f"{eid}: a {kind} estimator already names the window it "
                "reads, and `observations` says how long it is. A second "
                "`window` beside it is the same fact declared twice, which "
                "is how the two come to disagree."]
    if not isinstance(window, dict):
        return [f"{eid}: `window` is a mapping of `statistic` and "
                "`observations` — what this reading is judged against."]
    unknown = set(window) - {"statistic", "observations"}
    if unknown:
        return [f"{eid}: a window carries `statistic` and `observations` and "
                "nothing else; found " + ", ".join(sorted(unknown)) + "."]
    stat = str(window.get("statistic") or "")
    if stat not in WINDOW_STATISTICS:
        return [f'{eid}: `window.statistic` is "{stat or "nothing"}", which '
                "is not one of " + ", ".join(WINDOW_STATISTICS)
                + " — how the fiscal years this reading is judged against "
                  "are summarised. Adding one is a host change in "
                  "engine/contract.py."]
    obs = window.get("observations")
    if not isinstance(obs, int) or isinstance(obs, bool) or obs < 2:
        return [f"{eid}: `window.observations` counts the annual "
                "observations in the window, so it is a whole number of at "
                "least two — a three-point median and a five-point one do "
                "not resist an outlier equally, and that is the whole reason "
                "this is declared."]
    return []


def _check_estimator(entry) -> list:
    """Everything wrong with one entry's estimator declaration.

    Refused at load rather than tolerated, because what follows from it is
    how much evidence a breach of that measure needs. A missing estimator
    would have to fall back to something, and every fallback is either the
    strict one — which silently stops exits firing — or the loose one, which
    silently fires them on a single year. Both are quiet, and quiet is the
    failure this file exists to refuse.
    """
    from .contract import ESTIMATORS               # local: bank loads first
    eid = str(entry.get("id"))
    node = entry.get("estimator")
    if not isinstance(node, dict):
        return [f'{eid} declares no `estimator`. Every entry says how it is '
                f'read — one of {", ".join(ESTIMATORS)} — because how much '
                "evidence a breach of it needs is derived from that."]
    kind = str(node.get("kind") or "")
    if kind not in ESTIMATORS:
        return [f'{eid} declares estimator kind "{kind or "nothing"}", which '
                f'is not one of {", ".join(ESTIMATORS)}. Adding a kind is a '
                "host change in engine/contract.py, never a new word here."]
    unknown = set(node) - {"kind", "observations", "window"}
    if unknown:
        return [f"{eid}: an estimator carries `kind`, `observations` and "
                "`window` and nothing else; found "
                + ", ".join(sorted(unknown)) + "."]
    window = node.get("window")
    if window is not None:
        problems = _check_window(eid, kind, window)
        if problems:
            return problems
    obs = node.get("observations")
    if obs is not None and (not isinstance(obs, int) or isinstance(obs, bool)
                            or obs < 2):
        return [f"{eid}: `observations` counts the annual observations the "
                "estimator reads, so it is a whole number of at least two."]
    if kind in _WINDOWED and obs is None:
        return [f"{eid}: a {kind} estimator reads a window of fixed length, "
                "so it has to say how many annual observations are in it — "
                "a three-point median and a five-point one do not resist an "
                "outlier equally."]
    if kind in _UNWINDOWED and obs is not None:
        return [f"{eid}: a {kind} estimator reads no window of annual "
                "observations, so `observations` says nothing about it."]
    return []


# ---------------------------------------------------------------------------
# Applicability — the one condition in this file the HOST evaluates.
#
# Every entry may say when it does not mean anything for a filer. Two kinds of
# condition, and the difference is who refuses:
#
#   industry: [class ids]   The host refuses, BEFORE the formula runs, from
#                           the industry code the SEC publishes. Nothing about
#                           the company's figures is consulted, because
#                           nothing about them could change the answer.
#   data: <prose>           The formula refuses, from the figures themselves —
#                           a negative denominator, a base too small to
#                           compound from. Stated here so a reader can find
#                           out why a measure reads absent, and enforced where
#                           the arithmetic is.
#   undetected: <prose>     Nobody refuses. The condition is real and neither
#                           the code nor the figures can tell whether it holds
#                           — a consolidated captive finance arm is the one
#                           case, and it sits outside the industry band
#                           entirely because the filer is an automaker. It
#                           carries `needs`, saying what it would take, so the
#                           gap is a standing request against the host rather
#                           than a shrug; and it is drawn where the reader can
#                           see it, saying in as many words that this is
#                           theirs to check.
#
#                           It is deliberately unpleasant to declare. The
#                           alternative was moving these into `misfires`,
#                           where they would read as something a reader can
#                           weigh — and this is not that. It is a number that
#                           may be describing a different company, with
#                           nothing in the program able to say.
#
# Why the first is a key and not a sentence. It sat here as prose for as long
# as this file has existed, flagged untestable, and nothing ever checked it:
# a lender's debt-to-equity read 1.4x while its assets were seven times its
# equity, because deposits are not debt, and it passed. Prose that nothing
# reads is not a condition, it is a note about one. A structured key is
# checkable, and an author who writes a kind of company into `data` — where
# nothing would check it — is refused at load with the fix named.
#
# The propagation rule below is the other half. A measure built on a
# meaningless one is meaningless, so an entry that consumes a gated entry must
# be gated at least as widely. Left to an author to remember, that is exactly
# the check nobody performs on the day they add the fifty-ninth measure.
# ---------------------------------------------------------------------------

# The three forms, and what each one MEANS to a reader — one table, because
# the sentence and the word have to move together. They did not: the loader
# accepted three forms and the Metrics page held a two-way branch, so an
# `undetected` condition rendered as "refused by the calculation itself, from
# the figures", which is the exact inverse of what the form is for. Nothing
# refuses these and nothing can; that is the whole of why they are unpleasant
# to declare. A reader was being told the program had checked.
#
# Keeping the sentence here rather than in the view is the same argument
# `bank_view` already makes about industry class names: those words are the
# host's, a second copy in the interface is a copy that drifts, and a view
# holding a table of forms is a view that has to be edited when a form is
# added. Now a fourth form cannot be added without its sentence, because the
# thing the loader accepts and the thing the reader is shown are one object.
_NMW_FORMS = {
    "industry":
        "Settled from the industry code the SEC publishes, before anything "
        "is computed. This measure reports not applicable for such a filer "
        "rather than a number.",
    "data":
        "Refused by the calculation itself, from the figures. This measure "
        "reports absent for a filer whose figures read this way.",
    "undetected":
        "Nothing refuses this one. Neither this program nor the figures it "
        "reads can tell whether it holds, so the measure reports a number "
        "either way — this one is yours to check in the filing.",
}

# The nouns that name a kind of company this host can settle from a published
# industry code. Written out rather than derived from INDUSTRY_CLASSES,
# because deriving it is worse: the nouns there read "property companies and
# REITs", and a list built by splitting that would refuse any condition
# mentioning a company or a property. tests/test_applicability.py checks that
# every class the host names is reachable from a word here, so a class added
# later cannot slip past this without the test saying so.
_CLASSIFIABLE_WORDS = ("bank", "banks", "lender", "lenders", "insurer",
                       "insurers", "reit", "reits", "financial company",
                       "financial companies")


def _classes_named(entry) -> set:
    """Every industry class one entry declares itself not meaningful for."""
    out = set()
    for item in (entry.get("not_meaningful_when") or []):
        if isinstance(item, dict) and isinstance(item.get("industry"), list):
            out.update(str(c) for c in item["industry"])
    return out


def _check_applicability(entry) -> list:
    """Everything wrong with one entry's `not_meaningful_when`."""
    from .contract import INDUSTRY_CLASSES         # local: bank loads first
    eid = str(entry.get("id"))
    items = entry.get("not_meaningful_when")
    if items is None:
        return []
    if not isinstance(items, list) or not items:
        return [f"{eid}: `not_meaningful_when` is a non-empty list of the "
                "conditions under which this measure does not mean anything. "
                "An empty one states nothing, which is what leaving it out "
                "already does."]
    problems, seen = [], set()
    for i, item in enumerate(items):
        where = f"{eid}, not_meaningful_when {i + 1}"
        if not isinstance(item, dict):
            problems.append(f"{where}: each condition is a mapping.")
            continue
        unknown = set(item) - {"because", "needs", *_NMW_FORMS}
        if unknown:
            problems.append(
                f"{where}: a condition carries `because` and exactly one of "
                + ", ".join(f"`{k}`" for k in _NMW_FORMS) + "; found "
                + ", ".join(sorted(map(str, unknown)))
                + ". Unknown keys fail loudly rather than silently doing "
                  "nothing.")
        forms = [k for k in _NMW_FORMS if k in item]
        if len(forms) != 1:
            # Silent where a key was already refused above: an entry written
            # in a shape this file no longer accepts gets one sentence about
            # what it said, not a second about what it failed to say.
            if not unknown:
                problems.append(
                    f"{where}: say exactly one of `industry`, which the host "
                    "refuses on before the formula runs; `data`, which the "
                    "formula refuses on itself; or `undetected`, where the "
                    "condition is real and nothing here can tell. Never two "
                    "of them and never none.")
            continue
        if not str(item.get("because") or "").strip():
            problems.append(
                f"{where}: `because` says, in plain language, why the measure "
                "means nothing here. A refusal a reader cannot understand "
                "teaches them that the tool is broken.")
        # `needs` says what it would take to settle a condition nobody can
        # settle, so it belongs to `undetected` and to nothing else. Checked
        # here rather than inside the else-branch below, where it caught
        # `data` and let `industry` through — the view renders `needs`
        # wherever it appears, so one on a refused condition would print a
        # standing request against the host for a question the host answers.
        if forms[0] != "undetected" and "needs" in item:
            problems.append(
                f"{where}: `needs` belongs to an undetected condition, which "
                "is the only kind nobody can settle. This one is refused by "
                + ("the host, before the formula runs"
                   if forms[0] == "industry" else "the formula itself")
                + ", so nothing is owed.")
        if forms[0] == "industry":
            cls = item["industry"]
            if not isinstance(cls, list) or not cls:
                problems.append(
                    f"{where}: `industry` is a non-empty list of the kinds of "
                    "company this measure cannot describe.")
                continue
            for c in cls:
                if c not in INDUSTRY_CLASSES:
                    problems.append(
                        f'{where}: "{c}" is not one of '
                        + ", ".join(INDUSTRY_CLASSES)
                        + " — the kinds of company this host can tell apart "
                          "from a filer's published industry code. Adding one "
                          "is a host change in engine/contract.py.")
                elif c in seen:
                    problems.append(
                        f'{where}: "{c}" is already declared above. Two '
                        "reasons for one class means one of them is never "
                        "shown.")
                else:
                    seen.add(c)
        else:
            form = forms[0]
            prose = str(item.get(form) or "").strip()
            if not prose:
                problems.append(
                    f"{where}: `{form}` says which condition this is — "
                    + ("which reading of the figures the formula refuses on."
                       if form == "data" else
                       "what about the filer nothing here can detect."))
                continue
            if form == "undetected" and not str(
                    item.get("needs") or "").strip():
                problems.append(
                    f"{where}: an undetected condition carries `needs`, "
                    "saying what it would take to settle it. A gap with no "
                    "sentence about closing it is a shrug, and a shrug is "
                    "not a request against anything.")
            hit = [w for w in _CLASSIFIABLE_WORDS
                   if _names_a_kind(prose.lower(), w)]
            if hit and form == "data":
                problems.append(
                    f'{where}: this names a kind of company ("{hit[0]}"), and '
                    "`data` is prose the formula owns — nothing here would "
                    "ever check it, which is how these conditions came to sit "
                    "unenforced for as long as this file has existed. Say it "
                    "as `industry: [...]` instead, or as `undetected` where "
                    "the kind of filer sits outside the codes this host can "
                    "read.")
    return problems


def _names_a_kind(prose: str, word: str) -> bool:
    """Whether prose names a kind of company, on whole words only.

    Whole words because "blank" contains "bank" and "banking covenant" does
    not describe a filer that is one.
    """
    if " " in word:
        return word in prose
    parts = "".join(c if c.isalpha() else " " for c in prose).split()
    return word in parts


def _check_propagation(entries) -> list:
    """Every entry that consumes a gated entry without being gated itself.

    The distance between a number and a meaningless one is meaningless, and
    so is the ratio, the median and the spread. An author gating a leaf
    measure has no way to see the four entries built on top of it, so the
    file refuses to load rather than serving four confident numbers whose
    ingredient was refused.
    """
    gated = {str(e.get("id")): _classes_named(e) for e in entries}
    problems = []
    for e in entries:
        eid = str(e.get("id"))
        mine = gated.get(eid) or set()
        for src in ((e.get("inputs") or {}).get("entries") or []):
            theirs = gated.get(str(src)) or set()
            missing = sorted(theirs - mine)
            if missing:
                problems.append(
                    f"{eid} is built on {src}, which does not mean anything "
                    "for " + ", ".join(missing) + " — so neither does this. "
                    "Declare the same classes under its own "
                    "`not_meaningful_when`, with the reason this measure's "
                    "reader needs rather than a copy of that one's.")
    return problems


_QUOTED = "quoted"


def _check_clock(entries) -> list:
    """Every entry whose estimator kind disagrees with whether its formula
    reads a price.

    The one contradiction between a declaration and the arithmetic under it
    that can be settled exactly, so it is settled here rather than pinned by
    a test: which clock a breach is confirmed on follows from it, and an
    entry that gets it wrong is either an exit waiting a quarter on a number
    that moves every session, or one firing on two sessions of a figure that
    only changes when a filing arrives. Both are quiet.

    It is a refusal at load and not a lint because the bank is a file on the
    user's machine that this program re-reads when its mtime moves. A rule
    that only runs under pytest is not in force where the file is edited.

    Silent for anything the host cannot resolve — an entry with no formula,
    or a compute module that will not parse. This check is here to catch a
    wrong word, never to be the reason nothing loads.
    """
    try:
        from . import compute                     # local: compute reads this
        priced = compute.price_driven_entries()
        known = set(compute.REGISTRY)
    except Exception:                             # noqa: BLE001
        return []
    problems = []
    for e in entries:
        eid = str(e.get("id"))
        if eid not in known:
            continue
        kind = str((e.get("estimator") or {}).get("kind") or "")
        if not kind:
            continue                              # _check_estimator has it
        if eid in priced and kind != _QUOTED:
            problems.append(
                f'{eid} is declared "{kind}", but its computation reads a '
                "quoted price — so it has a new reading every session, and a "
                f'"{kind}" reading is confirmed over filings. A breach of it '
                "would wait a quarter while the thing being watched moved "
                f'every day. Declare `kind: {_QUOTED}`.')
        elif eid not in priced and kind == _QUOTED:
            problems.append(
                f'{eid} is declared "{_QUOTED}", which says a market price '
                "is in it and its readings are trading days — and its "
                "computation reads no price. Confirming it over sessions "
                "would count the same filing figure once a day. Declare the "
                "kind that names the leg a new filing replaces.")
    return problems


def _check_release(doc) -> list:
    """Everything wrong with the file's `version` and `changelog`.

    The same rule the strategy contract already makes, for the same reason and
    in the same shape: a version that does not say what changed is refused,
    because the record of rule changes depends on it — see
    contract.validate_declaration.

    It is checkable here, with no history on hand, precisely because it asks
    nothing about the previous release. Whether the version SHOULD have moved
    is a question only a journal can answer, and it answers it by comparing
    stamped definitions rather than by trusting this number.
    """
    version = doc.get("version")
    problems = []
    if not (isinstance(version, int) and not isinstance(version, bool)
            and version >= 1):
        problems.append(
            "`version` must be a whole number starting at 1 — it is what "
            "tells a release of these definitions from an edit made in "
            "place, and therefore who is asked to say what a change was for.")
        version = None
    log = doc.get("changelog")
    if not isinstance(log, dict) or not log:
        return problems + [
            "`changelog` must map each version number to a sentence saying "
            "what changed in that version. A definition decides what every "
            "exit demands, and the host can see one move without being able "
            "to say what the move meant — so it quotes the person who can."]
    for k, v in log.items():
        if not (isinstance(k, int) and not isinstance(k, bool)) \
                or not str(v or "").strip():
            problems.append("`changelog` entries map a version number to "
                            f"non-empty text; {k!r} does not.")
    if version is not None and version not in log:
        problems.append(
            f"version {version} has no changelog entry. A version that does "
            "not say what changed is refused — every journal quotes this line "
            "when it records that the measures moved under it.")
    return problems


def _at(node, path) -> str:
    """"metric-bank.yaml line 232" for a parsed node, or the file name alone.

    The round-trip parser records where every entry started, and the whole
    point of refusing an edit is that the person who made it can go back to
    it. A message naming the entry is only useful to somebody who can already
    find the entry; a message naming the line is useful to somebody looking at
    a file they have just broken. Best effort by design — a node with no
    position still gets a sentence, because a missing line number must never
    be the reason a problem goes unreported.
    """
    line = getattr(getattr(node, "lc", None), "line", None)
    if isinstance(line, int) and not isinstance(line, bool):
        return f"{path.name} line {line + 1}"
    return path.name


def _problems(doc, path) -> list:
    """Everything wrong with a parsed bank document, each sentence saying
    where it is."""
    schema = str(doc.get("schema") or "")
    if not schema.startswith("ledger.metric-bank/"):
        return [f'{path.name} does not declare a metric-bank schema '
                f'(found "{schema or "nothing"}").']
    entries = list(doc.get("entries") or [])
    problems = [f"{_at(e, path)}: {p}" for e in entries
                for p in _check_estimator(e) + _check_applicability(e)
                + _check_rendering(e)]
    # The three below read across entries or read the file as a whole, so no
    # single line is the answer; each names the entries it is about instead.
    problems += [f"{path.name}: {p}" for p in
                 _check_propagation(entries) + _check_clock(entries)
                 + _check_release(doc)]
    return problems


def _refusal_message(path, problems) -> str:
    return (f"{path.name} cannot be loaded:\n  " + "\n  ".join(problems))


def load_bank(name: str = "metric-bank"):
    """The bank as it should be read right now.

    Which is the version on disk when that version loads, and the last version
    that loaded when it does not. A refusal is recorded in `_bank_refused` and
    reported through `refusal()` — see the note above that dict for why this
    does not raise past the first load.
    """
    path = bank_path(name)
    if not path.exists():
        raise FileNotFoundError(
            f'The metric bank "{name}" was not found at {path}.')
    # Round-trip parsing a 2,000-line YAML costs real time and a render asks
    # for the bank several times; cache by mtime so edits still show up
    # without a restart. The doc is treated as read-only everywhere.
    mtime = path.stat().st_mtime
    held = _bank_cache.get(name)
    if held and held[0] == mtime:
        return held[1]

    # A version already refused is refused again without re-reading it. The
    # mtime has moved away from the good document by definition, so without
    # this the whole file would be re-parsed and re-checked on every render
    # for as long as the edit stood — which is exactly while the user is
    # working on it.
    refused = _bank_refused.get(name)
    if refused and refused["mtime"] == mtime \
            and refused["path"] == str(path):
        if held:
            return held[1]
        raise ValueError(refused["message"])

    try:
        doc = load_yaml(path) or {}
    except Exception as e:                # noqa: BLE001 — a bad file reports
        mark = getattr(e, "problem_mark", None)
        where = (f"{path.name} line {mark.line + 1}"
                 if mark is not None and isinstance(getattr(mark, "line", None),
                                                    int) else path.name)
        problems = [f"{where}: this is not valid YAML — "
                    + " ".join(str(getattr(e, "problem", None) or e).split())]
        doc = None
    else:
        problems = _problems(doc, path)

    if problems:
        _bank_refused[name] = {"mtime": mtime, "problems": problems,
                               "message": _refusal_message(path, problems),
                               "path": str(path), "holding": held is not None}
        if held:
            return held[1]
        raise ValueError(_refusal_message(path, problems))

    _bank_refused.pop(name, None)
    _bank_cache[name] = (mtime, doc)
    return doc


def refusal(name: str = "metric-bank"):
    """What is wrong with the file on disk, or None when nothing is.

        {"problems": [str, ...], "holding": bool, "path": str}

    `holding` is whether the program is still answering from an earlier
    version. It is the difference between "your edit has not taken effect" and
    "there is nothing to read", and a screen that could not tell them apart
    would be telling somebody their figures are current when they are not.

    Called for its side effect as much as its answer: it loads, so asking
    picks up a file that has since been fixed.
    """
    try:
        load_bank(name)
    except Exception:                     # noqa: BLE001 — reporting, not doing
        pass
    held = _bank_refused.get(name)
    if not held:
        return None
    return {"problems": list(held["problems"]), "holding": held["holding"],
            "path": held["path"]}


def bank_index(doc) -> dict:
    return {str(e.get("id")): e for e in (doc.get("entries") or [])}


# ---------------------------------------------------------------------------
# The definitions a journal stamps, and compares against on every read.
#
# One table, because the split it draws is the whole of what the record can
# honestly say and it must not be stated in one file and applied in another.
# Each entry's definition comes back as two maps and the shape is the rule:
#
#   states     value → recorded as a before and after. The value means
#              something on its own, so a reader can act on the move.
#   restates   digest → recorded as changed, contents not stated. The host can
#              see the arithmetic move and has no way to know what the move
#              meant, the same way it cannot say what a strategy's edited logic
#              now demands.
#
# There is deliberately no third map for the prose that explains a measure to a
# reader. It changes nothing a verdict consumes, and a wording pass over
# seventy-four entries would put seventy-four rows on every journal's record —
# burying the one retuning the record exists to surface.
# config/metric-bank.yaml says so in its own header, where somebody editing
# it will be looking.
#
# The keys are the words a screen prints. A second copy of them in the view is
# a copy that drifts, and a view holding a table of field names is a view that
# has to be edited when a field is added — which is the wrong turn principle 9
# names. So the record reads "observations read: 5 → 3" with nothing in the
# interface knowing what an observation is.
# ---------------------------------------------------------------------------

# Every key an entry can carry, and where a change to it lands. All of them,
# including the ones that land nowhere — the set of things NOT on the record is
# a decision and has to be written down as one, because the alternative is the
# complement of a list, which is not a decision but whatever nobody got round
# to. tests/test_bank.py pins this against the keys the shipped entries
# actually carry, so a key added to this file later cannot reach a journal
# without somebody choosing a side for it, and one deleted cannot leave a
# sentence here about a field that no longer exists.
ACCOUNTED_FOR = {
    "id": "not recorded: the entry's own name, which is what the record is "
          "keyed ON. It cannot move without one entry reading as removed and "
          "another as added — which is exactly what that is.",
    "label": "recorded as `name`.",
    "kind": "recorded as `answered by` — whether this is worked out from the "
            "filings or is a question the reader answers.",
    "unit": "recorded as `unit`.",
    "format": "recorded as `format`.",
    "polarity": "recorded as `favourable direction`.",
    "estimator": "recorded field by field: `how it is read`, `observations "
                 "read`, and the window it is `judged against`.",
    "inputs": "`entries` is recorded as `built on`, because it decides which "
              "measures a refusal propagates to. `filings` and `prices` are "
              "the human-readable gloss on a formula that is itself recorded.",
    "derivation": "recorded as the digest `how it is worked out`. The host "
                  "can see arithmetic move and cannot say what it now means.",
    "not_meaningful_when": "the industry classes are recorded as `does not "
                           "describe`; the data and undetected conditions as "
                           "digests. `because` is prose and is not recorded.",
    "question": "recorded as the digest `the question you answer`.",
    "response": "recorded field by field: `marks it accepts`, `prose`, and "
                "`unmarked reads as`.",
    "explanation": "not recorded: the plain-language account of the measure, "
                   "its misfires, and whose thinking it comes from. A reader "
                   "reads it; no verdict consumes a word of it.",
    "polarity_note": "not recorded: why a measure has no favourable "
                     "direction. The direction itself is recorded.",
    "parameters": "recorded as `parameters` — a number the formula needs and "
                  "this file does not fix, which a strategy then supplies.",
}


def _digest(*parts) -> str:
    """A short fingerprint of prose or arithmetic — enough to see that it
    moved, never enough to say what it now demands.

    Whitespace-normalised, so re-wrapping a formula to fit the column is not
    reported to four journals as a change to what they demand. Anything that
    survives that normalisation is a change to the characters of the
    arithmetic, and the host reports it without pretending to read it.
    """
    text = "\x1f".join(" ".join(str(p or "").split()) for p in parts)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _conditions(entry, form: str) -> list:
    """Every `not_meaningful_when` condition of one form, as declared."""
    return [item for item in (entry.get("not_meaningful_when") or [])
            if isinstance(item, dict) and item.get(form) is not None]


def _estimator(e) -> dict:
    return e.get("estimator") or {}


def _window(e) -> dict:
    w = _estimator(e).get("window")
    return w if isinstance(w, dict) else {}


def _response(e) -> dict:
    return e.get("response") or {}


def _marks(e):
    r = _response(e)
    return list(r.get("marks") or []) if r else None


# ---------------------------------------------------------------------------
# One row per field a definition carries, and everything about that field in
# one place: where it is read from, how a change to it is RECORDED, and
# whether a change to it leaves two readings COMPARABLE.
#
# Three lists keyed by the same names would be three lists that come apart,
# and the second and third columns answer questions that look alike and are
# not. Recording asks *can the host state what moved* — a number can, a
# formula cannot. Comparability asks *would two readings taken either side of
# this be readings of the same thing* — and the two cut the fields in
# genuinely different places:
#
#   `observations read` is STATED and INCOMPARABLE. A five-year median and a
#   three-year one are both perfectly sayable and are not the same measure.
#   This is the case that put the gate here at all.
#
#   `what the formula refuses on` is RESTATED and COMPARABLE. A condition
#   moving changes WHEN a value is absent, never what it is when present — so
#   either one side is absent already, or both were worked out by the same
#   arithmetic.
#
# So reusing the recording split for comparability would have missed the
# motivating case and gated four that never needed it.
#
# COMPARABLE is the narrow list on purpose. A field this build does not know
# is treated as breaking comparability, which is the safe direction: the cost
# is a drift row that says why it cannot be worked out, and the cost of the
# other default is a five-year median subtracted from a three-year one and
# reported as drift.
# ---------------------------------------------------------------------------

STATED, RESTATED = "states", "restates"
COMPARABLE, INCOMPARABLE = "comparable", "incomparable"

_FIELDS = (
    # field, read from, recorded as, and whether readings stay comparable
    ("name", lambda e: e.get("label"), STATED, COMPARABLE),
    ("answered by", lambda e: e.get("kind"), STATED, INCOMPARABLE),
    ("unit", lambda e: e.get("unit"), STATED, INCOMPARABLE),
    ("format", lambda e: e.get("format"), STATED, COMPARABLE),
    ("favourable direction", lambda e: e.get("polarity"), STATED, COMPARABLE),
    ("how it is read",
     lambda e: _estimator(e).get("kind"), STATED, INCOMPARABLE),
    ("observations read",
     lambda e: _estimator(e).get("observations"), STATED, INCOMPARABLE),
    # What a reading is JUDGED AGAINST, which robustness is derived from. It
    # decides what a leave-one-out re-read means and not what the reading is,
    # and a leave-one-out is computed live from today's filings either way.
    ("judged against",
     lambda e: _window(e).get("statistic"), STATED, COMPARABLE),
    ("observations judged against",
     lambda e: _window(e).get("observations"), STATED, COMPARABLE),
    ("built on",
     lambda e: list((e.get("inputs") or {}).get("entries") or []),
     STATED, INCOMPARABLE),
    # A number the formula needs and this file does not fix — the strategy
    # supplies it. No shipped entry declares one today; it is recorded anyway,
    # because the first one that does would otherwise arrive with nobody
    # watching, and an entry silently gaining a knob a strategy turns is
    # precisely what this record is for.
    ("parameters",
     lambda e: [str((p or {}).get("id")) for p in (e.get("parameters") or [])
                if isinstance(p, dict)], STATED, INCOMPARABLE),
    # The union across every industry condition, not one row per condition:
    # what the host acts on is the SET of classes this measure refuses for,
    # and "no longer declines insurance" is the statement a reader needs.
    # Which sentence went with which class is prose, and prose is not on this
    # record. Comparable for the reason the data conditions are: a class
    # arriving makes today inapplicable and a class leaving means there was no
    # reading to freeze, so the two sides are never both present and
    # differently worked out.
    ("does not describe",
     lambda e: sorted(_classes_named(e)), STATED, COMPARABLE),
    ("marks it accepts", _marks, STATED, INCOMPARABLE),
    ("prose", lambda e: _response(e).get("prose"), STATED, COMPARABLE),
    ("unmarked reads as",
     lambda e: _response(e).get("unmarked"), STATED, COMPARABLE),
    ("how it is worked out",
     lambda e: _digest((e.get("derivation") or {}).get("formula"),
                       (e.get("derivation") or {}).get("window")),
     RESTATED, INCOMPARABLE),
    ("what the formula refuses on",
     lambda e: _digest(*[c["data"] for c in _conditions(e, "data")]),
     RESTATED, COMPARABLE),
    ("what nothing here can settle",
     lambda e: _digest(*[p for c in _conditions(e, "undetected")
                         for p in (c["undetected"], c.get("needs"))]),
     RESTATED, COMPARABLE),
    ("the question you answer",
     lambda e: _digest(e.get("question")), RESTATED, INCOMPARABLE),
)

# The fields whose movement leaves a frozen reading and a live one comparable.
# Anything else — including a field added to the table above and any field
# this build has never heard of — makes them incomparable. See
# journals.measures_incomparable and context._baseline_of.
COMPARABLE_FIELDS = frozenset(
    field for field, _, _, compares in _FIELDS if compares == COMPARABLE)


def _definition(entry) -> dict:
    """One entry's rule-bearing state: what it computes, what it refuses on,
    how it is read, and what it does not describe."""
    e = to_plain(entry)
    states, restates = {}, {}
    for field, reads, record, _ in _FIELDS:
        (states if record == STATED else restates)[field] = reads(e)
    # A field the entry does not declare is left out rather than written down
    # as nothing. Absence is absence — and every journal on the machine keeps
    # a copy of this, so two hundred nulls is two hundred nulls per journal
    # and in every export. Safe in both directions because a comparison reads
    # `.get`, so a field that is missing and one that is null are the same
    # answer, and a field gaining a value moves from nothing either way.
    return {"states": {k: v for k, v in states.items() if v is not None},
            "restates": restates}


_definitions_cache: dict = {}


def definitions(name: str = "metric-bank") -> dict:
    """What this file demands, in the form a journal can stamp and compare.

        {"version": int, "entries": {id: {"states": {...},
                                          "restates": {...}}}}

    Plain data, so the record that holds it never carries a framework type and
    never has to be rebuilt to be read back. Cached against the loaded
    document's identity rather than recomputed per render, for the reason
    `load_bank` caches at all — this is asked for on every read of every
    journal, and an edit still lands because the document itself is rebuilt
    when its mtime moves.
    """
    doc = load_bank(name)
    held = _definitions_cache.get(name)
    if held and held[0] is doc:
        return held[1]
    out = {"version": doc.get("version"),
           "entries": {str(e.get("id")): _definition(e)
                       for e in (doc.get("entries") or [])}}
    _definitions_cache[name] = (doc, out)
    return out


def changelog(name: str = "metric-bank") -> dict:
    """{version: sentence} — the author's own account of each release, quoted
    by a journal that records the definitions moving under it. The host cannot
    say what a changed formula meant, so it quotes the person who can."""
    doc = load_bank(name)
    return {int(k): " ".join(str(v).split())
            for k, v in (doc.get("changelog") or {}).items()
            if isinstance(k, int) and not isinstance(k, bool)}


def bank_view(name: str = "metric-bank") -> dict:
    """The full bank for the Metrics page. No thresholds exist here.

    An applicability condition names its classes by id, and the screen renders
    what a class is *called*. The resolution happens here rather than in the
    view, because those words are the host's and a second copy of them in the
    interface is a copy that drifts — and because a view holding a table of
    class names is a view that has to be edited when a class is added, which
    is the wrong turn principle 9 names.

    Which FORM a condition is resolves here for exactly the same reason, and
    it is the same argument one step up. The view held its own table of forms,
    it knew about two of the three, and the third — the one where nothing
    refuses and nothing can — rendered as "refused by the calculation itself".
    A reader was told the program had checked. So each condition leaves here
    already carrying `form: {id, means}` and its own text under `states`, and
    the view renders what it is given rather than deciding what a form is.
    """
    from .contract import ESTIMATORS, CLOCKS      # local: bank loads first
    from .contract import INDUSTRY_CLASSES
    doc = load_bank(name)
    out = []
    for e in (doc.get("entries") or []):
        plain = to_plain(e)
        # The estimator's words resolve here, for the reason the class names
        # below already do: those words are the host's, and a second copy in
        # the interface is a copy that drifts. It had. ui/app.js carried a
        # hand-typed twin of these labels, it was missing `cumulative`, and
        # the one measure declaring that kind rendered the bare word on the
        # Metrics page — a reader shown a key instead of a sentence. A kind
        # added to engine/contract.py now arrives with its own words.
        est = plain.get("estimator")
        if isinstance(est, dict) and est.get("kind") in ESTIMATORS:
            spec = ESTIMATORS[est["kind"]]
            est["label"] = spec["label"]
            est["means"] = spec["means"]
            est["explain"] = spec["explain"]
            est["counts"] = CLOCKS[spec["clock"]]["noun"]
            est["confirmations"] = spec["confirmations"]
        for item in (plain.get("not_meaningful_when") or []):
            form = next((k for k in _NMW_FORMS if k in item), None)
            if form is None:
                continue                  # unreachable: load_bank refuses it
            item["form"] = {"id": form, "means": _NMW_FORMS[form]}
            if form == "industry":
                item["industry"] = [
                    {"id": c, "label": INDUSTRY_CLASSES[c]["label"],
                     "means": INDUSTRY_CLASSES[c]["means"]}
                    for c in item["industry"] if c in INDUSTRY_CLASSES]
            else:
                item["states"] = " ".join(str(item[form]).split())
        out.append(plain)
    return {"name": name, "schema": to_plain(doc.get("schema")),
            "entries": out}


def applicability(name: str = "metric-bank") -> dict:
    """{entry id: [(frozenset of class ids, because), ...]} — the conditions
    the HOST evaluates, and nothing else from the file.

    Only the `industry` form is here. A `data` condition belongs to the
    formula and is not something a caller can act on: handing it over would
    invite a second, weaker enforcement of a test the arithmetic already
    makes, and two enforcements of one rule is how they come to disagree.
    """
    doc = load_bank(name)
    out = {}
    for e in (doc.get("entries") or []):
        rules = [(frozenset(str(c) for c in item["industry"]),
                  str(item.get("because") or "").strip())
                 for item in (e.get("not_meaningful_when") or [])
                 if isinstance(item, dict)
                 and isinstance(item.get("industry"), list)]
        if rules:
            out[str(e.get("id"))] = rules
    return out


def data_conditions(name: str = "metric-bank") -> dict:
    """{entry id: [condition, ...]} — the conditions the FORMULA refuses on.

    The mirror of `applicability` above, and handed over for the opposite
    reason. Those are the host's to evaluate and are exported so it can. These
    are not — a reading of the figures can only be refused where the
    arithmetic is — and they are exported so the formula performing one can
    say the sentence in the bank's words rather than a copy of them, and so
    that naming a condition this file does not state can be refused. See
    compute.not_meaningful.
    """
    doc = load_bank(name)
    out = {}
    for e in (doc.get("entries") or []):
        stated = [" ".join(str(item["data"]).split())
                  for item in (e.get("not_meaningful_when") or [])
                  if isinstance(item, dict) and item.get("data")]
        if stated:
            out[str(e.get("id"))] = stated
    return out


def meta(name: str = "metric-bank") -> dict:
    """Per measure, what a screen needs to render it: label, unit, format,
    kind, favourable direction, and the plain-language explanation. The
    explanation travels because a number without one is incomplete."""
    doc = load_bank(name)
    out = {}
    for e in (doc.get("entries") or []):
        expl = e.get("explanation") or {}
        out[str(e.get("id"))] = {
            "label": to_plain(e.get("label")),
            "unit": to_plain(e.get("unit")),
            "format": to_plain(e.get("format")),
            "kind": to_plain(e.get("kind")),
            "polarity": to_plain(e.get("polarity")),
            "plain": to_plain(expl.get("plain")),
        }
    return out
