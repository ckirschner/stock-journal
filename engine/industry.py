"""What kind of company a filer is, from the industry code the SEC publishes.

The host holds no opinion about which strategy is right, and this module holds
none either. What it holds is a *fact*: the SEC assigns every filer a Standard
Industrial Classification code, EDGAR publishes it, the fetch already stores
it, and some of those codes name businesses the host's own measures were never
built to describe. Saying which is reporting. What a strategy does about it —
route to different rules, decline the company outright, ignore the whole
question — is the strategy's business and happens nowhere near here.

Why it exists at all, in one paragraph. Nearly every measure in the bank was
written for a company that sells something: revenue at the top, costs beneath
it, a balance sheet split into what falls due within the year and what does
not, and capital spending that is a choice. A bank fits none of that. Its
liabilities are deposits, its assets are loans, it does not classify anything
as current, and its operating cash flow moves with the period's change in
loans and deposits rather than with the business — so a *shrinking* bank
generates enormous free cash flow. An insurer's investment portfolio is held
against policy reserves and its cash flow carries the growth of float. A
property company's depreciation is an accounting artefact rather than a cost,
which puts every measure built on net income in the wrong place. Each of those
is a different failure and each one produces a confident number rather than a
gap, which is worse than a gap: absence renders as absence, and a wrong figure
renders as an answer.

**Code by code, never by range.** The SEC publishes a closed list — forty-one
codes between 6000 and 6999 — so a table over it is a statement about codes
that exist, where a range is a guess about codes that do not. Every range an
ordinary reading suggests is wrong somewhere, and the ways it is wrong are
recorded in tests/fixtures/groundtruth/sec-sic-6xxx-notes.md beside the
published list itself: the band that stops one code short of the
broker-dealers, the one that sweeps insurance brokers in with insurers, the
one that classifies a blank-cheque shell as real estate.

**A code that cannot settle it does not settle it.** Several of the forty-one
are catch-alls the SEC assigns to filers whose economics are opposite —
American Express files under the same code as a payment processor, Bear
Stearns under the same one as BlackRock. There is no fourth answer for those
and there must not be one: the classification is *absent*, with a reason
saying which code it was and what the code holds. That is principle 4 doing
the work it always does. An unrecognised 6xxx code is absent for the same
reason — the SEC adding one must not read as "an ordinary business" by
default, because the whole band is where the failures are.

**Two absences, and only one of them is evidence of anything.** A code that
was published and cannot be classified is a *problem the host can see*, and
the node says so with `unclassifiable`. No code at all is not: a security
nobody has fetched yet, or one that was never tied to a filer because its
figures are hand-entered, tells us nothing about what kind of company it is.
A journal driven entirely by hand is a supported way to use this program, and
treating "never fetched" as "possibly a bank" would refuse every verdict in
one. So a strategy that declines classes refuses the first and runs on the
second, and the difference is that the first has a published fact behind it
that points somewhere the measures do not go.

**The classification is identity, not measurement, and the clock does not
govern it.** Every measure the host serves obeys the day being evaluated,
because a restatement can move what a past day's filings said. This does not,
and the difference is worth stating rather than assuming. The SEC publishes
only a filer's *current* assignment — there is no "SIC as of March 2024" to
fetch — so the honest reading is what the identity record on disk holds, which
is append-only and stamped with the day each observation was made. A
reconstruction is served the observation that was in force on its day; a
reconstruction of a day before this program ever fetched the company is served
the earliest observation there is, and says so in its provenance rather than
reporting an absence that would refuse every backdated evaluation in the
journal. Where the class has actually moved between observations, the reading
carries a caution naming when and from what — a company that reclassifies part
way through a holding is a real case, and it is the case a silent answer would
hide.
"""

from __future__ import annotations

from . import contract, facts_store

# ---------------------------------------------------------------------------
# The published band, code by code.
#
# `None` means the code names a business the host's ordinary measures
# describe — the answer is "nothing special about this one", which is a real
# answer and not an absence. A string names one of contract.INDUSTRY_CLASSES.
# A code that is *missing* from this table but sits in the 6xxx band is
# refused rather than defaulted; see `classify`.
#
# Titles are the SEC's own, cased for reading. tests/test_industry.py pins
# both the codes and the titles against the published list, so a code the SEC
# adds or renames is a failing test rather than a silent gap.
# ---------------------------------------------------------------------------

_DEPOSIT, _INSURE, _PROPERTY = ("depository-lending", "insurance",
                                "real-estate")

# Codes the SEC assigns to filers whose economics are opposite. Each says what
# it holds, in the sentence a reader gets, because "we could not classify it"
# on its own teaches nothing and looks like a bug.
AMBIGUOUS = {
    "6199": "the SEC assigns this code both to lenders — American Express and "
            "Synchrony Financial file under it — and to payment processors, "
            "securitisation trusts and crypto businesses, whose economics are "
            "nothing alike. Its own entry in the SEC's list routes it to two "
            "different offices, which is the source saying the code does not "
            "settle it",
    "6200": "the SEC assigns this code both to exchanges, which are ordinary "
            "asset-light businesses, and to inter-dealer brokers and funds, "
            "whose balance sheets are other people's money. The code does not "
            "say which this is",
    "6211": "the SEC assigns this code both to broker-dealers, whose balance "
            "sheet is trading inventory and customer cash, and to asset "
            "managers, which are ordinary fee businesses. The code does not "
            "say which this is",
    "6221": "a commodity dealer's balance sheet is open contracts and margin "
            "held for other people, and its cash from operations moves with "
            "those rather than with the business. That is a third thing "
            "again — it is not lending and it is not an ordinary operating "
            "company — and this host has no class that honestly describes it",
    "6770": "a blank-cheque shell has no operating business yet, so nothing "
            "here describes it, and the code says nothing about what it "
            "intends to become",
    "6799": "the SEC assigns this code to closed-end funds, business "
            "development companies, limited partnerships and investment "
            "holding companies alike. What such a filer reports as operating "
            "cash flow is its investing, and the code does not say which kind "
            "of vehicle it is",
}

SIC = {
    # -- deposits, loans and lease receivables ---------------------------
    "6021": (_DEPOSIT, "National Commercial Banks"),
    "6022": (_DEPOSIT, "State Commercial Banks"),
    "6029": (_DEPOSIT, "Commercial Banks, NEC"),
    "6035": (_DEPOSIT, "Savings Institution, Federally Chartered"),
    "6036": (_DEPOSIT, "Savings Institutions, Not Federally Chartered"),
    "6099": (_DEPOSIT, "Functions Related to Depository Banking, NEC"),
    "6111": (_DEPOSIT, "Federal & Federally-Sponsored Credit Agencies"),
    "6141": (_DEPOSIT, "Personal Credit Institutions"),
    "6153": (_DEPOSIT, "Short-Term Business Credit Institutions"),
    "6159": (_DEPOSIT, "Miscellaneous Business Credit Institution"),
    "6162": (_DEPOSIT, "Mortgage Bankers & Loan Correspondents"),
    # A loan broker looks like a fee business and is not one: loans held for
    # sale sit on the balance sheet between origination and sale, and
    # operating cash flow swings with origination volume rather than with the
    # business. Same failure as a lender's, from the same cause.
    "6163": (_DEPOSIT, "Loan Brokers"),
    "6172": (_DEPOSIT, "Finance Lessors"),
    "6189": (_DEPOSIT, "Asset-Backed Securities"),
    "6199": (None, "Finance Services"),                 # see AMBIGUOUS
    "6200": (None, "Security & Commodity Brokers, Dealers, Exchanges & "
                   "Services"),                         # see AMBIGUOUS
    "6211": (None, "Security Brokers, Dealers & Flotation Companies"),
    "6221": (None, "Commodity Contracts Brokers & Dealers"),  # see AMBIGUOUS
    # Fee income against a small balance sheet. An asset manager is an
    # ordinary business by every measure here, which is exactly why routing
    # all of 6xxx one way would have been wrong.
    "6282": (None, "Investment Advice"),

    # -- insurance -------------------------------------------------------
    "6311": (_INSURE, "Life Insurance"),
    "6321": (_INSURE, "Accident & Health Insurance"),
    "6324": (_INSURE, "Hospital & Medical Service Plans"),
    "6331": (_INSURE, "Fire, Marine & Casualty Insurance"),
    "6351": (_INSURE, "Surety Insurance"),
    "6361": (_INSURE, "Title Insurance"),
    "6399": (_INSURE, "Insurance Carriers, NEC"),
    # Brokers, not carriers. They hold no reserves and carry no underwriting
    # risk — Marsh, Aon and Brown & Brown are fee businesses whose margins,
    # returns on capital and free cash flow all mean what they usually mean.
    "6411": (None, "Insurance Agents, Brokers & Service"),

    # -- property --------------------------------------------------------
    "6500": (_PROPERTY, "Real Estate"),
    "6510": (_PROPERTY, "Real Estate Operators (No Developers) & Lessors"),
    "6512": (_PROPERTY, "Operators of Nonresidential Buildings"),
    "6513": (_PROPERTY, "Operators of Apartment Buildings"),
    "6519": (_PROPERTY, "Lessors of Real Property, NEC"),
    # For others: a managing agent earns fees and owns none of the buildings,
    # so depreciation is not doing anything strange to its earnings.
    "6531": (None, "Real Estate Agents & Managers (For Others)"),
    "6532": (_PROPERTY, "Real Estate Dealers (For Their Own Account)"),
    "6552": (_PROPERTY, "Land Subdividers & Developers (No Cemeteries)"),
    "6770": (None, "Blank Checks"),                     # see AMBIGUOUS
    # Royalty vehicles, and not property whatever the office that reviews
    # them. There is no depreciable building here and no rent roll.
    "6792": (None, "Oil Royalty Traders"),
    "6794": (None, "Patent Owners & Lessors"),
    "6795": (None, "Mineral Royalty Traders"),
    "6798": (_PROPERTY, "Real Estate Investment Trusts"),
    "6799": (None, "Investors, NEC"),                   # see AMBIGUOUS
}


def _known(value, cautions=None, provenance=None, **extra) -> dict:
    node = {"status": "known", "value": value, "source": "sec",
            "cautions": list(cautions or []),
            "provenance": list(provenance or [])}
    node.update(extra)
    return node


def _absent(reason: str, **extra) -> dict:
    node = {"status": "absent", "reason": reason}
    node.update(extra)
    return node


def _code(sic) -> str:
    """A SIC as the SEC publishes it.

    EDGAR has served it as a string and as a number at different times, and a
    code that arrived as 6021 rather than "6021" must not read as a company
    the host has never heard of. Nothing else is done to it — not padded, not
    normalised — because the published list holds three-digit codes as well as
    four, and a code this program reshaped would no longer be the SEC's.
    """
    text = str(sic or "").strip()
    return text[:-2] if text.endswith(".0") else text


def classify(sic) -> tuple:
    """(class id or None, one sentence saying why there is no class) for one
    SIC code.

    Three outcomes and no fourth. A class the host names; `None` with no
    complaint, meaning the code names a business the ordinary measures
    describe; or `None` with a sentence, meaning the code does not settle it
    and the classification is therefore absent rather than defaulted.

    "No code at all" comes back with a sentence too, which is right for a
    direct caller — an unclassified filer is not an ordinary one. `report`
    never reaches it: it answers a filer with nothing on record first, and
    with a different sentence, because "the SEC published none" and "the code
    it published does not settle it" point at different fixes.
    """
    code = _code(sic)
    if not code:
        return None, ("the SEC has published no industry code for this filer")
    if code in AMBIGUOUS:
        return None, f"SIC {code} does not say what kind of company this is: "\
                     f"{AMBIGUOUS[code]}"
    hit = SIC.get(code)
    if hit is not None:
        return hit[0], None
    if code[:1] == "6":
        # Refused, never defaulted. Every failure this module exists for is
        # inside this band, so a code the SEC has added since — or one this
        # table is missing — must not be waved through as an ordinary
        # business. Loud and absent beats quiet and wrong.
        return None, (f"SIC {code} is a financial-sector code this program "
                      "does not recognise, so what kind of company this is "
                      "cannot be said. Codes in the 6000s are the ones whose "
                      "accounts the measures here are not built for, so an "
                      "unrecognised one is refused rather than assumed "
                      "ordinary")
    return None, None


def noun_of(cls: str) -> str:
    """What to call a kind of company in a sentence — "banks and lenders".

    Read off the host's own table rather than spelled out at each call site,
    so a class the host renames is renamed everywhere it is spoken about.
    """
    spec = contract.INDUSTRY_CLASSES.get(cls)
    return spec["noun"] if spec else str(cls)


def title_of(sic) -> str | None:
    """The SEC's own title for a code, where this table holds one. Used only
    where the filer record carries no description of its own."""
    hit = SIC.get(_code(sic))
    return hit[1] if hit else None


def _observations(doc: dict) -> list:
    """Every distinct industry code this program has observed for one filer,
    oldest first, as (observed stamp, sic, description).

    Read off the append-only identity history rather than off the current
    record alone, and collapsed on the code: the history appends whenever any
    part of a filer's identity moves — a ticker, the forms it files — and
    twelve entries saying 6021 are one observation, not twelve.
    """
    out = []
    history = doc.get("identity_history")
    entries = history if isinstance(history, list) else []
    for h in entries:
        ident = h.get("identity") if isinstance(h, dict) else None
        if not isinstance(ident, dict):
            continue
        code = _code(ident.get("sic"))
        if out and out[-1][1] == code:
            continue
        out.append((str(h.get("observed") or "")[:10], code,
                    str(ident.get("sic_description") or "").strip() or None))
    if out:
        return out
    ident = doc.get("identity")
    if isinstance(ident, dict):
        return [(None, _code(ident.get("sic")),
                 str(ident.get("sic_description") or "").strip() or None)]
    return []


def _in_force(seen: list, on: str | None) -> tuple:
    """(the observation in force on `on`, whether it predates every
    observation).

    Before the first observation the earliest is served, and the caller says
    so. It is the one place here that reaches across a date, and it is a
    deliberate departure from how every measure behaves: a measure is a
    reading of a moment and a restatement can move it, so serving today's for
    a past day would rewrite what somebody was shown. An industry code is not
    a reading of a moment — the SEC publishes only the current assignment and
    no history of it exists to consult — so refusing to answer would not be
    more honest, it would only refuse every backdated evaluation in every
    journal over a fact that almost never moves. What it does instead is say
    which observation it is using and when that observation was made.
    """
    if not seen:
        return None, False
    if not on:
        return seen[-1], False
    applicable = [s for s in seen if s[0] and s[0] <= on]
    if applicable:
        return applicable[-1], False
    return seen[0], True


def _moved(seen: list, chosen: tuple) -> list:
    """A caution for each time this filer's CLASS changed, naming the day it
    was first seen to have changed and what it was before.

    The class and not the code. A filer moving from 6021 to 6022 has changed
    which regulator chartered it and nothing whatever about how its accounts
    read, and a caution on every such move would be noise on the one node a
    reader most needs to trust.
    """
    out = []
    for before, after in zip(seen, seen[1:]):
        was, now = classify(before[1])[0], classify(after[1])[0]
        if was == now:
            continue
        label = (contract.INDUSTRY_CLASSES[was]["label"] if was
                 else "an ordinary operating business")
        out.append(
            f"this filer was classified as {label} (SIC {before[1] or 'none'})"
            f" until {after[0] or 'a later fetch'}, when the SEC's code for it"
            f" became {after[1] or 'none'}"
            + (" — the reading above is the earlier one"
               if chosen is before else ""))
    return out


def NOT_ESTABLISHED() -> dict:
    """A history for a filer nobody has established — no code, no problem.

    Spelled out rather than defaulted. Everything that computes a measure has
    to say what kind of company it is computing for, and the honest answer is
    sometimes "nothing on record": synthetic filings in a test, a security
    driven entirely by hand. Naming it costs one argument and buys the thing a
    default cannot — a computation site that forgets is refused rather than
    quietly ungated, which is the whole difference between a boundary and a
    habit.
    """
    return {"seen": [], "problem": None}


def history(security: dict) -> dict:
    """Everything one filer's identity record says about its industry, read
    once: {"seen": [...observations, oldest first...], "problem": node|None}.

    Split out from `report` because a per-filing series asks the same
    question at a dozen dates, and reading the record a dozen times would
    both cost a dozen file reads and let two of them disagree — the record
    can be rewritten by a fetch between two of the reads, and a series whose
    2019 point saw one identity and whose 2024 point saw another would be a
    history nobody could reconcile. Read once, resolved many times.

    Plain data, so it can cross into `compute` without dragging the store
    behind it: a computation is told what kind of company this is and reaches
    for nothing.
    """
    cik = security.get("cik")
    if not cik:
        return {"seen": [], "problem": _absent(
            "this security has not been tied to a company on EDGAR yet, so "
            "the SEC's industry code for it is not on record — fetch its "
            "data")}
    try:
        doc = facts_store.load_company(int(cik))
    except Exception as e:  # noqa: BLE001 — an unreadable file is a fact
        return {"seen": [], "problem": _absent(
            "the stored company record could not be read "
            f"({type(e).__name__}: {e}), so the SEC's industry code for this "
            "filer cannot be reported")}
    return {"seen": _observations(doc), "problem": None}


def at(hist: dict, as_of: str | None = None) -> dict:
    """{"sic": node, "industry": node} for one day, from a history already
    read.

    Both from one reading of the record, because they are two views of one
    fact and two readers of it could disagree about which observation was in
    force. The code is reported whether or not it classifies: a filer whose
    code the host cannot act on still has a code, and a reader looking at an
    absent classification should be able to see the thing that could not be
    classified rather than being told only that something failed.
    """
    problem = (hist or {}).get("problem")
    if problem is not None:
        return {"sic": problem, "industry": dict(problem)}

    seen = list((hist or {}).get("seen") or [])
    chosen, before_first = _in_force(seen, as_of)
    if chosen is None or not chosen[1]:
        gone = _absent(
            "no industry code is stored for this filer — its identity has "
            "not been fetched from EDGAR yet, or EDGAR published none")
        return {"sic": gone, "industry": dict(gone)}

    when, code, described = chosen
    cls, why = classify(code)
    title = described or title_of(code) or "no title published"
    read = ("as the SEC classified this filer"
            + (f" when it was last read from EDGAR on {when}" if when
               else " in the record on disk")
            + (f". Nothing on record says what the code was on {as_of}: the "
               "SEC publishes only a filer's current assignment, so this is "
               "the earliest observation there is"
               if before_first and as_of else ""))
    where = f"SIC {code} ({title}), {read}"
    cautions = _moved(seen, chosen)
    published = _known(f"{code} — {title}", cautions, [where],
                       **{"sic": code, "title": title})

    if why is not None:
        # `unclassifiable` and not merely absent. A code was published and
        # the host cannot act on it, which is a different fact from having no
        # code at all — the first says the SEC has told us something that
        # points where these measures do not go, the second says nobody has
        # asked yet. Only the first is grounds for refusing to evaluate.
        return {"sic": published,
                "industry": _absent(f"{why} ({title}, {read})",
                                    sic=code, title=title,
                                    unclassifiable=True)}
    label = (contract.INDUSTRY_CLASSES[cls]["label"] if cls
             else "Ordinary operating business")
    return {"sic": published,
            "industry": _known(label, cautions, [where],
                               **{"class": cls, "sic": code, "title": title})}


def report(security: dict, as_of: str | None = None) -> dict:
    """{"sic": node, "industry": node} for one security on one day."""
    return at(history(security), as_of)


def observation(security: dict, as_of: str | None = None) -> dict:
    """What kind of company this security's filer is, as the host reports it.

    Known with a class the host names, known with no class at all (an
    ordinary operating business, which is a real answer), or absent with the
    reason — never a guess, and never "ordinary" standing in for "we could
    not tell". The two absences read differently on purpose: nothing has been
    fetched, or the code the SEC published does not settle it.
    """
    return report(security, as_of)["industry"]
