"""Where a measure cannot be right, it is absent — and the arithmetic is what
performs that, not a sentence next to the number.

Every case here produced a confident figure in the flattering direction, each
one for a reason somebody had already written down:

  cash conversion        divided free cash flow by a loss. Two negatives make
                         a positive, so a company that lost money AND burned
                         cash read as converting its earnings perfectly.
  payout over FCF        divided a payout by negative free cash flow and
                         reported the negative. A company borrowing to fund
                         its dividend read as paying out less than it earns —
                         and a caution beside it said, in as many words, that
                         those years are uninterpretable.
  long-term debt         served a filer's us-gaap:LongTermDebt as the
                         noncurrent split, overstated by the current portion,
                         called conservative because it can only make a limit
                         harder to meet. True on the way in. Graham cites the
                         same measure on its exit, where a false fail sells.
  ROIC                   declared a gate against revenue and skipped it
                         whenever revenue could not be read — which is the
                         one class of filer the map says tags no revenue
                         total at all.
  free cash flow         added capital spending when a filer tagged it
                         negative, with a caution saying to check the filing.

Absence is the answer in every one, and the reason each is a test rather than
a paragraph is that none of them crashes. They come back as numbers a reader
has no way to doubt.
"""

import pytest
from conftest import balance_face, dur, filing, inst, no_filer, symbols

from engine import concept_map as cm
from engine.compute import compute_all

FY = [("2019-01-01", "2019-12-31"), ("2020-01-01", "2020-12-31"),
      ("2021-01-01", "2021-12-31"), ("2022-01-01", "2022-12-31"),
      ("2023-01-01", "2023-12-31")]


PRETAX = ("us-gaap:IncomeLossFromContinuingOperationsBeforeIncomeTaxes"
          "ExtraordinaryItemsNoncontrollingInterest")


def year(start, end, accession, *, revenue=1000.0, net_income=100.0,
         cfo=200.0, capex=50.0, dividends=None, buybacks=None,
         issuance=None, equity=800.0, debt=100.0, cash=50.0,
         operating_income=130.0, pretax=130.0, tax=30.0, extra=()):
    """One fiscal year of an invented company, filed as its own 10-K."""
    facts = [
        dur("us-gaap:Revenues", start, end, revenue),
        dur("us-gaap:NetIncomeLoss", start, end, net_income),
        dur("us-gaap:OperatingIncomeLoss", start, end, operating_income),
        dur(PRETAX, start, end, pretax),
        dur("us-gaap:IncomeTaxExpenseBenefit", start, end, tax),
        dur("us-gaap:NetCashProvidedByUsedInOperatingActivities", start, end,
            cfo, stmt="CashFlowStatement"),
        dur("us-gaap:PaymentsToAcquirePropertyPlantAndEquipment", start, end,
            capex, stmt="CashFlowStatement"),
    ]
    if dividends is not None:
        facts.append(dur("us-gaap:PaymentsOfDividendsCommonStock", start, end,
                         dividends, stmt="CashFlowStatement"))
    if buybacks is not None:
        facts.append(dur("us-gaap:PaymentsForRepurchaseOfCommonStock", start,
                         end, buybacks, stmt="CashFlowStatement"))
    if issuance is not None:
        facts.append(dur("us-gaap:ProceedsFromIssuanceOfCommonStock", start,
                         end, issuance, stmt="CashFlowStatement"))
    facts += balance_face(end, assets=2000.0, extra=[
        inst("us-gaap:StockholdersEquity", end, equity),
        inst("us-gaap:LongTermDebtNoncurrent", end, debt),
        inst("us-gaap:CashAndCashEquivalentsAtCarryingValue", end, cash),
    ] + list(extra))
    return filing(accession, "10-K", end[:4] + "-02-20", end, facts)


def five(**over):
    """Five filed fiscal years. `over` maps a year end to that year's kwargs."""
    per_year = over.pop("per_year", {})
    return [year(s, e, f"A-{i}", **{**over, **per_year.get(e, {})})
            for i, (s, e) in enumerate(FY)]


def entry(filings, eid):
    return compute_all(filings, None, symbols("SYN"), industry=no_filer(),
                       entry_ids=[eid])[eid]


# ---------------------------------------------------------------------------
# a ratio whose denominator is not a quantity
# ---------------------------------------------------------------------------

class TestCashConversionWillNotDivideByALoss:

    def test_five_ordinary_years_still_compute(self):
        """The control. Without it a refusal that fired on everything would
        look exactly like a refusal that fires on the right thing."""
        r = entry(five(), "cash_conversion_median_5y")
        assert r["status"] == "computed"
        assert r["value"] == pytest.approx(1.5)      # (200 − 50) ÷ 100

    def test_a_loss_year_refuses_rather_than_reading_as_a_conversion(self):
        """The case. Cash flow is negative too, so the ratio comes back
        POSITIVE and lands in the middle of the five — a perfect conversion
        read off the worst year the company has had."""
        r = entry(five(per_year={"2021-12-31": {"net_income": -100.0,
                                                "cfo": -50.0, "capex": 50.0}}),
                  "cash_conversion_median_5y")
        assert r["status"] == "absent"
        assert "net income in any year of the window is zero or negative" \
            in r["reason"]
        assert "2021-12-31" in r["reason"]

    def test_the_reason_is_the_banks_sentence_and_not_a_copy(self):
        from engine import bank
        r = entry(five(per_year={"2020-12-31": {"net_income": -10.0}}),
                  "cash_conversion_median_5y")
        assert bank.data_conditions()["cash_conversion_median_5y"][0] \
            in r["reason"]


class TestPayoutOverFreeCashFlowWillNotReportABorrowedDividend:

    def test_five_ordinary_years_still_compute(self):
        r = entry(five(dividends=30.0, buybacks=0.0, issuance=0.0),
                  "payout_to_fcf_median_5y")
        assert r["status"] == "computed"
        assert r["value"] == pytest.approx(20.0)     # 30 ÷ 150

    def test_a_year_that_burned_cash_refuses_rather_than_reading_low(self):
        """The case, and the direction is the whole point. Paying 30 out of
        −60 of free cash flow is −50%, which passes any "at most" limit a
        strategy can set — the company funding its dividend with borrowing
        reads as the most conservative payer in the journal."""
        r = entry(five(dividends=30.0, buybacks=0.0, issuance=0.0,
                       per_year={"2022-12-31": {"cfo": 40.0, "capex": 100.0}}),
                  "payout_to_fcf_median_5y")
        assert r["status"] == "absent"
        assert "free cash flow in any year of the window is zero or negative"\
            in r["reason"]
        assert "2022-12-31" in r["reason"]

    def test_the_condition_moved_out_of_the_reader_only_section(self):
        """It lived in `misfires` — the section describing what makes a
        reading noisy — and the formula cautioned rather than refused. A
        condition that decides whether a figure exists is not a thing to
        mention beside it, and the two sections are read by different halves
        of the program: one by a person, the other by nothing at all."""
        from engine import bank
        e = next(x for x in bank.load_bank()["entries"]
                 if x["id"] == "payout_to_fcf_median_5y")
        assert "uninterpretable" not in str(e["explanation"]["misfires"])
        assert any("free cash flow in any year" in str(i.get("data") or "")
                   for i in e["not_meaningful_when"])


# ---------------------------------------------------------------------------
# a gate that switched itself off
# ---------------------------------------------------------------------------

class TestROICWillNotComputeUngatedWhenItCannotBeGated:

    def test_an_ordinary_filer_still_computes(self):
        r = entry(five(), "roic_median_5y")
        assert r["status"] == "computed"

    def test_an_asset_light_denominator_is_refused(self):
        """The gate doing its job: invested capital of 30 against revenue of
        1000 is 3%, and the ratio explodes."""
        r = entry(five(equity=800.0, debt=100.0, cash=870.0),
                  "roic_median_5y")
        assert r["status"] == "absent"
        assert "under 10% of revenue" in r["reason"]

    def test_the_same_filer_with_no_revenue_is_refused_too(self):
        """The defect. Revenue is not in the formula, so it used to be read
        `if not is_absent(rev)` — and a filer tagging no revenue total got
        the ratio with the guard silently switched off. That filer is the
        asset-light one above with one fact removed, and it used to come back
        computed."""
        filings = five(equity=800.0, debt=100.0, cash=870.0)
        for f in filings:
            f["facts"] = [x for x in f["facts"]
                          if x["concept"] != "us-gaap:Revenues"]
        r = entry(filings, "roic_median_5y")
        assert r["status"] == "absent"
        assert "measured against revenue" in r["reason"]


# ---------------------------------------------------------------------------
# a figure that answers a wider question than the one asked
# ---------------------------------------------------------------------------

class TestLongTermDebtIsAbsentRatherThanOverstated:

    def _filing(self, *lines):
        d = "2023-12-31"
        return cm.FilingIndex(filing("L-1", "10-K", "2024-02-20", d,
                                     balance_face(d, extra=list(lines))))

    def test_the_split_is_read_where_the_filer_states_it(self):
        fi = self._filing(inst("us-gaap:LongTermDebtNoncurrent",
                               "2023-12-31", 3000))
        assert cm.resolve_instant(fi, "long_term_debt",
                                  "2023-12-31")["value"] == 3000

    def test_a_combined_line_is_not_served_as_the_split(self):
        """us-gaap:LongTermDebt usually includes the current maturities, so
        serving it here overstates by an unknown amount. Graham's exit reads
        this measure, and there a false fail is a sale."""
        fi = self._filing(inst("us-gaap:LongTermDebt", "2023-12-31", 5000,
                               label="Long-term debt"))
        assert cm.resolve_instant(fi, "long_term_debt", "2023-12-31") is None

    def test_and_it_is_absent_rather_than_a_completeness_zero(self):
        """What the fallback was actually protecting against. Zero would be a
        confident answer with the real figure in the same filing."""
        fi = self._filing(inst("us-gaap:LongTermDebt", "2023-12-31", 5000,
                               label="Long-term debt"))
        got = cm.resolve_instant(fi, "long_term_debt", "2023-12-31")
        assert got is None or got["value"] != 0


# ---------------------------------------------------------------------------
# a sign the map declared and nothing read
# ---------------------------------------------------------------------------

class TestAPaymentsLineTaggedNegativeIsRefused:

    def test_capex_tagged_the_usual_way_computes(self):
        r = entry(five(cfo=200.0, capex=50.0), "fcf_ttm")
        assert r["status"] == "computed"
        assert r["value"] == pytest.approx(150.0)

    def test_capex_tagged_negative_makes_free_cash_flow_absent(self):
        """`cfo - capex` ADDED the spending: 200 − (−50) = 250 against a true
        150. The caution beside it said to check the filing, and
        fcf_margin_ttm carried the number onto an exit rule regardless."""
        r = entry(five(cfo=200.0, capex=-50.0), "fcf_ttm")
        assert r["status"] == "absent"
        assert r.get("value") is None

    def test_it_is_refused_where_the_sign_is_declared_not_where_it_bit(self):
        """Free cash flow was one consumer. The payout ratio divides by two
        more of these lines, and a check inside one formula is a check the
        others do not have."""
        d, s = "2023-12-31", "2023-01-01"
        fi = cm.FilingIndex(filing("N-1", "10-K", "2024-02-20", d, [
            dur("us-gaap:PaymentsOfDividendsCommonStock", s, d, -40.0,
                stmt="CashFlowStatement")]))
        r = cm.resolve_duration(fi, "dividends_paid", s, d)
        assert cm.is_absent(r)
        assert "value" not in r

    def test_the_refusal_says_it_was_the_sign_and_not_a_missing_line(self):
        """The absence that could not say why.

        Every way a resolution could fail came back as None, so the sentence
        a reader finally saw was assembled from the only fact left — that
        nothing arrived. "Capital expenditure did not resolve in the newest
        annual report" is true of a filer that tags no such caption, and it
        is what was shown for a filer whose caption is right there tagged
        negative. The reader was sent to look for a line that is in the
        filing, and the two point at completely different things: one is a
        gap in the data, the other is this program refusing a number it
        cannot interpret.
        """
        d, s = "2023-12-31", "2023-01-01"
        fi = cm.FilingIndex(filing("N-2", "10-K", "2024-02-20", d, [
            dur("us-gaap:PaymentsToAcquirePropertyPlantAndEquipment", s, d,
                -50.0, stmt="CashFlowStatement")]))
        r = cm.resolve_duration(fi, "capex", s, d)
        assert cm.is_absent(r)
        why = r["reason"]
        assert "-50" in why                     # the figure that is there
        assert "payments line" in why           # the convention that fired
        assert "opposite convention or a real reversal" in why
        assert "did not resolve" not in why

    def test_a_line_that_is_genuinely_missing_says_that_instead(self):
        """The other half, so the sentence above is not simply what every
        absence now says."""
        d, s = "2023-12-31", "2023-01-01"
        fi = cm.FilingIndex(filing("N-3", "10-K", "2024-02-20", d, [
            dur("us-gaap:Revenues", s, d, 1000.0)]))
        r = cm.resolve_duration(fi, "capex", s, d)
        assert cm.is_absent(r)
        assert "no concept this program maps to" in r["reason"]
        assert "payments line" not in r["reason"]

    def test_the_reason_reaches_the_measure_a_reader_is_looking_at(self):
        """The whole point of the channel. It has to survive the trip from
        the resolver, through period assembly, to the sentence on the entry
        the reader clicked — otherwise it is a better message nobody sees."""
        r = entry(five(cfo=200.0, capex=-50.0), "fcf_ttm")
        assert r["status"] == "absent"
        assert "payments line" in r["reason"]
        assert "-50" in r["reason"]

    def test_a_sign_convention_the_host_cannot_perform_refuses_the_map(self):
        """`sign` sat in the map unread for as long as it existed. A word
        nothing enforces is what this check exists to stop being."""
        import copy
        doc = copy.deepcopy(cm.load_map())
        doc["inputs"]["capex"]["sign"] = "inflow_positive"
        cm._cache["doc"] = doc
        try:
            assert cm.load_map()["inputs"]["capex"]["sign"] == \
                "inflow_positive"
        finally:
            cm._cache.pop("mtime", None)
            cm.load_map()
        assert cm.load_map()["inputs"]["capex"]["sign"] == "outflow_positive"


# ---------------------------------------------------------------------------
# a ratio whose NUMERATOR is not a quantity
# ---------------------------------------------------------------------------

class TestEVOverEBITWillNotDivideANegativePrice:
    """Only the denominator was guarded.

    Enterprise value is market cap plus debt minus cash, so a company holding
    more cash than its shares and its borrowings are worth together prices at
    less than nothing. Dividing that by a real profit gives a negative
    multiple, which sorts below every genuine reading on a measure where lower
    is better — the worst case reading as the best bargain, which is the same
    fault the EBIT guard beside it was written for, arriving through the other
    end of the ratio.

    It compounds one level up, and that is what made it worth a refusal rather
    than a caution: `ev_ebit_to_own_5y_median` divides the current multiple by
    the median of twenty quarterly ones, and two negatives make a positive. A
    company whose enterprise value moved from −10× profit to −7× — the price
    going UP — came back at 0.70×, under a sentence saying it sits 30% below
    its own normal.
    """

    def _priced(self, close, shares=100.0):
        from engine import price_store
        doc = price_store.load(9101)
        price_store.merge_series(doc, "SYN", "test",
                                 [["2023-12-29", close, 1000]], [])
        return doc

    def _filings(self, cash):
        """Five ordinary years, the last one holding `cash` on its face and
        naming a cover share count so a market cap can be struck."""
        out = five(per_year={"2023-12-31": {"cash": cash}})
        out[-1]["facts"].append(
            {**inst("dei:EntityCommonStockSharesOutstanding", "2024-02-20",
                    100.0, stmt=None), "unit": "shares", "currency": None})
        return out

    def _entry(self, filings, prices, eid):
        return compute_all(filings, prices, symbols("SYN"),
                           industry=no_filer(), entry_ids=[eid])[eid]

    def test_an_ordinary_enterprise_value_still_computes(self):
        """The control. A refusal that fired on everything would look exactly
        like one that fires on the right thing."""
        r = self._entry(self._filings(cash=50.0), self._priced(10.0),
                        "ev_to_ebit")
        assert r["status"] == "computed"
        # 100 shares × $10 = 1,000 market cap, + 100 debt − 50 cash = 1,050,
        # over EBIT of 130.
        assert r["value"] == pytest.approx(1050.0 / 130.0)

    def test_more_cash_than_the_company_is_worth_refuses(self):
        """Market cap 1,000 + debt 100 − cash 3,000 = −1,900. Positive EBIT
        of 130 underneath, so nothing else in the formula objects: without
        the guard this returns −14.6× and reads as the cheapest company on
        the screen."""
        r = self._entry(self._filings(cash=3000.0), self._priced(10.0),
                        "ev_to_ebit")
        assert r["status"] == "absent"
        assert r.get("value") is None
        assert "enterprise value is zero or negative" in r["reason"]

    def test_the_reason_is_the_banks_sentence_and_not_a_copy(self):
        from engine import bank
        r = self._entry(self._filings(cash=3000.0), self._priced(10.0),
                        "ev_to_ebit")
        assert "enterprise value is zero or negative" in \
            bank.data_conditions()["ev_to_ebit"]
        assert "-1,900" in r["reason"]

    def test_the_median_relative_measure_refuses_with_it(self):
        """The consumer, and the reason the guard is here rather than in the
        view. It cites ev_to_ebit's own refusal rather than restating it, so
        the whole chain is readable from the one sentence: this measure needs
        a current value, the current value is not meaningful, and the figure
        that made it not meaningful is −1,900.

        Asserted on the CAUSE and not only on the status. Absent for the
        wrong reason is what this test would otherwise report as a pass —
        without the guard the current period computes, the twenty-quarter
        window fails to assemble, and the measure is absent anyway."""
        r = self._entry(self._filings(cash=3000.0), self._priced(10.0),
                        "ev_ebit_to_own_5y_median")
        assert r["status"] == "absent"
        assert r.get("value") is None
        assert "EV/EBIT is not meaningful in the current period" in r["reason"]
        assert "enterprise value is zero or negative" in r["reason"]
        assert "-1,900" in r["reason"]
