"""Which of a company's symbols is its common stock.

Market capitalisation is denominated in the common stock. A warrant, a
preferred series, a unit, a right or an exchange-listed note never is, and the
SEC's ticker map — the only list of a filer's symbols the host has — says
which company a symbol belongs to and nothing whatever about what the symbol
*is*. Synchrony Financial maps to SYF, SYF-PA and SYF-PB; Bank of America to
BAC and eleven preferred series; an ordinary post-SPAC operating company to
its share, its unit and its warrant. Pick the wrong one and the whole
valuation half of every strategy is wrong in a way that looks right, because a
dollar figure is plausible in shape whatever its value.

**The authoritative source is the filer, on the cover of its own filing.**
Since the cover-page tagging the SEC phased in over 2019-2021, every 10-K and
10-Q carries the "Securities registered pursuant to Section 12(b) of the Act"
table in XBRL: one row per registered security, each with the instrument's
title, its trading symbol and its exchange. That is the company saying, in the
same document the share count comes from, that SYF is "Common stock, par value
$0.001 per share" and SYFPrA is "Depositary Shares Each Representing a 1/40th
Interest in a Share of 5.625% ... Preferred Stock". Nothing is inferred from
the shape of a symbol. The last time this program reasoned from a code pattern
rather than a published statement it was wrong in the way that mattered, and a
suffix convention is a convention: CLSKW is a warrant and BRK-B is not.

How a row is read, in order, and this order is the whole rule:

1. **The axis member, where the SEC's own taxonomy names it.** A row tagged
   `us-gaap:CommonStockMember` or `us-gaap:CommonClassAMember` is common stock
   because the taxonomy element means that and nothing else. The list below is
   closed and holds only members whose definition *is* common equity; it is
   never widened to a prefix or a pattern, because "starts with Common" would
   sweep in `CommonStockIncludingAdditionalPaidInCapitalMember`, which is a
   balance-sheet line and not a class of anything.
2. **Otherwise the title the filer wrote.** Roughly half of real rows use a
   filer-defined member — Alphabet's Class C is `goog:CapitalClassCMember`,
   Perrigo's ordinary shares are `prgo:OrdinaryShares0001ParValueMember` — so
   the member alone settles nothing for them and the title has to. Titles are
   free text, so this is the one heuristic here, and it is written to fail
   towards refusal: the *earliest* instrument word in the title decides, and
   anything the two lists below do not recognise is unknown rather than
   common.

   Earliest-match rather than "contains", because a security title names its
   instrument first and qualifies it afterwards. "Units, each consisting of
   one share of Class A common stock and one-half of one redeemable warrant"
   contains the words "common stock" and is a unit; "Common Stock, $.01 par
   value, and associated Preferred Share Purchase Rights" contains the words
   "preferred" and "rights" and is common stock. A rule reading either as a
   set of words gets one of those two wrong whichever way it is written.

**Where this fails.** Said plainly, because the honest failure of a heuristic
is part of what it is:

- A filing older than the cover-page tagging carries no table at all. Nothing
  is inferred from its absence: with one mapped symbol there was never a
  choice to get wrong, and with several the answer is a refusal.
- A title whose leading phrase neither list knows is unknown, and a company
  whose *only* common row is unknown loses its market capitalisation rather
  than gaining a guessed one. New instrument wording therefore costs coverage
  and never costs correctness, which is the direction it has to fail in.
- The table lists securities registered under section 12(b). A class quoted
  over the counter or on a foreign venue is not in it, so it comes back
  unknown — which is why an unclassified mapped symbol is reported as a
  caution rather than ignored.
- The symbols the filer writes here are the filer's own spelling. SYF-PA in
  the SEC's map is "SYFPrA" on Synchrony's cover, and the two do not resolve
  to each other. Only the *common* symbol is matched back to the map, where
  the spellings do agree, and non-common rows are used to rule symbols out by
  meaning rather than by name.

**Identity, not measurement, so the clock does not govern it.** What a symbol
denotes does not change with the day being evaluated, and the symbol list this
resolves over is already unclocked — the SEC publishes only the current
ticker-to-CIK association and keeps no history of it. Resolving from the
newest cover on record, and serving that resolution to a reconstruction of
2016, is therefore consistent with the list itself; the alternative refuses a
2016 reading because of a preferred series first issued in 2024, which is a
sentence about the wrong year. This is the same argument engine/industry.py
makes for the classification the SEC publishes, and it is made here for the
same reason: stating it beats assuming it.
"""

from __future__ import annotations

import re

from . import concept_map as cm
from . import price_store

# Members of the SEC's own class-of-stock axis whose definition is common
# equity. Closed, and short on purpose: a member that is not here falls to the
# title, and a title neither list knows refuses. Widening this table is the
# one edit that can turn a refusal into a wrong number, so it holds only
# elements that cannot mean anything but a class of common stock.
COMMON_MEMBERS = frozenset({
    "us-gaap:CommonStockMember",
    "us-gaap:CommonClassAMember",
    "us-gaap:CommonClassBMember",
    "us-gaap:CommonClassCMember",
    "us-gaap:CommonClassUndesignatedMember",
    "us-gaap:NonvotingCommonStockMember",
    "us-gaap:ConvertibleCommonStockMember",
})

# The instrument words a security title can lead with. Whichever list matches
# EARLIEST in the title decides; a title matching neither is unknown.
#
# Both lists are word-anchored. "right" as a substring would fire inside
# "copyright" and "unit" inside "united", and a security title is one place
# where a company name can appear.
_COMMON_WORDS = (
    r"common stock", r"common shares?", r"ordinary shares?",
    r"ordinary stock", r"capital stock", r"shares of beneficial interest",
    r"common shares of beneficial interest",
)
_NOT_COMMON_WORDS = (
    r"warrants?", r"rights?", r"units?", r"preferred", r"deposit[ao]ry",
    r"notes?", r"debentures?", r"bonds?", r"subordinated",
    r"capital securities", r"contingent value", r"subscriptions?",
    r"purchase contracts?", r"trust preferred",
)
_COMMON_RE = re.compile(r"\b(?:" + "|".join(_COMMON_WORDS) + r")\b")
_NOT_COMMON_RE = re.compile(r"\b(?:" + "|".join(_NOT_COMMON_WORDS) + r")\b")

COMMON, NOT_COMMON, UNKNOWN = "common", "not-common", "unknown"


def classify_title(title: str) -> str:
    """What instrument a security title names: COMMON, NOT_COMMON or UNKNOWN.

    Whichever list matches earliest wins, so the instrument the title leads
    with decides and the qualifiers after it do not. See the module docstring
    for why that is not the same rule as "contains".
    """
    text = re.sub(r"\s+", " ", str(title or "").replace("\xa0", " ")).lower()
    if not text:
        return UNKNOWN
    yes = _COMMON_RE.search(text)
    no = _NOT_COMMON_RE.search(text)
    if yes and (no is None or yes.start() < no.start()):
        return COMMON
    if no:
        return NOT_COMMON
    return UNKNOWN


def classify_row(row: dict) -> str:
    """One 12(b) row: the taxonomy member first, then the title."""
    if str(row.get("member") or "") in COMMON_MEMBERS:
        return COMMON
    return classify_title(row.get("title"))


def _same_symbol(a, b) -> bool:
    return str(b or "").upper() in price_store.symbol_forms(a)


class CompanySymbols:
    """A company's symbols with the common one picked out — or with a reason
    why it cannot be.

    This exists to be the *only* way a computation gets a symbol to price a
    whole-company figure at. `common` is one symbol or None; there is no list
    on it to take a newest close from, so the substitution this module was
    written to end cannot be reintroduced without first changing this class.
    """

    __slots__ = ("all", "common", "reason", "provenance", "unclassified")

    def __init__(self, all_symbols, common=None, reason=None,
                 provenance=None, unclassified=None):
        self.all = list(all_symbols)
        self.common = common
        self.reason = reason
        self.provenance = list(provenance or [])
        self.unclassified = list(unclassified or [])

    def __repr__(self):                                   # pragma: no cover
        return (f"CompanySymbols(all={self.all!r}, common={self.common!r}, "
                f"reason={self.reason!r})")

    def common_or_absent(self) -> dict:
        """The common symbol as a value, or an absence saying why not — the
        shape every other refusal in the engine has, so a caller cannot read
        past it by accident."""
        if self.common:
            return {"symbol": self.common}
        return {"absent": True,
                "reason": self.reason or "which of this company's symbols is "
                                         "its common stock is not established"}


def _cover_table(filings: list[dict]):
    """The newest cover-page 12(b) table on record, and the filing it came
    from — the current statement of what this filer registers.

    Newest wins because the table is a statement about what trades now: a
    class delisted last year is off the current cover and should be, and an
    older filing naming it would resurrect it.
    """
    dated = sorted((f for f in filings or []),
                   key=lambda f: (str(f.get("filed") or ""),
                                  str(f.get("accession") or "")),
                   reverse=True)
    for f in dated:
        rows = cm.FilingIndex(f).cover_securities()
        if rows:
            return rows, f
    return [], None


def company_symbols(filings: list[dict], tickers) -> CompanySymbols:
    """Resolve which mapped symbol is this filer's common stock.

    `tickers` is every symbol the SEC maps to the company; `filings` is what
    the raw facts store holds for it, in any order. The answer is one symbol
    or a refusal with a sentence, never a shortlist.
    """
    symbols = [str(t).upper() for t in (tickers or []) if t]
    rows, source = _cover_table(filings)
    where = (f"the cover of filing {source.get('accession')} "
             f"({source.get('form')}, filed {source.get('filed')})"
             if source else None)

    if not rows:
        if len(symbols) == 1:
            return CompanySymbols(
                symbols, common=symbols[0],
                provenance=[f"{symbols[0]} is the only symbol the SEC maps to "
                            "this filer, and no stored filing carries a "
                            "cover-page list of registered securities"])
        if not symbols:
            return CompanySymbols(
                symbols, reason="the SEC maps no symbol to this filer, so "
                                "there is no instrument to price it in")
        return CompanySymbols(
            symbols,
            reason=f"the SEC maps {len(symbols)} symbols to this filer "
                   f"({', '.join(symbols)}) and no stored filing says which "
                   "of them is the common stock — the cover-page list of "
                   "registered securities was phased in over 2019-2021, and "
                   "nothing on record here carries one",
            unclassified=symbols)

    verdicts = {}
    for row in rows:
        sym, verdict = row.get("symbol"), classify_row(row)
        for s in symbols:
            if _same_symbol(s, sym):
                # A symbol can appear on several rows — Microsoft tags its
                # listed notes with the symbol of its common stock — so one
                # row saying "common" settles it and later rows cannot
                # unsettle it.
                if verdicts.get(s) != COMMON:
                    verdicts[s] = verdict
    common = sorted(s for s, v in verdicts.items() if v == COMMON)

    def others(chosen):
        """The mapped symbols the cover leaves unaccounted for. Not the ones
        it names as something else — a preferred series the filer has told us
        about is a fact, not a doubt."""
        return [s for s in symbols if s != chosen and s not in verdicts]

    if len(common) == 1:
        return CompanySymbols(
            symbols, common=common[0],
            provenance=[f"{where} registers {common[0]} as common stock"],
            unclassified=others(common[0]))
    if len(common) > 1:
        return CompanySymbols(
            symbols,
            reason=f"{where} registers {len(common)} classes of common stock "
                   f"({', '.join(common)}), which trade at their own prices, "
                   "and the cover states one share count for the whole "
                   "company rather than a count for each — so there is no way "
                   "to price the count without assuming one class is the "
                   "other")
    if not verdicts and len(symbols) == 1:
        # The table exists and does not mention this symbol at all — a class
        # quoted somewhere section 12(b) does not reach. There is still only
        # one symbol, so nothing can be picked wrongly out of it.
        return CompanySymbols(
            symbols, common=symbols[0],
            provenance=[f"{symbols[0]} is the only symbol the SEC maps to "
                        f"this filer, and {where} does not list it"])
    if not verdicts:
        return CompanySymbols(
            symbols,
            reason=f"{where} lists no security trading under any of this "
                   f"filer's {len(symbols)} mapped symbols "
                   f"({', '.join(symbols)}), so nothing on record says which "
                   "of them is the common stock",
            unclassified=symbols)
    named = ", ".join(f"{s} ({verdicts[s]})" for s in sorted(verdicts))
    return CompanySymbols(
        symbols,
        reason=f"{where} registers none of this filer's symbols as common "
               f"stock — it classifies {named}. Market capitalisation is "
               "denominated in the common stock, and none of these is it",
        unclassified=others(None))
