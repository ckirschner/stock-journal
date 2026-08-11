"""Building what a strategy receives: one plain dict per security.

The context is the host's entire offer. A strategy consumes it and produces
a decision; it never fetches, never reaches the stores, never sees a
framework type. Everything in here is plain data, deep-copied on the way
out, so a strategy can neither corrupt the host's caches nor reach a live
reference into the journal.

The shape, in full::

    {
      "contract": <contract.CONTRACT_VERSION>,
      "today": "YYYY-MM-DD",        # the clock; everything below obeys it
      "security": {"ticker", "name", "cik",
                   "sic":      {"status": "known", "value": "6021", ...}
                             | {"status": "absent", "reason"},
                   "industry": {"status": "known", "value", "class", "sic",
                                "title", "source", "cautions", "provenance"}
                             | {"status": "absent", "reason"}},
      "measures": {bank id: {
          "current": {"status": "known", "value", "source", "cautions",
                      "provenance"}
                   | {"status": "absent", "reason"}
                   | {"status": "inapplicable", "reason", "industry"},
          "series": {"cadence", "points": [{"period_end", "filed", "form",
                                            "accession", "value", "reason",
                                            "cautions", "provenance"}],
                     "note", "truncated"}}},
      "price":    {"latest": {"status": "known", "value", "source",
                              "cautions", "provenance", "date", "ticker"}
                            | {"status": "absent", "reason"},
                   "closes": [[date, close], ...],   # as traded, ascending
                   "events": [[date, "split"|"dividend", amount], ...]},
                  # All three describe the security this journal holds, and
                  # only it. See the reading rule on share classes below.
      "position": {"held", "shares", "opened", "months_held",
                   "last_purchase", "purchases",
                   "baselines": {anchor: {"status": "known", "date", "lot",
                                          "measures": {bank id: known}}
                                       | {"status": "absent", "reason"}},
                   "lots":      [{"date", "shares", "remaining", "open"}],
                   "disposals": [{"date", "shares"}],
                   "market_value": known-or-absent,
                   "weight": known-or-absent},       # percent of the account
      "portfolio": {"cash", "account_value",         # known-or-absent
                    "slots": {"occupied"},
                    "holdings": [{"ticker", "name", "shares", "opened",
                                  "market_value", "weight"}]},
      "values": {id: value},        # the resolved declaration chain
      "inputs": {id: value},        # the answers that apply, with answers
      "reference": {file name: parsed},   # what the bundle ships, frozen
    }

`reference` is attached by engine/contract.evaluate rather than built here:
it belongs to the strategy, not the security, and it is shared read-only
across every evaluation instead of being copied for each one.

Reading rules a strategy can rely on:

- **The clock governs everything.** Series points come only from filings
  filed by `today`; each point is computed from the filings on record at its
  own boundary, priced at the close on or before that boundary's filed date.
  Prices stop at `today`. A reconstructed evaluation therefore sees the
  world of its day, never this one.
- **Absence is a value.** Every bank measure is present in `measures`; where
  the host cannot honestly serve a number, status is "absent" with a reason,
  and a series point that could not be read carries value None with its
  reason. Nothing is zero-filled, carried forward, or interpolated.
- **A measure that cannot describe this filer says so, and says it
  differently.** The bank declares, per measure, the kinds of company it was
  never built for — a lender's accounts have no invested capital in the sense
  return on it means, and no amount of data changes that. Such a measure is
  `inapplicable`, settled from the industry code the SEC publishes before any
  arithmetic runs, and it is a different fact from `absent`: absent is a gap
  that a fetch or a filing may close, this is a boundary that will not move
  while the company is what it is. A strategy need not know the word — every
  reader asks whether the status is "known", so an inapplicable measure can
  never be tested as a pass, exactly as an absent one cannot. What the word
  buys is that a reader is told which of the two they are looking at, and
  that a screen listing what to go and fetch does not list it forever.

  A hand-entered figure does not override it. Whatever was typed is a
  different quantity wearing this measure's name and unit, and it would feed
  a verdict — so the entry stays on the dated record and is not served while
  the classification holds.
- **A qualified number says so wherever it appears.** Where a figure rests on
  an approximation, a borrowed price or a line the concept map matched
  loosely, its `cautions` say so — on `current` and on every `series` point
  alike, because the qualification belongs to the reading and not to the
  moment it was read. A strategy never restates a caution (it cites; the
  host answers), but nothing it is handed is a bare number pretending to be
  more certain than it is.
- **A share class is a security; the company is not.** Two classes of one
  company are two instruments at two prices, and the two scopes are served
  differently. `price`, `position.market_value`, `position.weight` and every
  holding in `portfolio` are about the *instrument this journal holds*, priced
  from its own symbol alone — where that symbol has no close the value is
  absent with a reason, never a sibling's price. `measures` are about the
  *company*, so a whole-enterprise figure such as market capitalization reads
  every class; where one of them has no price of its own the measure says so
  in its cautions, which is the only place in this context an approximation
  is permitted to appear.

  This is not a convention to be remembered. The reader that serves a price
  takes one symbol and refuses a list, because taking the newest close across
  every mapped class is what priced twenty shares of a Class B security at
  $14,100,000 instead of $9,400 — silently, in a figure sizing rules bind on.
- **Percent units are percent numbers** (18.9 means 18.9%), including
  position weight, matching the metric bank's convention.
- **A hand-entered value is dated, like everything else the user supplies.**
  It wins over a computed one for its own day, says so in `source`, and
  names the day it was entered in `provenance`. A reconstruction sees the
  figure that was on record *then* — the value you typed last week is not
  served to a purchase backdated to 2024, which is absent with the reason
  instead. Clearing a value is an entry too, not a deletion: the computed
  figure underneath becomes visible again and the withdrawal stays legible.
  A hand-entered *price* is the one exception left — it carries no date and
  never reaches into the past at all.
- **A qualitative measure is a judgement the user made, and it is dated.**
  The bank's qualitative entries — a moat read, a management read — are
  answered per security in prose plus a pass or a fail, and arrive here as
  an ordinary measure with `source: "judgement"`, a yes/no value and the
  reasoning in `provenance`. Nothing else about citing one differs: a
  strategy names it as `{"measure": "<id>"}` and the host answers.

  Two things follow from the record being append-only and dated. A
  reconstruction sees the assessment that stood on its own day and nothing
  written later, so a backdated purchase never inherits an opinion formed
  afterwards; and an assessment older than the holding you have now carries
  a caution saying so, because buying a name back does not renew a judgement
  made about a different decision. The first of those is now true of every
  value the user supplies; the second is true only of the ones that are
  about a *holding*, which a number read off a balance sheet is not.

  An unanswered question is absent with its reason. What to do about that is
  the strategy's business — the host holds no view on whether a missing moat
  read should stop a verdict — but absence resolves to `unknown` and can
  never come out as a pass. A judgement is never served from a hand-entered
  number: one laid over a question about a moat would be an assessment
  wearing a measurement's clothes.
- **What kind of company this is, is a fact and not a judgement.**
  `security.industry` carries the class the host derives from the industry
  code the SEC publishes for the filer — a lender, an insurer, a property
  company, or no class at all, which is the ordinary answer and covers almost
  everything. A strategy that routes on it reads `["class"]`, which is a host
  id; the `value` beside it is the sentence a reader sees and must never be
  compared against, because a strategy comparing against a label is a
  strategy quoting the host.

  Absent means the code does not settle it, and there is no third answer:
  several codes the SEC publishes cover businesses whose accounts have
  nothing in common — American Express and a payment processor file under the
  same one — so "ordinary" would be an invention there rather than a reading.
  A strategy that declares `declines` never sees such a company at all: the
  host refuses it before `decide` runs. See engine/industry.py for why the
  clock does not govern this one figure.
- **Unknown keys may appear** in future contract versions; a strategy reads
  what it declares an interest in and ignores the rest.
- **`position` is the holding you have now, except where it says otherwise.**
  `held`, `shares`, `opened`, `months_held`, `market_value` and `weight` are
  all about the current holding period — the run from the purchase that took
  the position up from nothing to now. `opened` is that period's first
  purchase and does not move when a lot is trimmed away: it answers when this
  holding began, not how old the oldest surviving share is. A rule that wants
  lot ages reads `lots`, where every entry carries its own date, `remaining`
  and `open`. A re-entry after a full exit opens a new period, so `opened`
  counts from the re-entry, and `months_held` with it.

  `months_held` is whole months from `opened` to `today`, clamped the way
  `contract.months_after` adds them, so a rule can compare it against a
  holding period without writing month arithmetic of its own. Absent — None
  — where nothing is held.
- **`lots` and `disposals` are the security's whole record, not the current
  holding's.** Every purchase this journal ever made in the name is in
  `lots`, and every sale in `disposals`, including those belonging to a
  holding that closed before the current one opened. That is deliberate: a
  strategy asking "have I owned this before" has nowhere else to look. But it
  means these two are scoped differently from everything beside them, so a
  rule counting entries wants `[l for l in lots if l["open"]]` rather than
  the length.

  `disposals` cannot be narrowed that way, and that is a known gap rather
  than a design: each entry carries only `date` and `shares`, so nothing on
  it says which holding it ended. Two securities can arrive with identical
  `lots`, `disposals` and `shares` and different `opened` — one closed out
  and bought back the same day, one added and trimmed the same day — and no
  rule reading `disposals` can tell them apart. Until an entry can say which
  holding it belongs to, treat `disposals` as a fact about the security and
  not about the position, and do not derive "what this holding has sold" from
  it.
- **`baselines` are what you were shown, not what today's filings say about
  that day.** Each anchor carries the figures frozen onto that purchase's
  own snapshot, copied and never recomputed. A company restating two years
  of accounts cannot move them, which is the whole point: a rule asking
  whether something has worsened since you last said yes is asking about
  what you saw when you said it. A purchase with no frozen record is absent
  with a reason, and a measure the record never held is absent too — neither
  is ever a zero and neither can come out as a pass. `first-purchase` and
  `last-purchase` are the same purchase until you buy a second time; see
  contract.BASELINE_ANCHORS for why both exist and why averaging them is
  wrong for both questions they answer.
- **Nothing here says what a position cost.** Cost basis is reporting and is
  kept out of the context entirely, so a rule that fires on the distance
  from your own purchase price cannot be written. See contract.HOST_FACTS.
  This is what makes "a third now, a third 25% below what I paid" not merely
  unsupported but unwritable — a staged plan has to hang off what the
  business is worth, not off what you paid for it.
- **The account is derived, never declared.** `portfolio.account_value` is
  free cash plus the market value of every holding the journal knows about,
  which is why free cash is the one thing a strategy has to ask for. An
  account value the user typed would be a conclusion the tool could reach
  itself, and when a weight came out wrong there would be no way to see
  which input was wrong.
- **Free cash is only served where a strategy asked for it.** An input
  carrying the `cash` role is what unlocks cash, the account value and every
  weight; a strategy that declares no such input gets all of them absent
  with a reason saying the question was never asked. The host holds no view
  about whether a journal ought to record cash.
"""

from __future__ import annotations

import copy
from datetime import date

from . import bank as bank_mod
from . import compute, contract, dataview, facts_store, hand_entered
from . import industry as industry_mod
from . import instruments, judgements, portfolio, price_store, tickermap

# Series stop at the same number of filing boundaries the sell-confirmation
# view uses; the truncated flag says when older boundaries exist.
SERIES_BOUNDARY_CAP = compute.CONFIRMATION_BOUNDARY_CAP


def _tickers_of(security: dict) -> list:
    """Every symbol the SEC maps to this security's company.

    Company-scoped, and only that. A whole-company measure — market cap over
    every class, the shares a per-share valuation divides by — genuinely needs
    all of them, because the company is the subject.

    Nothing about the *position* comes through here. Share classes are
    different instruments at different prices, so what a holding is worth, and
    every figure derived from it, reads the security's own symbol alone and
    goes nowhere near this list. See dataview.price_view.

    Cached snapshot only; building a context never touches the network."""
    ticker = str(security.get("ticker") or "").upper()
    cik = security.get("cik")
    if cik:
        try:
            mapped = tickermap.tickers_for(tickermap.load_cached(), cik)
        except Exception:  # noqa: BLE001 — a missing snapshot is not fatal
            mapped = []
        if mapped:
            if ticker and ticker not in mapped:
                mapped.append(ticker)
            return mapped
    return [ticker] if ticker else []


def _known(value, source, cautions=None, provenance=None,
           leave_one_out=None) -> dict:
    """One measure as a strategy reads it.

    `leave_one_out` travels beside the value because it is part of the same
    answer: for a measure read over a window of fiscal years, "and what does
    it say without its most flattering year?" is not a second measure, it is
    the only robustness test available — waiting for another filing re-reads
    the same years. Present only where the estimator reads a window; absent,
    never a copy of the value, so a check that cannot be made comes back
    unmade rather than passing itself.
    """
    out = {"status": "known", "value": value, "source": source,
           "cautions": list(cautions or []),
           "provenance": list(provenance or [])}
    if leave_one_out:
        out["leave_one_out"] = [dict(o) for o in leave_one_out]
    return out


def _absent(reason: str) -> dict:
    return {"status": "absent", "reason": reason}


def _inapplicable(reason: str, cls: str | None = None) -> dict:
    """A measure that will never describe this filer.

    The third status a measure can reach, and the one that must not read as
    the second. `absent` is a gap: something is missing and a fetch, a filing
    or an answer may close it, so it belongs among the things to go and do.
    This is a boundary: it was knowable before anything was computed, and it
    holds for as long as the company is the kind of company it is.

    Nothing that consumes a measure has to learn the word. Every reader asks
    whether the status is "known", so this can never be mistaken for a value
    and can never come out of a test as a pass. What the word buys is that a
    reader is told which of the two they are looking at.
    """
    node = {"status": "inapplicable", "reason": reason}
    if cls:
        node["industry"] = cls
    return node


# -- measures ----------------------------------------------------------------

def _current_values(security, cik, tickers, registry_ids, as_of):
    """{entry id: current dict} for every computable entry, hand-entered
    values winning over computed ones exactly as the journal shows them.

    A hand-entered value is dated, so a pinned reading serves the figure
    that was on record on its day and nothing entered afterwards. Where
    none was — the figure was typed later, or withdrawn — the measure is
    absent with the reason, and a strategy is never told a present-day
    number was known on a past day.

    The absence only shows through where the computed layer has nothing
    known to offer. A user who typed a figure today and then withdrew it has
    not made the filings unreadable, and "you cleared this" is a worse
    answer than the number that was there all along.

    A judgement is not among them. Hand-entered values are numbers, and a
    number laid over a question about a moat would be an assessment
    presented as a measurement — the one thing principle 5 says a captured
    judgement must never be. Judgements are served from their own dated
    record, in `_measures`; the hand-entered write refuses the id, and this
    read refuses it again.
    """
    out = {}
    if cik:
        if as_of:
            results = dataview.asof_results(cik, tickers, registry_ids, as_of)
        else:
            results = dataview.computed_results(cik, tickers, registry_ids)
        for eid, r in results.items():
            if r.get("status") == "computed":
                out[eid] = _known(r["value"], "computed",
                                  r.get("cautions"), r.get("provenance"),
                                  r.get("leave_one_out"))
            elif r.get("status") == "inapplicable":
                out[eid] = _inapplicable(r["reason"], r.get("industry"))
            else:
                out[eid] = _absent(r.get("reason")
                                   or "the value could not be computed")
    for eid in hand_entered.ids(security):
        # A measure that cannot describe this filer is not made applicable by
        # somebody typing a number into it. Whatever they typed is a different
        # quantity wearing this measure's name, unit and explanation, and it
        # would feed a verdict — which is the one place principle 4 says a
        # qualification is read by a person and ignored by the arithmetic. The
        # figure stays on the record, dated, and becomes readable again if the
        # SEC ever reclassifies the filer; it is the serving that is refused,
        # not the recording.
        if (out.get(eid) or {}).get("status") == "inapplicable":
            continue
        r = hand_entered.reading(security, eid, as_of)
        if r["status"] == "known":
            out[eid] = _known(r["value"], "manual", r["cautions"],
                              r["provenance"])
        elif (out.get(eid) or {}).get("status") != "known":
            out[eid] = _absent(r["reason"])
    return out


def _series_for(filings, prices, symbols, today, ind=None):
    """{entry id: series dict} for every entry with a filing cadence, all
    entries of a cadence sharing one pinned context per boundary so the
    series is cheap to assemble and every reading obeys the same clock.

    The identity history goes to every boundary context, so a point read at a
    2019 filing is judged against what the SEC called this filer then. A
    company that reclassified part way through a holding is the case this
    exists for: without it, one measure would read inapplicable across a
    history in which it meant something."""
    dated = [f for f in filings
             if str(f.get("filed") or "")[:10]
             and str(f.get("filed") or "")[:10] <= today]
    out = {}
    for cadence in ("annual", "quarterly"):
        eids = [e for e, c in compute.CADENCE.items()
                if c == cadence and e in compute.REGISTRY]
        bounds = compute.confirmation_boundaries(dated, cadence)
        take = bounds[-SERIES_BOUNDARY_CAP:]
        contexts = []
        for b in take:
            prefix = [f for f in dated
                      if str(f.get("filed") or "")[:10] <= b["filed"]]
            contexts.append((b, compute.Ctx(prefix, prices, symbols,
                                            today=b["filed"],
                                            price_cutoff=b["filed"],
                                            industry=ind)))
        for eid in eids:
            points = []
            for b, bctx in contexts:
                try:
                    r = bctx.entry(eid)
                except Exception as e:  # noqa: BLE001 — a point, not a crash
                    r = {"status": "absent",
                         "reason": f"computation failed: "
                                   f"{type(e).__name__}: {e}"}
                ok = r.get("status") == "computed"
                points.append({
                    "period_end": b["period_end"], "filed": b["filed"],
                    "form": b["form"], "accession": b["accession"],
                    "value": r.get("value") if ok else None,
                    "reason": None if ok else (r.get("reason")
                                               or "the reading could not "
                                                  "be computed"),
                    # A reading is qualified exactly as the current value
                    # is. A point computed from a debt line that folds in
                    # finance leases, or a market cap with a class valued
                    # at a sibling's close, is that kind of number whether
                    # it is read today or at a filing boundary two years
                    # back — and a strategy citing the point gets the
                    # qualification with it rather than a bare figure.
                    "cautions": list(r.get("cautions") or []) if ok else [],
                    "provenance": list(r.get("provenance") or []) if ok
                    else [],
                })
            if points:
                note = None
            elif not dated:
                note = ("no filing data is stored for this security on or "
                        f"before {today} — fetch data to build its history")
            else:
                note = ("none of the stored filings delivers a new "
                        + ("annual" if cadence == "annual"
                           else "quarterly or annual")
                        + " reporting period, so there is nothing to read")
            out[eid] = {"cadence": cadence, "points": points, "note": note,
                        "truncated": len(bounds) > len(take)}
    return out


def _no_series(note: str) -> dict:
    return {"cadence": None, "points": [], "note": note, "truncated": False}


def _measures(security, cik, tickers, as_of, today) -> dict:
    bank = bank_mod.load_bank()
    entries = [(str(e.get("id")), e) for e in (bank.get("entries") or [])]
    registry_ids = [eid for eid, _ in entries if eid in compute.REGISTRY]

    current = _current_values(security, cik, tickers, registry_ids, as_of)
    # Answered by the user, per security, from their own dated record. The
    # clock governs them as it governs everything else: a reconstruction
    # sees the assessment that stood on its day, and where none did the
    # measure is absent with the reason rather than inheriting an opinion
    # formed afterwards.
    assessed = judgements.observations(security, as_of=as_of, today=today)
    if cik:
        filings = facts_store.load_all_filings(cik)
        prices = price_store.load(cik)
        # Which symbol is the common stock, resolved off the whole filing set
        # rather than per boundary. A boundary in 2017 predates the cover-page
        # tagging that answers the question, and refusing a 2017 reading
        # because a preferred series first listed in 2024 shares the CIK would
        # be a sentence about the wrong year. See engine/instruments.py.
        series = _series_for(filings, prices,
                             instruments.company_symbols(filings, tickers),
                             today, industry_mod.history(security))
    else:
        series = {}

    out = {}
    for eid, entry in entries:
        kind = str(entry.get("kind") or "")
        if kind == "qualitative":
            cur = assessed.get(eid) or _absent(
                "assessed by you, not computed — nothing is recorded in this "
                "journal yet")
            ser = _no_series("assessed by you, not computed — no filing "
                            "series exists")
        elif eid not in compute.REGISTRY:
            cur = current.get(eid) or _absent(
                f"this host has no computation for {eid} — its data source "
                "is not ingested")
            ser = _no_series(f"this host has no computation for {eid}")
        else:
            cur = current.get(eid) or _absent(
                "no filing data is stored for this security — fetch data "
                "first")
            ser = series.get(eid) or _no_series(
                "no filing data is stored for this security — fetch data "
                "first" if not cik else
                f"{eid} has no filing cadence, so no per-filing series "
                "exists")
        out[eid] = {"current": cur, "series": ser}
    return out


# -- price -------------------------------------------------------------------

def _price_basis(view, ticker) -> str:
    """Where a price came from, in a sentence — the instrument and the day,
    or that it was typed in.

    One sentence, one home. Market value says "20 shares at the ACME close of
    2026-08-01" and the price itself says the same thing about the same
    figure; two versions of it drift, and the half that goes missing is
    always the half naming which share class was priced.
    """
    if view.get("source") == "manual":
        return "the price entered by hand, which carries no date"
    ended = view.get("terminal")
    where = (f'the {view.get("ticker") or ticker} close of {view["date"]}'
             if view.get("date") else "the recorded close")
    if ended:
        # A fact, and the one that has to be said loudest. Every other
        # qualifier here is about how old a price is; this one is about
        # whether it is still a price at all, and a novice reading a dead
        # series rendered as a live quote has no way to tell.
        return (f"{where} — the last this instrument ever traded at, because "
                f"its price series has ended "
                f"({ended.get('reason') or 'no reason recorded'})")
    return where


def _days_since(view, today):
    """Whole days from the close behind a price to the day being asked
    about, or None where the price carries no date at all.

    Arithmetic over two dates the host already owns, offered for exactly the
    reason `position.months_held` is: every strategy with a view about how
    old a price may be would otherwise write it again, and a strategy cannot
    write it at all — it has a date and no way to subtract one.

    None is the honest answer for a hand-entered price. It is not zero: zero
    would say the price is today's, and nothing here knows when it was typed.
    """
    when = view.get("date")
    if not when:
        return None
    try:
        return (date.fromisoformat(str(today)[:10])
                - date.fromisoformat(str(when)[:10])).days
    except ValueError:
        return None


def _price_age(view, today) -> list[str]:
    """How old the close behind a price-derived figure is, as a caution — or
    that it has no date at all.

    Always said, never judged. Whether four days is fine and eleven is not is
    a strategy's question, and until this the host answered it: a caution
    appeared past seven days and nothing appeared below it, so silence meant
    either "current" or "nobody asked" and the reader could not tell which.

    Counted against the clock the figure belongs to, so a reconstruction
    reports its age as of the day being rebuilt rather than as of today.
    """
    out = []
    ended = view.get("terminal")
    manual = view.get("source") == "manual"
    if ended and not manual:
        # A caution and not only a provenance clause. Provenance says where a
        # figure came from and stops at the figure it describes; a caution
        # travels up — market value into the account total, both into weight
        # — and weight is the number a sizing rule fires on. A dead series
        # reaching the price and not the weight is the fact arriving
        # everywhere except where it decides something.
        #
        # Not on a hand-entered price. The mark is about the stored series,
        # and a figure the user typed did not come from it — saying this
        # figure "rests on the last close the security ever had" would be
        # the host describing a number it did not produce, and describing it
        # wrongly. What the ended series means for a price the user supplied
        # is said on the price itself, where the reader can see both.
        out.append(
            "the price series behind this has ended "
            f"({ended.get('reason') or 'no reason recorded'}), so this rests "
            "on the last close the security ever had rather than on what it "
            "trades at")
    if manual:
        return out + ([view["undated"]] if view.get("undated") else [])
    when = view.get("date")
    if not when:
        return out
    try:
        days = (date.fromisoformat(str(today)[:10])
                - date.fromisoformat(str(when)[:10])).days
    except ValueError:
        return out
    if days <= 0:
        return out + [f"priced at the close of {when}, the latest held"]
    return out + [f"priced at the close of {when}, "
                  + ("a day" if days == 1 else f"{days} days") + " earlier"]


def _price(security, cik, ticker, as_of, today) -> dict:
    """This security's price and its own close history.

    One instrument throughout. The history has to belong to the same
    instrument as the close beside it or a strategy measures a move that never
    happened — and both have to belong to the security the journal holds, not
    to whichever class of the company happens to have traded most recently.
    Where this instrument has no rows the history is empty, because another
    class's history is not a fallback for it; it is a different price series
    for a different thing.

    `latest` is built like every other figure the host reports, through
    `_known`, so a strategy citing it gets the day and the symbol behind it
    rather than a bare number. It was the one node that was not: the value
    was right and its provenance was missing, which is cite-don't-quote
    failing at the node where the symbol had just become load-bearing. The
    same close reported through `position.market_value` named the instrument;
    reported as itself it did not.
    """
    if as_of:
        # A hand-entered price is a statement about now; it never reaches
        # into the past, even when no fetched history exists to answer.
        view = dataview.price_view_asof(cik, ticker, as_of) if cik else \
            {"value": None,
             "reason": "no fetched price history is stored for this "
                       f"security, so no close exists to reconstruct "
                       f"for {as_of}"}
    else:
        view = dataview.price_view(security, cik, ticker)
    if view.get("value") is None:
        latest = _absent(view.get("reason")
                         or "no price is stored for this security — fetch "
                            "prices, or enter one by hand")
    else:
        # `source` means here exactly what it means on every other figure:
        # which side the value came from. Fetched or hand-entered, never a
        # word invented for this node.
        latest = _known(float(view["value"]), view.get("source") or "price",
                        cautions=_price_age(view, as_of or today),
                        provenance=[_price_basis(view, ticker)])
        # Kept beside the provenance sentence rather than only inside it: a
        # rule that wants the close's own date wants a date, not prose. The
        # same goes for a series that has ended and for how old the close is
        # — a strategy deciding what is too old needs a number to compare,
        # and a sentence is something it would have to parse.
        latest["date"] = view.get("date")
        latest["ticker"] = view.get("ticker")
        latest["terminal"] = view.get("terminal")
        latest["days_since_close"] = _days_since(view, as_of or today)
    closes, events = dataview.price_series(cik, ticker, until=today)
    return {"latest": latest, "age": _price_age_fact(view, latest, as_of
                                                     or today),
            "closes": closes, "events": events}


def _price_age_fact(view, latest, today) -> dict:
    """How many days ago the market last set this price, as a figure a rule
    can compare — or an absence saying which of the two reasons it is.

    Two, and they are not the same answer. There may be no price at all, in
    which case the price's own reason is the reason; or there may be a price
    the user typed, which has no date because nothing here knows when it was
    typed. A single sentence covering both would tell someone with no price
    stored that they entered one by hand, and send them looking for a figure
    they never wrote.
    """
    if latest["status"] != "known":
        return _absent("there is no price on record to date — "
                       + latest["reason"])
    days = _days_since(view, today)
    if days is None:
        return _absent(view.get("undated")
                       or "the price on record carries no date")
    return _known(days, "computed",
                  provenance=[f'the close of {view["date"]}, against '
                              f"{today}"])


# -- position and portfolio --------------------------------------------------

def _market_value(sec, shares, today, as_of=None):
    """Shares times the price of the security actually held.

    The price belongs to the clock — the journal's effective price live, the
    reconstructed close under a pin — and to the instrument. A holding is
    priced from its own symbol and from nothing else: a company's other share
    classes trade at their own prices, and borrowing one would put a plausible
    dollar figure into market value, the account total and every weight
    measured against it, with nothing on the screen to say it was the wrong
    thing. Where this security has no close, the value is absent with the
    reason, per principle 4.

    The provenance names the instrument as well as the day, so the figure can
    be checked without leaving the screen.
    """
    cik = sec.get("cik")
    ticker = str(sec.get("ticker") or "")
    if as_of:
        view = dataview.price_view_asof(cik, ticker, as_of) if cik else \
            {"value": None,
             "reason": "no fetched price history is stored for this "
                       f"security, so no close exists to reconstruct "
                       f"for {as_of}"}
    else:
        view = dataview.price_view(sec, cik, ticker)
    if view.get("value") is None:
        return _absent(view.get("reason")
                       or "no price is stored for this security, so its "
                          "market value cannot be computed")
    # The price's age and whether its series has ended travel with the
    # figure rather than staying in `price_view`. Market value and the weight
    # built on it are what a sizing rule fires on, and they were the two
    # numbers with the least said about the price underneath them: a weight
    # from a two-month-old close and one from this morning's read identically
    # to a strategy and to the reader.
    return _known(float(view["value"]) * shares, "computed",
                  cautions=_price_age(view, as_of or today),
                  provenance=[f"{shares:g} shares at "
                              f"{_price_basis(view, ticker)}"])


_NO_CASH_ROLE = ("no strategy in this journal asks for your free cash, so "
                 "the journal does not record it and the account it would "
                 "be measured against cannot be reached")


def _usd(n) -> str:
    return f"${n:,.0f}"


def _cash(roles, as_of) -> dict:
    """Free cash, from whichever declared input claims the `cash` role.

    The answers reaching here are already the ones that were on record on
    the day being evaluated — they are resolved against the journal's dated
    change record before the context is built, in journals.answers_on. So
    there is no caution to attach and no carrying-forward to admit to: the
    figure either was the answer on that day or there is no answer, and the
    second case arrives here as an absence like any other.

    That is a change from serving today's balance with a warning beside it.
    A qualified wrong number still decides — the account total is built from
    this, every weight is measured against the account, and strategies bind
    on weight — so the number is the thing that had to move, not the
    sentence.
    """
    entry = (roles or {}).get("cash")
    if entry is None:
        return _absent(_NO_CASH_ROLE)
    if "value" not in entry:
        if as_of:
            # A different absence from "answer it in settings". Two ways to
            # get here — the journal had not been told yet, or it did not
            # exist on that day — and this node cannot tell them apart, so it
            # says both rather than guessing. Which it was is on the record:
            # the reconstruction's own note names the day the journal was
            # created when that is the reason.
            return _absent(
                f'this journal holds no answer for what "{entry["label"]}" '
                f"was on {as_of} — it had not been told, or it did not yet "
                "exist. What you have told it since is an answer about the "
                "days it was told, and carrying that back would size a "
                "decision made then against an account measured now")
        return _absent(entry.get("reason")
                       or "this journal has no answer for it yet")
    when = f", as it stood on {as_of}" if as_of else ""
    return _known(float(entry["value"]), "input", None,
                  [f'"{entry["label"]}", answered in this journal\'s '
                   f"settings{when}"])


def _account_value(cash, holdings) -> dict:
    """Free cash plus every holding at market. Derived rather than asked
    for: it is a figure the host can reach, and a typed one would let two
    numbers disagree with nothing to say which was wrong.

    One unpriced holding makes the whole total absent. Treating a missing
    price as zero would understate the account and quietly inflate every
    weight measured against it — a confident wrong answer in the number a
    sizing rule binds on.
    """
    if cash["status"] != "known":
        return _absent("the account is free cash plus the value of every "
                       "holding, and " + cash["reason"])
    dark = [h for h in holdings if h["market_value"]["status"] != "known"]
    if dark:
        names = ", ".join(str(h["ticker"]) for h in dark)
        return _absent(
            f"{len(dark)} of {len(holdings)} holdings have no price "
            f"({names}), so the account total cannot be reached without "
            "inventing one")
    total = cash["value"] + sum(h["market_value"]["value"] for h in holdings)
    # Every holding's price qualifiers, not only the cash figure's. The
    # account total is priced from as many closes as there are holdings, and
    # one series that stopped updating months ago is exactly the one worth
    # knowing about — the same reason a multi-class market cap reports its
    # OLDEST close rather than its freshest.
    cautions = list(cash.get("cautions") or [])
    for h in holdings:
        for note in h["market_value"].get("cautions") or []:
            line = f'{h["ticker"]}: {note}'
            if line not in cautions:
                cautions.append(line)
    return _known(total, "computed", cautions,
                  [f'{_usd(cash["value"])} free cash plus {len(holdings)} '
                   f'holding{"" if len(holdings) == 1 else "s"} at market'])


def _weight(market_value, account_value) -> dict:
    """A holding's share of the account, as a percent number. Arithmetic,
    not an opinion — whether a weight is too high belongs to a strategy."""
    if market_value["status"] != "known":
        return _absent(market_value["reason"])
    if account_value["status"] != "known":
        return _absent(account_value["reason"])
    if account_value["value"] <= 0:
        return _absent("the account works out to nothing or less once free "
                       "cash is included, so a share of it cannot be "
                       "expressed")
    # Both sides. A weight is this holding's price over an account priced
    # from every other holding's, so a qualifier on either one qualifies it —
    # and it forwarded only the account's, which is the half that says
    # nothing about the security in front of you.
    cautions = list(market_value.get("cautions") or [])
    for note in account_value.get("cautions") or []:
        if note not in cautions:
            cautions.append(note)
    return _known(market_value["value"] / account_value["value"] * 100,
                  "computed", cautions,
                  [f'{_usd(market_value["value"])} of an account of '
                   f'{_usd(account_value["value"])}'])


_NO_HOLDING = ("no position is held, so there is no purchase to measure "
               "from")


def _baseline_of(lot, anchor) -> dict:
    """One anchor purchase, as a strategy reads it: the day, and every figure
    that was frozen onto that decision.

    Read off the snapshot and never recomputed. That is principle 3 being
    load-bearing rather than decorative — a recomputation would answer "what
    do today's filings say about that day", which a restatement moves, and
    the question a re-underwrite asks is what you were shown when you said
    yes. It also means a baseline can never be improved by fetching more
    data, which is correct: the moment has passed and the record of it is
    closed.

    A purchase with no frozen record at all is absent rather than empty. The
    two would otherwise read identically — "no reading of this was on record"
    said thirty times over — and one of them is a gap in the data while the
    other is a gap in the journal, which point at different fixes.
    """
    if lot is None:
        return _absent(_NO_HOLDING)
    snapshot = lot.get("snapshot")
    if not isinstance(snapshot, dict):
        return _absent(
            f'the purchase on {lot.get("date")} that is {anchor["means"]} has '
            "no frozen record of what was true then, so there is nothing to "
            "measure against")
    measures = {}
    for eid, v in (snapshot.get("metrics") or {}).items():
        if isinstance(v, dict) and "value" in v:
            measures[eid] = _known(v["value"], v.get("source") or "frozen",
                                   v.get("cautions"), v.get("provenance"))
    return {"status": "known", "date": lot.get("date"), "lot": lot.get("id"),
            "measures": measures}


def _baselines(security, today) -> dict:
    """The two moments a rule about a holding can measure from.

    Both, always, and never one averaged out of the other. See
    contract.BASELINE_ANCHORS for why they are different questions: a
    business-deterioration rule anchored to the first purchase fires an exit
    on a position you consciously re-underwrote last quarter, and a drift
    rule anchored to the last purchase can never see six quarters of small
    declines that each looked fine against the one before.

    On a position bought exactly once the two are the same purchase, and that
    is not a special case to collapse — it is the honest answer, and the day
    they part company is the day the second purchase is recorded.

    The clock governs which purchases exist, exactly as it governs everything
    else here: under a pin, a purchase made after that day had not happened.
    """
    buys = portfolio.purchases_in_holding(security, today)
    first, last = (buys[0], buys[-1]) if buys else (None, None)
    return {
        "first-purchase": _baseline_of(
            first, contract.BASELINE_ANCHORS["first-purchase"]),
        "last-purchase": _baseline_of(
            last, contract.BASELINE_ANCHORS["last-purchase"]),
    }


def _position(security, today, as_of, account_value) -> dict:
    """The lot history as a strategy reads it: every acquisition with what
    remains of it, every disposal, and not one figure about cost.

    `opened` is the current holding period's first purchase — when this
    holding began — and is read off the period rather than recomputed here,
    so what a strategy is told and what the screens show for the same holding
    are one value rather than two that happen to agree.
    """
    held_lots = portfolio.open_lots(security, today)
    shares = round(sum(l["remaining"] for l in held_lots), 8)
    held = shares > 0
    opened = portfolio.opened_on(security, today)
    # Every purchase that built the holding you have now — the same period
    # `opened` is read off, so the first of these and `opened` are one value.
    # A trimmed-away lot is still one of them: it is still a day somebody
    # looked at this business and said yes.
    bought = portfolio.purchases_in_holding(security, today)
    out = {
        "held": held,
        "shares": shares,
        "opened": opened,
        # When you last put money in, and how many times you have. `opened`
        # answers when you started; these answer when you last agreed and how
        # often. They are the same day until the second purchase, and a rule
        # that wants one of them must not silently be reading the other —
        # which is why they are separate keys rather than one read two ways.
        "last_purchase": bought[-1]["date"] if bought else None,
        "purchases": len(bought),
        "baselines": _baselines(security, today),
        # Whole months from `opened` to the clock's today, counted by the
        # host's own month arithmetic. It is here so that a strategy with a
        # holding period in it does not have to write that arithmetic again:
        # adding months and counting them both have to clamp the same way,
        # and a count that disagrees with the clamp reports a position as 23
        # months held on the day its two-year clock falls due.
        "months_held": (contract.months_between(opened, today)
                        if held and opened else None),
        "lots": [{"date": l["date"], "shares": float(l["shares"]),
                  "remaining": l["remaining"], "open": l["open"]}
                 for l in held_lots],
        "disposals": [{"date": l["date"], "shares": float(l["shares"])}
                      for l in portfolio.lots(security, "sell", today)],
    }
    if held:
        out["market_value"] = _market_value(security, shares, today,
                                            as_of)
        out["weight"] = _weight(out["market_value"], account_value)
    else:
        out["market_value"] = _absent("no position is held")
        out["weight"] = _absent("no position is held")
    return out


def _portfolio(journal_securities, subject, today, as_of, roles) -> dict:
    holdings = []
    seen = set()
    # The security being evaluated counts even when the caller passed no
    # list: a portfolio that excluded the holding in front of you would
    # measure its weight against an account it was not part of.
    pool = list(journal_securities or [])
    if subject is not None:
        pool.append(subject)
    for sec in pool:
        ticker = str(sec.get("ticker") or "")
        if ticker in seen:
            continue
        seen.add(ticker)
        # The clock governs the portfolio exactly as it governs the position:
        # a holding bought after the pin did not occupy a slot then, and a
        # sale made after it had not reduced anything.
        shares = portfolio.shares_held(sec, today)
        if shares <= 0:
            continue
        holdings.append({
            "ticker": sec.get("ticker"), "name": sec.get("name"),
            "shares": shares,
            "opened": portfolio.opened_on(sec, today),
            "market_value": _market_value(sec, shares, today, as_of),
        })
    cash = _cash(roles, as_of)
    account_value = _account_value(cash, holdings)
    for h in holdings:
        h["weight"] = _weight(h["market_value"], account_value)
    return {
        "cash": cash,
        "account_value": account_value,
        "slots": {"occupied": len(holdings)},
        "holdings": holdings,
    }


def portfolio_view(journal_securities: list, roles: dict,
                   today: str | None = None) -> dict:
    """The journal's portfolio node on its own, without evaluating anything.

    The same free cash, account value, slot count and per-holding market
    values a strategy is handed — from the same code, not from a second
    implementation that agrees today. A screen about where capital goes has
    to measure against exactly the account the verdicts it is summarising
    were measured against, or two screens report different totals for the
    same holdings and neither is visibly the wrong one.
    """
    return _portfolio(journal_securities, None,
                      today or date.today().isoformat(), None, roles)


# -- the public build --------------------------------------------------------

def build_context(security: dict, journal_securities: list | None,
                  values: dict, inputs: dict,
                  as_of: str | None = None, record: dict | None = None) -> dict:
    """The context for one security, live or pinned.

    With `as_of`, everything is reconstructed from what was observable on
    that day — filings filed by then, the close on or before it, no
    hand-entered price — exactly as the as-of purchase machinery reads the
    past. Without it, the clock is today and the newest stored data serves.

    `record` is the loaded strategy. It is what turns the journal's raw
    answers into the ones that currently apply, and what says which of them
    the host may report as a figure. Without it the answers are passed
    through as given and no role is served — which is the honest reading of
    "there is no strategy to ask", not a silent fallback.
    """
    today = str(as_of)[:10] if as_of else date.today().isoformat()
    cik = security.get("cik")
    tickers = _tickers_of(security)

    effective, roles = dict(inputs or {}), {}
    if record is not None:
        effective, _ = contract.check_inputs(record, inputs or {},
                                             values or {})
        roles = contract.input_roles(record, effective)

    # The portfolio comes first: a position's weight is measured against an
    # account that includes the position, so the total has to exist before
    # any share of it can.
    folio = _portfolio(journal_securities, security, today, as_of, roles)
    ctx = {
        "contract": contract.CONTRACT_VERSION,
        "today": today,
        "security": {"ticker": security.get("ticker"),
                     "name": security.get("name"),
                     "cik": cik,
                     # The published industry code and what the host makes of
                     # it. Reported and not interpreted: whether a rule set
                     # has anything to say about a lender belongs to the rule
                     # set, and the same host serves strategies that would
                     # answer that differently.
                     **industry_mod.report(security, as_of)},
        # Two symbol scopes, deliberately. `tickers` is every class the SEC
        # maps to the company, which is what a whole-company measure needs.
        # The price is the security's own instrument and never sees that list.
        "measures": _measures(security, cik, tickers, as_of, today),
        "price": _price(security, cik, str(security.get("ticker") or ""),
                        as_of, today),
        "position": _position(security, today, as_of,
                              folio["account_value"]),
        "portfolio": folio,
        "values": values or {},
        "inputs": effective,
    }
    # One deep copy at the boundary: the strategy's dict shares nothing with
    # the journal or the dataview caches, so mutating it can corrupt nothing.
    return copy.deepcopy(ctx)
