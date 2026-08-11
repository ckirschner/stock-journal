"""What a whole-company figure is priced in, and what it refuses.

The defect these pin was fixed once for positions and stayed alive for
measures: a share count multiplied by whichever symbol the SEC maps to the
filer had closed most recently. On Synchrony Financial that list is SYF,
SYF-PA and SYF-PB; on an ordinary post-SPAC company it is the share, the unit
and the warrant. The wrong one produces a dollar figure, and a dollar figure
is plausible in shape whatever its value, so nothing downstream can notice.

Two kinds of evidence here and they are not interchangeable:

- **Real filings.** The cover-page classifications are checked against
  tests/fixtures/extracted, which is what the pipeline saw for filings a
  person has read. Realty Income registers a common stock and eleven listed
  notes; Alphabet registers a Class C whose title never says "common"; Perrigo
  registers ordinary shares under a member the SEC's taxonomy does not define.
  Each of those breaks a different plausible shortcut, which is why they are
  the cases and not invented ones.
- **Invented companies**, for arrangements no fixture happens to contain — a
  warrant that closes after its share, a filer whose only listed security is a
  preferred series. Those are synthetic on purpose: nothing here is a claim
  about a real company beyond what its own filing says.
"""

import gzip
import json
from pathlib import Path

import pytest
from conftest import balance_face, filing, inst, no_filer, symbols

from engine import compute, crosscheck, instruments, price_store
from engine.instruments import COMMON, NOT_COMMON, UNKNOWN

FIX = Path(__file__).parent / "fixtures" / "extracted"
M = 1e6


def load_filing(cik, accession):
    p = FIX / f"CIK{cik:010d}" / f"{accession}.json.gz"
    if not p.exists():
        pytest.skip(f"recorded extraction missing: {p.name}")
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return json.load(f)


def all_filings(cik):
    d = FIX / f"CIK{cik:010d}"
    if not d.exists():
        pytest.skip(f"recorded extractions missing: {d.name}")
    out = []
    for p in sorted(d.glob("*.json.gz")):
        with gzip.open(p, "rt", encoding="utf-8") as f:
            out.append(json.load(f))
    return out


# -- the cover page, against real filings ------------------------------------

class TestTheFilerSaysWhatItsSymbolsAre:
    """The section 12(b) table, read off filings a person has checked.

    Every row below is transcribed from the recorded extraction, and the
    titles are the filers' own wording. They are the evidence that this is a
    published statement rather than a pattern in a symbol.
    """

    def test_realty_income_registers_one_common_stock_and_eleven_notes(self):
        """The case the defect is worst on: twelve NYSE-listed securities
        against one CIK, eleven of them bonds, and one cover share count for
        the whole company."""
        filings = all_filings(726728)
        rows = {r["symbol"]: r
                for r in instruments._cover_table(filings)[0]}
        assert rows["O"]["title"] == "Common Stock, $0.01 Par Value"
        assert instruments.classify_row(rows["O"]) == COMMON
        notes = [s for s in rows if s != "O"]
        assert len(notes) == 11
        for s in notes:
            assert instruments.classify_row(rows[s]) == NOT_COMMON, s

    def test_alphabets_class_c_is_common_and_its_title_never_says_so(self):
        """"Class C Capital Stock, $0.001 par value". A rule looking for the
        word "common" misses it; a rule reading the taxonomy member misses it
        too, because goog:CapitalClassCMember is Alphabet's own."""
        rows = {r["symbol"]: r
                for r in instruments._cover_table(all_filings(1652044))[0]}
        assert rows["GOOG"]["title"] == "Class C Capital Stock, $0.001 par value"
        assert rows["GOOG"]["member"] == "goog:CapitalClassCMember"
        assert instruments.classify_row(rows["GOOG"]) == COMMON
        assert instruments.classify_row(rows["GOOGL"]) == COMMON

    def test_perrigo_files_ordinary_shares_under_its_own_member(self):
        """An Irish issuer: no "common", and prgo:OrdinaryShares...Member is
        not in any taxonomy this host can consult. The title carries it."""
        rows = {r["symbol"]: r
                for r in instruments._cover_table(all_filings(1585364))[0]}
        assert rows["PRGO"]["title"] == "Ordinary shares, €0.001 par value"
        assert not rows["PRGO"]["member"].startswith("us-gaap:")
        assert instruments.classify_row(rows["PRGO"]) == COMMON

    def test_one_symbol_on_several_rows_is_settled_by_the_common_one(self):
        """Microsoft tags its two listed note series with the trading symbol
        of its common stock. Read row by row, MSFT is a note on two rows out
        of three; one row saying common has to settle it."""
        filings = all_filings(789019)
        rows = instruments._cover_table(filings)[0]
        assert [r["symbol"] for r in rows] == ["MSFT", "MSFT", "MSFT"]
        assert sorted(instruments.classify_row(r) for r in rows) == \
            [COMMON, NOT_COMMON, NOT_COMMON]
        assert instruments.company_symbols(filings, ["MSFT"]).common == "MSFT"

    def test_a_filing_older_than_the_tagging_carries_no_table(self):
        """Cover-page XBRL was phased in over 2019-2021. Absence of the table
        is "the filer did not say", and nothing may be read into it."""
        old = compute.cm.FilingIndex(
            load_filing(27419, "0000027419-17-000008"))
        assert old.cover_securities() == []

    def test_target_tags_one_security_with_no_axis_at_all(self):
        """A filer with a single registered security needs no axis to say
        which security a title belongs to, and its row is a row."""
        rows = instruments._cover_table(all_filings(27419))[0]
        assert len(rows) == 1
        assert rows[0]["member"] is None
        assert rows[0]["symbol"] == "TGT"
        assert instruments.classify_row(rows[0]) == COMMON

    def test_two_undimensioned_securities_have_nothing_joining_them(self):
        """A title and a symbol with no axis between them are one security's
        only while there is one of each. Assembling a row out of two would
        name one instrument and price another."""
        f = filing("X", "10-Q", "2026-02-01", "2026-02-01", [
            {"concept": c, "value": v, "instant": "2026-02-01", "start": None,
             "end": None, "dimensions": None, "statement_type": None,
             "unit": None, "currency": None, "decimals": None, "label": None}
            for c, v in (("dei:Security12bTitle", "Common Stock"),
                         ("dei:TradingSymbol", "ACME"),
                         ("dei:Security12bTitle", "Warrants"),
                         ("dei:TradingSymbol", "ACMEW"))])
        assert compute.cm.FilingIndex(f).cover_securities() == []

    def test_alphabets_2017_trading_symbol_is_not_a_symbol(self):
        """dei:TradingSymbol undimensioned, tagged as the single string
        "GOOG, GOOGL". Read as one symbol it invents an instrument, which is
        why only a row carrying a Security12bTitle counts as a row."""
        old = compute.cm.FilingIndex(
            load_filing(1652044, "0001652044-18-000007"))
        assert old.cover_securities() == []


class TestTitlesAreReadFrontToBack:
    """Earliest instrument word wins. Both directions of the alternative are
    wrong on a real title, so "contains" cannot be the rule either way."""

    @pytest.mark.parametrize("title,want", [
        # A SPAC unit names the common stock it contains. It is not one.
        ("Units, each consisting of one share of Class A common stock and "
         "one-half of one redeemable warrant", NOT_COMMON),
        ("Redeemable warrants, each whole warrant exercisable for one share "
         "of Class A common stock at an exercise price of $11.50", NOT_COMMON),
        # Common stock names the rights attached to it. It is still common.
        ("Common Stock, $.01 par value per share, and associated Preferred "
         "Share Purchase Rights", COMMON),
        ("Class A Common Stock, par value $0.0001 per share", COMMON),
        ("Depositary Shares Each Representing a 1/40th Interest in a Share "
         "of 5.625% Fixed-Rate Reset Non-Cumulative Perpetual Preferred "
         "Stock, Series A", NOT_COMMON),
        ("6.25% Series B Cumulative Redeemable Preferred Stock", NOT_COMMON),
        ("1.125% Notes due 2027", NOT_COMMON),
        ("Common Shares of Beneficial Interest, $0.01 par value", COMMON),
        ("Ordinary shares, €0.001 par value", COMMON),
        # Nothing either list knows. Unknown is not common, and a company
        # whose only candidate is unknown loses the figure rather than
        # gaining a guessed one.
        ("Perpetual Trust Certificates, Series 2029", UNKNOWN),
        ("", UNKNOWN),
    ])
    def test_title(self, title, want):
        assert instruments.classify_title(title) == want


# -- resolution --------------------------------------------------------------

def cover(*rows, accession="C-1", form="10-Q", filed="2026-02-01"):
    """A filing carrying only a cover-page 12(b) table."""
    facts = []
    for member, symbol, title in rows:
        for concept, value in (("dei:Security12bTitle", title),
                               ("dei:TradingSymbol", symbol),
                               ("dei:SecurityExchangeName", "NYSE")):
            facts.append({"concept": concept, "value": value,
                          "instant": filed, "start": None, "end": None,
                          "dimensions":
                              {"us-gaap:StatementClassOfStockAxis": member},
                          "statement_type": None, "unit": None,
                          "currency": None, "decimals": None, "label": None})
    return filing(accession, form, filed, filed, facts)


class TestResolvingTheCommonSymbol:
    def test_the_cover_picks_the_share_out_of_a_share_unit_and_warrant(self):
        """The arrangement an ordinary post-SPAC company is in. NEWCO trades
        beside NEWCOU and NEWCOW, and only one of them is what a share count
        is denominated in."""
        f = cover(("us-gaap:CommonClassAMember", "NEWCO",
                   "Class A common stock, par value $0.0001 per share"),
                  ("newco:UnitsMember", "NEWCOU",
                   "Units, each consisting of one share of Class A common "
                   "stock and one-half of one redeemable warrant"),
                  ("us-gaap:WarrantMember", "NEWCOW",
                   "Redeemable warrants, each exercisable for one share"))
        got = instruments.company_symbols([f], ["NEWCO", "NEWCOU", "NEWCOW"])
        assert got.common == "NEWCO"
        assert got.unclassified == []
        assert "registers NEWCO as common stock" in got.provenance[0]

    def test_one_symbol_and_no_cover_page_has_nothing_to_choose_from(self):
        got = instruments.company_symbols([], ["SYN"])
        assert got.common == "SYN"
        assert "only symbol" in got.provenance[0]

    def test_several_symbols_and_no_cover_page_refuses(self):
        got = instruments.company_symbols([], ["SYN", "SYNW"])
        assert got.common is None
        assert "no stored filing says which of them is the common stock" \
            in got.reason

    def test_two_classes_of_common_and_one_total_count_refuses(self):
        """Two classes at their own prices and no count for each. Valuing the
        whole count at either one is an assumption whose size nobody can
        state — unlike the per-class blend, which knows what share of the
        company it assumed and says so."""
        f = cover(("us-gaap:CommonClassAMember", "DUAL-A",
                   "Class A Common Stock"),
                  ("us-gaap:CommonClassBMember", "DUAL-B",
                   "Class B Common Stock"))
        got = instruments.company_symbols([f], ["DUAL-A", "DUAL-B"])
        assert got.common is None
        assert "2 classes of common stock" in got.reason

    def test_a_filer_whose_only_listed_security_is_preferred_refuses(self):
        """Cedar Realty is in this position: the common was taken private and
        two preferred series still trade. Its shares outstanding are real and
        there is no share price anywhere — which is an absence, not a
        preferred price."""
        f = cover(("us-gaap:SeriesBPreferredStockMember", "GONE-PB",
                   "7.25% Series B Cumulative Redeemable Preferred Stock"),
                  ("us-gaap:SeriesCPreferredStockMember", "GONE-PC",
                   "6.50% Series C Cumulative Redeemable Preferred Stock"))
        got = instruments.company_symbols([f], ["GONE-PB", "GONE-PC"])
        assert got.common is None
        assert "none of this filer's symbols as common stock" in got.reason

    def test_the_newest_cover_is_the_one_that_counts(self):
        """A class delisted last year is off the current cover, and an older
        filing naming it must not resurrect it."""
        old = cover(("us-gaap:CommonClassAMember", "OLD", "Common Stock"),
                    accession="OLD", filed="2021-02-01")
        new = cover(("us-gaap:CommonStockMember", "NEW", "Common Stock"),
                    accession="NEW", filed="2026-02-01")
        got = instruments.company_symbols([old, new], ["OLD", "NEW"])
        assert got.common == "NEW"

    def test_the_symbol_is_matched_through_its_punctuation(self):
        f = cover(("us-gaap:CommonClassBMember", "BRK.B",
                   "Class B Common Stock"))
        assert instruments.company_symbols([f], ["BRK-B"]).common == "BRK-B"

    def test_a_symbol_the_cover_never_mentions_is_unclassified(self):
        """Section 12(b) does not reach an over-the-counter line, so its
        absence from the table is not evidence about what it is."""
        f = cover(("us-gaap:CommonStockMember", "ACME", "Common Stock"))
        got = instruments.company_symbols([f], ["ACME", "ACMEF"])
        assert got.common == "ACME"
        assert got.unclassified == ["ACMEF"]


# -- what the measures do with it --------------------------------------------

def _company(shares, *, symbol_rows=(), end="2025-12-31"):
    facts = balance_face(end) + [
        {**inst("dei:EntityCommonStockSharesOutstanding", "2026-01-31",
                shares, stmt=None), "unit": "shares", "currency": None},
    ]
    out = [filing("K1", "10-K", "2026-02-20", end, facts)]
    if symbol_rows:
        out.append(cover(*symbol_rows, accession="C-1", filed="2026-02-20"))
    return out


def _prices(cik, *rows):
    doc = price_store.load(cik)
    for sym, date, close in rows:
        price_store.merge_series(doc, sym, "test", [[date, close, 100]], [])
    return doc


class TestMarketCapIsDenominatedInTheCommonStock:
    ROWS = (("us-gaap:CommonStockMember", "ACME",
             "Common Stock, $0.01 par value"),
            ("us-gaap:WarrantMember", "ACMEW",
             "Warrants, each exercisable for one share of common stock"))

    def _ctx(self, prices, tickers, filings):
        return compute.Ctx(
            filings, prices,
            instruments.company_symbols(filings, tickers),
            today="2026-03-02", industry=no_filer())

    def test_a_warrant_closing_later_does_not_set_the_market_cap(self):
        """The defect, exactly. The warrant closes a day after the share, so
        the rule that kept the newest close valued 100 million shares at
        $1.10 — a $110 million company that is worth $2.0 billion — and said
        nothing about it."""
        filings = _company(100 * M, symbol_rows=self.ROWS)
        prices = _prices(401, ("ACME", "2026-02-27", 20.0),
                         ("ACMEW", "2026-02-28", 1.10))
        ctx = self._ctx(prices, ["ACME", "ACMEW"], filings)
        r = ctx.entry("market_cap")
        assert r["status"] == "computed"
        assert r["value"] == 2000 * M
        assert any("ACME: 100,000,000 shares × 20.00" in p
                   for p in r["provenance"])
        assert not any("ACMEW" in c for c in r["cautions"])

    def test_the_share_having_no_close_is_an_absence_not_the_warrants(self):
        """The other half of the same guarantee. With no close for the common
        stock there is no market capitalization, and borrowing the one
        instrument that does have a close is the error, not the fallback."""
        filings = _company(100 * M, symbol_rows=self.ROWS)
        prices = _prices(402, ("ACMEW", "2026-02-28", 1.10))
        r = self._ctx(prices, ["ACME", "ACMEW"], filings).entry("market_cap")
        assert r["status"] == "absent"
        assert "ACME" in r["reason"]

    def test_an_unidentifiable_company_refuses_rather_than_guessing(self):
        filings = _company(100 * M)          # no cover-page table at all
        prices = _prices(403, ("ACME", "2026-02-27", 20.0),
                         ("ACMEW", "2026-02-28", 1.10))
        r = self._ctx(prices, ["ACME", "ACMEW"], filings).entry("market_cap")
        assert r["status"] == "absent"
        assert "which of them is the common stock" in r["reason"]

    def test_everything_built_on_market_cap_refuses_with_it(self):
        """Enterprise value, both yields and dividend yield read market cap.
        A refusal that leaked a number into any of them would be the same
        wrong answer wearing a different label."""
        filings = _company(100 * M)
        prices = _prices(404, ("ACME", "2026-02-27", 20.0),
                         ("ACMEW", "2026-02-28", 1.10))
        ctx = self._ctx(prices, ["ACME", "ACMEW"], filings)
        for eid in ("enterprise_value", "price_to_book", "dividend_yield",
                    "pe_ttm", "pe_3y_avg_eps", "ncav_to_market_cap"):
            assert ctx.entry(eid)["status"] != "computed", eid

    def test_a_price_alone_never_reaches_a_per_share_valuation(self):
        """P/E used to take the newest close over EPS, with no share count
        involved, so a warrant priced it too — and it could disagree with the
        market cap beside it about which instrument the company trades as."""
        filings = _company(100 * M, symbol_rows=self.ROWS)
        prices = _prices(405, ("ACME", "2026-02-27", 20.0),
                         ("ACMEW", "2026-02-28", 1.10))
        ctx = self._ctx(prices, ["ACME", "ACMEW"], filings)
        per_share = compute._price_per_common_share(ctx)
        assert per_share["status"] == "computed"
        assert per_share["value"] == 20.0

    def test_an_unidentified_symbol_that_trades_is_said_out_loud(self):
        """A preferred series the filer registers is a fact and stays quiet.
        Something trading against this filer that no cover page accounts for
        is a doubt, and it is the only one worth a caution: if it is another
        class of common, the count priced here covers shares this price does
        not describe."""
        filings = _company(100 * M, symbol_rows=(
            ("us-gaap:CommonStockMember", "ACME", "Common Stock"),))
        prices = _prices(406, ("ACME", "2026-02-27", 20.0),
                         ("ACMEF", "2026-02-27", 19.0))
        r = self._ctx(prices, ["ACME", "ACMEF"], filings).entry("market_cap")
        assert r["status"] == "computed"
        assert any("ACMEF also trade against this filer" in c
                   for c in r["cautions"])

    def test_a_registered_preferred_series_is_not_reported_as_a_doubt(self):
        filings = _company(100 * M, symbol_rows=(
            ("us-gaap:CommonStockMember", "ACME", "Common Stock"),
            ("us-gaap:SeriesAPreferredStockMember", "ACME-PA",
             "6.00% Series A Cumulative Preferred Stock")))
        prices = _prices(407, ("ACME", "2026-02-27", 20.0),
                         ("ACME-PA", "2026-02-27", 25.0))
        r = self._ctx(prices, ["ACME", "ACME-PA"], filings).entry("market_cap")
        assert r["status"] == "computed"
        assert r["value"] == 2000 * M
        assert not any("also trade against" in c for c in r["cautions"])

    def test_a_dead_warrant_series_is_not_a_caution_about_the_share(self):
        """`_ended_series` used to walk every symbol mapped to the filer, so
        a warrant that stopped trading printed a warning on a figure it had
        nothing to do with."""
        filings = _company(100 * M, symbol_rows=self.ROWS)
        prices = _prices(408, ("ACME", "2026-02-27", 20.0),
                         ("ACMEW", "2025-06-30", 1.10))
        prices["series"]["ACMEW"]["terminal"] = {"reason": "warrants expired"}
        r = self._ctx(prices, ["ACME", "ACMEW"], filings).entry("market_cap")
        assert r["status"] == "computed"
        assert not any("ACMEW" in c for c in r["cautions"])


class TestTheCoverCountIsLookedForEverywhere:
    """Found while wiring the above, and its own defect.

    "Newest filing" means newest *reporting period*; the stored filings are
    ordered by *filed date*. The fallback that looks for a cover share count
    in earlier filings dropped the last of the second ordering and walked the
    rest, so wherever the two disagree it skipped a filing it had never tried
    and retried one that had already refused. The result is an absent market
    capitalization — and an absent enterprise value, P/E and every yield —
    for a company whose share count is in the store.
    """

    def _ctx(self, filings):
        return compute.Ctx(filings, None, symbols("ACME"),
                           today="2026-03-02", industry=no_filer())

    def test_two_filings_on_one_day_and_only_one_carries_the_count(self):
        """A cover-page-only companion sorts after the 10-K by filed date and
        before it by period, which is the disagreement in its simplest form."""
        filings = _company(100 * M, symbol_rows=(
            ("us-gaap:CommonStockMember", "ACME", "Common Stock"),))
        assert len(filings) == 2
        got = compute._cover_shares(self._ctx(filings))
        assert got["total"] == 100 * M
        assert got["accession"] == "K1"

    def test_a_late_amendment_is_searched_and_not_stepped_over(self):
        """The newest *period* is a 10-Q that omits the cover fact; the count
        is in an amendment of an older period, filed after it. Filed last, so
        it was the one filing the old walk never looked in — and it was the
        only one that could answer.
        """
        recent = filing("Q3", "10-Q", "2026-11-05", "2026-09-30",
                        balance_face("2026-09-30"))
        amended = filing("Q1A", "10-Q/A", "2026-12-01", "2026-03-31",
                         balance_face("2026-03-31") + [
                             {**inst("dei:EntityCommonStockSharesOutstanding",
                                     "2026-04-30", 100 * M, stmt=None),
                              "unit": "shares", "currency": None}])
        got = compute._cover_shares(self._ctx([recent, amended]))
        assert got["total"] == 100 * M
        assert got["accession"] == "Q1A"


class TestTheContextRefusesAList:
    def test_a_bare_ticker_list_cannot_build_a_context(self):
        """The signature is the guarantee, the same way price_view's is: with
        no list to take a newest close from, the substitution cannot come
        back without changing this line first."""
        with pytest.raises(TypeError) as e:
            compute.Ctx([], None, ["ACME", "ACMEW"], industry=no_filer())
        assert "CompanySymbols" in str(e.value)

    def test_a_price_reader_cannot_be_handed_several_symbols(self):
        ctx = compute.Ctx([], None, symbols("ACME"), industry=no_filer())
        for call in (lambda: ctx.price_for(["ACME", "ACMEW"]),
                     lambda: ctx.price_on(["ACME"], "2026-01-01")):
            with pytest.raises(TypeError):
                call()

    def test_nothing_offers_a_newest_close_across_the_company(self):
        ctx = compute.Ctx([], None, symbols("ACME"), industry=no_filer())
        assert not hasattr(ctx, "price_now")


class TestTheCrossCheckPricesTheSameThing:
    """The public-float check exists to catch a wrong price basis. It had
    one: where the cover stated a single total it priced it at the first of
    the company's symbols with a close near the date, in alphabetical order.
    """

    def _filings(self, float_usd, shares, rows=()):
        end = "2023-12-31"
        facts = balance_face(end) + [
            {**inst("dei:EntityPublicFloat", "2023-06-30", float_usd,
                    stmt=None), "currency": "USD"},
            {**inst("dei:EntityCommonStockSharesOutstanding", "2024-01-25",
                    shares, stmt=None), "unit": "shares", "currency": None},
        ]
        out = [filing("K1", "10-K", "2024-02-20", end, facts)]
        if rows:
            out.append(cover(*rows, accession="C-1", filed="2024-02-20"))
        return out

    def test_it_prices_the_common_stock_and_not_the_warrant(self):
        rows = (("us-gaap:CommonStockMember", "ACME", "Common Stock"),
                ("us-gaap:WarrantMember", "ACMEW", "Warrants"))
        filings = self._filings(9.0e9, 1.0e9, rows)
        prices = _prices(409, ("ACME", "2023-06-30", 10.0),
                         ("ACMEW", "2023-06-30", 1.0))
        out = crosscheck.run(
            filings, prices,
            instruments.company_symbols(filings, ["ACME", "ACMEW"]))
        row = out["checks"][0]
        assert row["status"] == "pass"
        assert row["market_cap"] == 10.0e9

    def test_it_skips_rather_than_checking_the_wrong_instrument(self):
        filings = self._filings(9.0e9, 1.0e9)     # no cover-page table
        prices = _prices(410, ("ACME", "2023-06-30", 10.0),
                         ("ACMEW", "2023-06-30", 1.0))
        out = crosscheck.run(
            filings, prices,
            instruments.company_symbols(filings, ["ACME", "ACMEW"]))
        row = out["checks"][0]
        assert row["status"] == "skipped"
        assert "common stock" in row["note"]
