"""Where capital goes — one question, asked across the journal.

This module answers "I have money, where does it go". It is deliberately a
*different* question from "what does my strategy say about this security",
and the split is the whole reason it exists.

Asked per security, on the page you are already looking at, "should I buy
more of this" is an averaging-down machine with an authority stamp on it.
Nobody opens a holding's page at random; they open it because it is down. A
verdict sitting there saying "yes, more" is the tool lending its credibility
to the single most reliable way retail investors lose money, at the exact
moment they are looking for permission.

So the security page answers only whether this is *eligible* to receive
capital — which the strategy already says, by returning a state whose render
is `commit`. How much, and which one, is a portfolio question, and it is
answered here, on a screen you have to go to on purpose. The default reading
of this screen is the position furthest from where its own strategy wants it
to be, which structurally cannot be the thing you already hold too much of.

Nothing here holds an opinion. Every figure is arithmetic over what the
strategies supplied: a strategy said how much may go in and in what unit, the
host converts that to money using the account it already computes, and the
order is that number, descending. There is no scoring, no ranking by
conviction, no preference between two eligible names beyond which is further
from its own target. Where a figure cannot be reached — no price, no account
value, no free cash — it is absent with its reason and the entry is listed
unordered rather than ordered by a guess.

Two things this deliberately does not do.

It does not divide your money up for you. Splitting a sum across four names
is a view about how fast to deploy and how much to diversify, and neither is
the host's to hold. It says what each position could take and stops.

It does not evaluate a staged plan's condition. A commit carrying a condition
is capital the strategy is holding back, and the host reports the condition
in the strategy's own words without ever deciding whether it has been met.
The day it is met, the strategy returns that tranche as the size in front of
you, with no condition on it — because the strategy re-runs every time, which
is strictly better than a schedule executing itself six months after the last
time anybody looked at the company.
"""

from __future__ import annotations

# Only `commit` says capital may go in. That is the host's own vocabulary,
# defined by the contract, so reading it is not an opinion about investing —
# `commit` means "capital may go in" by definition, and which securities
# deserve capital is never asked here.
ELIGIBLE_RENDER = "commit"


def _known(value, provenance=None) -> dict:
    return {"status": "known", "value": value,
            "provenance": list(provenance or [])}


def _absent(reason: str) -> dict:
    return {"status": "absent", "reason": reason}


def _usd(n) -> str:
    return f"${n:,.0f}"


def _each(n) -> str:
    """A price per share, to the cent.

    Separate from `_usd` because a provenance line exists to let the reader
    redo the arithmetic, and rounding a price to the dollar breaks it: "10
    shares at $12" beside a figure of $125 is a sentence that does not add
    up, and the reader has no way to tell whether the price or the total is
    the wrong one. Cents are noise on an account total and load-bearing on a
    single share.
    """
    return f"${n:,.2f}"


def _money(size, account_value, price, ticker) -> dict:
    """What a strategy's size comes to in money.

    A strategy sizes in whatever unit suits it — a share of the account, a
    figure in dollars, a number of shares — and two of those cannot be
    compared across securities without converting. The conversion is
    arithmetic over figures the host already owns, which is the only reason
    it is allowed to happen here at all.

    Every way it can fail is absence with its own reason, never a fallback.
    A weight with no account value behind it, or a share count with no price,
    would each produce a plausible dollar figure from a number that is not
    there — and this figure decides what order the screen puts your holdings
    in, which is the one place a confident wrong answer would be acted on
    without being read.
    """
    unit, value = size.get("unit"), size.get("value")
    if unit == "usd":
        return _known(float(value), ["the strategy sized this in dollars"])
    if unit == "weight":
        if account_value.get("status") != "known":
            return _absent(
                "the strategy sized this as a share of the account, and "
                + account_value.get("reason", "the account value is not known"))
        total = float(account_value["value"])
        return _known(total * float(value) / 100.0,
                      [f"{value:g}% of an account of {_usd(total)}"])
    if unit == "shares":
        if price.get("status") != "known":
            return _absent(
                "the strategy sized this in shares, and "
                + price.get("reason", f"no price is on record for {ticker}"))
        each = float(price["value"])
        return _known(each * float(value),
                      [f"{value:g} shares at {_each(each)}"])
    return _absent(f'the strategy sized this in "{unit}", which the host '
                   "cannot turn into money")


def _tranche(size, condition, account_value, price, ticker) -> dict:
    return {"size": dict(size),
            "condition": dict(condition) if condition else None,
            "amount": _money(size, account_value, price, ticker)}


def _plan_view(payload, account_value, price, ticker) -> dict | None:
    """A staged entry as the screen reads it: what goes in now, what is held
    back, and what releases each part.

    `held_back` totals only the tranches whose money could be worked out. A
    total quietly missing one of them would understate what you are
    committing to, so where any tranche is unpriced the total is absent and
    says which — the same rule the account value follows when one holding has
    no price.
    """
    plan = payload.get("plan")
    if not plan:
        return None
    tranches = [_tranche(t["size"], t["condition"], account_value, price,
                         ticker) for t in plan]
    dark = [i + 1 for i, t in enumerate(tranches)
            if t["amount"]["status"] != "known"]
    if dark:
        held_back = _absent(
            f"{len(dark)} of the {len(tranches)} tranches held back could not "
            "be worked out in money, so the total cannot be either")
    else:
        held_back = _known(
            sum(t["amount"]["value"] for t in tranches),
            [f"{len(tranches)} tranche" + ("" if len(tranches) == 1 else "s")
             + " held back"])
    return {"tranches": tranches, "held_back": held_back}


def _target(committed, now, held_back) -> dict:
    """What the whole position is meant to come to: what is already in, plus
    what goes in now, plus what is being held back.

    Derived rather than declared, so it cannot disagree with the parts it is
    made of. One unknown part makes the whole thing absent — a target that
    quietly dropped a tranche it could not price would read as a smaller
    commitment than the strategy actually described, which is the direction
    that gets acted on.
    """
    parts = [(name, p) for name, p in
             (("what is already in", committed),
              ("what may go in now", now),
              ("what is held back", held_back)) if p is not None]
    made_of = ", plus ".join(name for name, _p in parts)
    dark = [name for name, p in parts if p.get("status") != "known"]
    if dark:
        return _absent(f"it is {made_of}, and " + " and ".join(dark)
                       + " could not be worked out")
    return _known(sum(p["value"] for _n, p in parts), [made_of])


def _summary_of(decision) -> str:
    return ((decision or {}).get("reason") or {}).get("summary") or ""


def _entry(security, decision, price, account_value) -> dict:
    """One security's line, whichever side of the fence it falls."""
    state = (decision or {}).get("state") or {}
    return {
        "ticker": security.get("ticker"),
        "name": security.get("name"),
        "held": float(security.get("_shares") or 0) > 0,
        "shares": security.get("_shares"),
        "render": (decision or {}).get("render"),
        "state": {"id": state.get("id"), "name": state.get("name"),
                  "description": state.get("description")},
        "rule": ((decision or {}).get("reason") or {}).get("rule"),
        "summary": _summary_of(decision),
        "tier": (decision or {}).get("tier"),
        # Which side produced it. A strategy saying "not this one" and the
        # host saying "I could not ask" are different facts and this screen
        # has to be able to tell them apart — one is the discipline working
        # and the other is a machine that needs fixing.
        "produced_by": (decision or {}).get("produced_by"),
        "price": price,
    }


def _order(entries) -> list:
    """Furthest from its own target first.

    The ordering is the whole defence against the doom loop, and it is pure
    arithmetic over what the strategies said: the position with the most room
    left under its own strategy's size for it goes to the top. The thing you
    already hold too much of is never what this suggests, because it has the
    least room by construction — not because anything here decided it was a
    bad idea.

    Entries whose money could not be worked out sort last, in ticker order,
    and keep their reason. Ordering them by nothing would be inventing a
    position for them in a list whose whole meaning is the position.
    """
    ordered = [e for e in entries if e["amount"]["status"] == "known"]
    unordered = [e for e in entries if e["amount"]["status"] != "known"]
    ordered.sort(key=lambda e: (-e["amount"]["value"], str(e["ticker"] or "")))
    unordered.sort(key=lambda e: str(e["ticker"] or ""))
    return ordered + unordered


def view(securities, decisions, prices, folio) -> dict:
    """The allocation screen, whole.

    `decisions` and `prices` are keyed by ticker: the verdict already
    computed for each security and the price already read for it. `folio` is
    the host's own portfolio node — the same free cash, account value and
    per-holding market values every strategy in this journal was handed.

    Nothing is evaluated again and nothing is priced again. A second
    computation is a second chance for two screens to disagree about the same
    holding, and this one exists to be read beside the security pages it
    summarises: an account value here that differed from the one behind a
    weight there would make both untrustworthy without either being visibly
    wrong.
    """
    cash = folio.get("cash") or _absent("free cash is not recorded")
    account_value = folio.get("account_value") or _absent(
        "the account value could not be reached")
    at_market = {h.get("ticker"): h.get("market_value")
                 for h in folio.get("holdings") or []}

    ready, waiting, excluded = [], [], []
    for s in securities:
        ticker = s.get("ticker")
        decision = decisions.get(ticker)
        price = prices.get(ticker) or _absent(
            f"no price is on record for {ticker}")
        entry = _entry(s, decision, price, account_value)
        if (decision or {}).get("render") != ELIGIBLE_RENDER:
            excluded.append(entry)
            continue

        payload = decision.get("payload") or {}
        size = payload.get("size") or {}
        condition = payload.get("condition")
        # None where nothing is held: a first purchase has nothing committed,
        # and "$0" would put a confident figure where the honest answer is
        # that the question does not arise yet.
        committed = at_market.get(ticker)
        entry.update({
            "size": dict(size),
            "amount": _money(size, account_value, price, ticker),
            "condition": dict(condition) if condition else None,
            "committed": committed,
            "plan": _plan_view(payload, account_value, price, ticker),
        })
        entry["target"] = _target(
            committed, entry["amount"],
            (entry["plan"] or {}).get("held_back") if entry["plan"] else None)
        # A condition is the strategy holding this back. The host never
        # decides whether it has been met — it is prose, and the strategy
        # re-reads it on its own next evaluation — so the two lists are "the
        # strategy says now" and "the strategy says not yet", never "we
        # checked and it is not time".
        (waiting if condition else ready).append(entry)

    ready, waiting = _order(ready), _order(waiting)
    return {
        "cash": cash,
        "account_value": account_value,
        "ready": ready,
        "waiting": waiting,
        "excluded": sorted(excluded, key=lambda e: str(e["ticker"] or "")),
        "standing": _standing(securities, ready, waiting, excluded, cash),
    }


def _affordable(ready, cash) -> dict:
    """Whether the free cash on record covers anything on the list.

    Anything, not the first thing. The list is ordered by how much each
    position could take, so the top of it is the *largest* — and a screen
    that said "the free cash does not cover the first of them" over four
    smaller names it comfortably covers would be reporting the one entry the
    reader is least able to act on as though it were the whole answer. The
    honest question is whether there is somewhere for the money to go at all.

    Reported and never enforced. A journal that does not record cash gets an
    absence naming the question nobody asked, not a screen that refuses to
    show what the strategy said.
    """
    priced = [e for e in ready if e["amount"]["status"] == "known"]
    if not priced:
        return _absent("nothing on the list has an amount that could be "
                       "worked out in money")
    if cash.get("status") != "known":
        return _absent(cash.get("reason") or "free cash is not known")
    free = float(cash["value"])
    within = [e for e in priced if free >= e["amount"]["value"]]
    smallest = min(e["amount"]["value"] for e in priced)
    return _known(bool(within),
                  [f"{_usd(free)} free against "
                   + (f'{len(within)} of {len(priced)} positions it covers'
                      if within else
                      f"the smallest of {len(priced)}, which could take "
                      f"{_usd(smallest)}")])


def _standing(securities, ready, waiting, excluded, cash) -> dict:
    """What this screen says when there is nothing on it.

    An empty list is the ordinary outcome of a disciplined strategy, and an
    empty screen teaches nothing. Holding cash because nothing qualifies is a
    position — it is the position, most of the time — and the screen has to
    say so with the arithmetic that makes it true, rather than rendering as
    though something had failed to load.

    Four standings, because they call for four different things and one
    message covering all of them would be wrong three times:

      empty       nothing is tracked at all. The only screen here that
                  invites an action, because it is the only one where there
                  is an action.
      unfunded    the strategy has somewhere to put money and there is none
                  to put. Not a failure of the rules.
      cash        every security was considered and none qualifies. This is
                  the strategy working, and the count of what it turned down
                  is the evidence for that rather than a consolation.
      open        there is somewhere to put capital now.

    Nothing here is scored or hidden. The securities that did not qualify are
    listed with the state that excluded them, because "your strategy said no
    to eleven names today" is the useful half of an empty screen, and because
    a name you bought against the signal has to be recordable from somewhere.
    """
    unasked = [e for e in excluded if e["produced_by"] != "strategy"]
    if securities and not ready and not waiting \
            and len(unasked) == len(excluded):
        return {
            "id": "unavailable",
            "headline": "This journal's strategy could not be asked.",
            "detail": (
                f"None of the {len(securities)} "
                + ("security" if len(securities) == 1 else "securities")
                + " below has a verdict, and the reason is against each of "
                  "them — the Strategy tab says what to fix. Nothing you "
                  "have recorded is affected, and recording a purchase is "
                  "never blocked by this: every name is still listed, and "
                  "buying one is logged the way any purchase made without a "
                  "signal is."),
            "action": None}
    if not securities:
        return {"id": "empty", "headline": "Nothing is being tracked yet.",
                "detail": "Add a security and this journal's strategy will "
                          "say what it makes of it.",
                "action": "Add a security"}
    if ready:
        afford = _affordable(ready, cash)
        if afford["status"] == "known" and afford["value"] is False:
            return {
                "id": "unfunded",
                "headline": f"{len(ready)} position"
                            + ("" if len(ready) == 1 else "s")
                            + " could take capital, and the free cash on "
                              "record does not cover any of them.",
                "detail": "The list still says where money would go. What it "
                          "cannot do is find any — recording a cash balance "
                          "in this journal's settings is what makes this "
                          "arithmetic honest.",
                "action": None}
        return {"id": "open",
                "headline": f"{len(ready)} position"
                            + ("" if len(ready) == 1 else "s")
                            + " may take capital now.",
                "detail": "Furthest from where its own strategy wants it "
                          "first. Nothing here is a recommendation to buy — "
                          "it is where this journal's rules say capital "
                          "belongs if you are putting any in.",
                "action": None}
    held = len([s for s in securities if s.get("_shares")])
    return {
        "id": "cash",
        "headline": "Nothing qualifies today.",
        "detail": (
            f"Your strategy looked at {len(securities)} "
            + ("security" if len(securities) == 1 else "securities")
            + (f", {held} of which you hold" if held else "")
            + ", and will not put capital into any of them"
            + (f". {len(waiting)} " + ("is" if len(waiting) == 1 else "are")
               + " waiting on a condition it stated" if waiting else "")
            + ". That is the strategy working rather than failing — cash is a "
              "position, and it is the one your own rules are asking for. "
              "Every name is below with the rule that turned it down."),
        "action": None,
    }
