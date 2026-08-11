"""The metric bank — what every value *is*.

The bank (config/metric-bank.yaml) defines each measure: its label, unit,
format, how it is derived, and the plain-language explanation that must
accompany it. It holds no thresholds and no decision power, because deciding
is a strategy's job and the same host has to serve strategies that contradict
each other.

This module is the only reader of that file. It ships with the program rather
than living in the user's data directory: the bank is part of what the
program *is*, and a measure's definition is not a user setting.
"""

from __future__ import annotations

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

# Kinds whose estimator reads a fixed-length window of annual observations, so
# `observations` says something and its absence is a hole. A streak has no
# fixed window and may leave it out; a reading at one date or over a trailing
# window has no annual observations to count, and stating one would be noise.
_WINDOWED = ("averaged", "median", "range", "cumulative")
_UNWINDOWED = ("instant", "trailing", "assessed")


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
    unknown = set(node) - {"kind", "observations"}
    if unknown:
        return [f"{eid}: an estimator carries `kind` and `observations` and "
                "nothing else; found " + ", ".join(sorted(unknown)) + "."]
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

_NMW_FORMS = ("industry", "data", "undetected")

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
            if form == "data" and "needs" in item:
                problems.append(
                    f"{where}: `needs` belongs to an undetected condition. "
                    "This one is enforced, so nothing is owed.")
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


def load_bank(name: str = "metric-bank"):
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
    doc = load_yaml(path) or {}
    schema = str(doc.get("schema") or "")
    if not schema.startswith("ledger.metric-bank/"):
        raise ValueError(
            f'{path.name} does not declare a metric-bank schema '
            f'(found "{schema or "nothing"}").')
    entries = list(doc.get("entries") or [])
    problems = [p for e in entries
                for p in _check_estimator(e) + _check_applicability(e)]
    problems += _check_propagation(entries)
    if problems:
        raise ValueError(f"{path.name} cannot be loaded:\n  "
                         + "\n  ".join(problems))
    _bank_cache[name] = (mtime, doc)
    return doc


def bank_index(doc) -> dict:
    return {str(e.get("id")): e for e in (doc.get("entries") or [])}


def bank_view(name: str = "metric-bank") -> dict:
    """The full bank for the Metrics page. No thresholds exist here.

    An applicability condition names its classes by id, and the screen renders
    what a class is *called*. The resolution happens here rather than in the
    view, because those words are the host's and a second copy of them in the
    interface is a copy that drifts — and because a view holding a table of
    class names is a view that has to be edited when a class is added, which
    is the wrong turn principle 9 names.
    """
    from .contract import INDUSTRY_CLASSES         # local: bank loads first
    doc = load_bank(name)
    out = []
    for e in (doc.get("entries") or []):
        plain = to_plain(e)
        for item in (plain.get("not_meaningful_when") or []):
            named = item.get("industry")
            if isinstance(named, list):
                item["industry"] = [
                    {"id": c, "label": INDUSTRY_CLASSES[c]["label"],
                     "means": INDUSTRY_CLASSES[c]["means"]}
                    for c in named if c in INDUSTRY_CLASSES]
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
