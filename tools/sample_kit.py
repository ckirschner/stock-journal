"""Shared machinery for building the demonstration journals.

There is one of these per shipped strategy, because a journal has exactly
one strategy and two strategies means two journals. That is principle 6, and
a sample that showed it any other way would be teaching the opposite of what
the program enforces.

Everything a sample needs that is not its own story lives here: the scratch
data directory, the clock, and the wrappers that drive the real API. The
stories themselves live in the per-strategy scripts beside this file, because
a story is about one strategy's states and nothing about it generalises.

**Every company and every figure in a sample is invented.** Nothing in one is
a recommendation, a model portfolio, or a real security.

A sample is built by driving the real API against a scratch data directory,
so every lot, every frozen entry snapshot, every dated hand-entered figure
and every verdict is produced by the same code the app runs. Each security is
then evaluated and the state it exists to demonstrate is asserted. If a change
to a strategy or to the host moves any of those states, the script refuses to
write its file rather than shipping a sample that no longer shows what its own
notes claim.

**What a hand-built sample structurally cannot show.** No company in one is
linked to a CIK, so there is no filing history, so no series exists to walk.
Any exit whose rule is "breached on N consecutive filings" can therefore be
crossed but never confirmed. That is not a limitation of the samples — it is
true of any real journal driven by hand, and it is worth a reader knowing.
Each sample's own notes say which of its strategy's states it loses to this.
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# A scratch data directory, so building a sample can never touch a real
# journal. Set before anything imports the store.
#
# Assigned outright and never with setdefault, and the difference is the
# whole guarantee. LEDGER_DATA is the documented way somebody moves their
# real journals somewhere else, so it is precisely the variable most likely
# to already be pointing at live data — and a generator that yielded to it
# would drive the real API against the user's own store, add sample journals
# to it and switch which journal is open. "Cannot touch a real journal" has
# to be true by construction rather than by the variable happening to be
# unset; see principle 14.
os.environ["LEDGER_DATA"] = tempfile.mkdtemp(prefix="ledger-sample-")

from app import Api                                            # noqa: E402
from engine import dated, portfolio                            # noqa: E402

TEMPLATE_DIR = ROOT / "data.template"

api = Api()


class writing_on:
    """Write dated entries as though on a chosen day.

    Every record the user supplies is stamped by the host at the moment of
    writing and no caller can hand in its own date — that guarantee is what
    makes "what did I know then" answerable, and it is not weakened for a
    sample. So the generator does what a test does: it moves the clock the
    host reads, rather than asking politely for a date.
    """

    def __init__(self, day):
        # Local noon, because that is what the real stamp records: the day
        # the writer was standing on. A fixed UTC hour lands on the following
        # calendar day east of about UTC+10, which would build a sample whose
        # entries are dated a day after the story says they were.
        self.day = (datetime.fromisoformat(f"{day}T12:00:00")
                    .astimezone().isoformat(timespec="seconds"))

    def __enter__(self):
        self._dated, self._stamp = dated.stamp, portfolio._stamp
        dated.stamp = lambda: self.day
        portfolio._stamp = lambda: self.day

    def __exit__(self, *exc):
        dated.stamp, portfolio._stamp = self._dated, self._stamp


def call(fn, *a, **kw):
    r = fn(*a, **kw)
    assert r.get("ok"), f"{fn.__name__}: {r.get('error')}"
    return r


OPENED_ON = "2024-01-02"


def journal(name, strategy_id, inputs, cash=None):
    """Create the sample's journal, open its cash record, and leave it open.

    Created before the earliest entry in it, deliberately. What a journal has
    been told begins on the day it was created, and its cash record begins on
    the day it was opened — so a journal stamped today could not size a
    purchase it is being told about from two years ago, and every frozen
    verdict would read "waiting on setup" instead of the state its own note
    describes. A sample is a journal that has been kept for a while, and it is
    built as one.

    `cash` opens the record rather than answering a question: free cash is
    worked out from what the journal records moving, and the figure a sample
    starts with is day one of that. Dated the same day the journal is, because
    nothing may be recorded before the opening balance and every entry below
    comes after it.
    """
    with writing_on(OPENED_ON):
        return call(api.create_journal, name, strategy_id, inputs,
                    opening_cash=cash, opening_cash_on=OPENED_ON)


def security(ticker, name, price, values, on, thesis=None, notes=(),
             earlier=None, judged=()):
    """One invented company: its figures on the record, dated, with the
    thesis, notes and assessments that go with them.

    `judged` is [(day, bank id, "pass"|"fail", reasoning)] — the questions no
    filing answers. They are dated like everything else the user writes, and
    the record is append-only, so a mind changed about a business shows as
    two entries rather than one rewritten.
    """
    call(api.add_security, ticker, name)
    if earlier:
        day, figures, then_price = earlier
        with writing_on(day):
            call(api.save_metrics, ticker, figures, then_price)
    with writing_on(on):
        call(api.save_metrics, ticker, values, price)
        if thesis:
            call(api.amend_thesis, ticker, thesis[0], thesis[1])
    for day, entry_id, mark, reasoning in judged:
        with writing_on(day):
            call(api.record_judgement, ticker, entry_id, mark, reasoning)
    for day, text in notes:
        with writing_on(day):
            call(api.add_note, ticker, text)


def buy(ticker, shares, cost, opened, override_reason="", recollection=""):
    """One purchase, dated.

    `recollection` is what the buyer remembers thinking, on a purchase entered
    out of their own records rather than captured at the time. It is never a
    thesis and never counted as one — see engine/portfolio._recollection — and
    it is the only thing here that may be offered where an override reason
    cannot be, because there was no verdict to go against.
    """
    with writing_on(opened):
        return call(api.open_position, ticker, shares, cost, opened,
                    override_reason, None, recollection)


def sell(ticker, reason, price, exited, shares=None):
    with writing_on(exited):
        return call(api.sell_shares, ticker, reason, price, exited, shares)


def state_of(ticker):
    open_journal, record, chain, _ = api._open()
    s = api._find(open_journal, ticker)
    decision = api._decide(s, open_journal["securities"], open_journal,
                           record, chain)
    return decision["state"]["id"], decision


def expect(ticker, want):
    got, decision = state_of(ticker)
    assert got == want, (f"{ticker}: expected {want}, got {got} — "
                         f"{decision['reason']['summary']}")
    return decision


def securities():
    open_journal, *_ = api._open()
    return open_journal["securities"]


def import_list(pulled_on, tickers, floor=None):
    """One pull of the list a journal works from, dated.

    Written through the same API method the user's own import goes through,
    on the day the story says it was pulled — so the sample's lists are
    ordered by when they were imported exactly as a real journal's are, and
    the strategy's own freshness rule is answered off real records rather
    than off something written straight into the file.
    """
    with writing_on(pulled_on):
        return call(api.import_list, pulled_on, "\n".join(tickers), floor)


def pass_over(ticker, reason, on):
    with writing_on(on):
        return call(api.pass_over, ticker, reason)


def lists_of():
    open_journal, *_ = api._open()
    return list(open_journal.get("lists") or [])


def write(filename, strategy_id, free_cash, as_of, stories):
    """Assert every story, then write the file.

    The assertions are the gate. A sample whose companies no longer reach the
    states its notes describe is worse than no sample, because the notes are
    what a reader learns the states from.
    """
    for ticker, want in stories.items():
        expect(ticker, want)
    rows = securities()
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    path = TEMPLATE_DIR / filename
    payload = {"built": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "as_of": as_of,
               "free_cash": free_cash,
               "strategy": strategy_id,
               "securities": rows}
    # Only where there are any, so the three samples whose strategies screen
    # for themselves keep exactly the file they had.
    imported = lists_of()
    if imported:
        payload["lists"] = imported
    path.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}: {len(rows)} securities, "
          f"{len(set(stories.values()))} distinct states"
          + (f", {len(imported)} list imports" if imported else ""))
    return rows
