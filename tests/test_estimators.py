"""Averaged endpoints, and confirmation keyed to the estimator.

Two structural changes with one thing in common: both replace a rule that
looked rigorous with one that measures what it claims to.

**Averaged endpoints.** A compound rate between two single years describes
whatever one-off sat in either of them. The dangerous case is not the company
that fails high and gets rejected — it is the one that fails *mid-band*: a
true 7% grower whose base year carried a charge reads about 20%, passes every
plausible test, and nothing anywhere says so. That case is pinned below, and
it is the reason for the whole change.

**Confirmation keyed to the estimator.** Two consecutive readings of a rolling
five-year window share four of five years. Demanding several of them
accumulates one piece of evidence and several years, and the year that
produced the breach does not leave the window by being looked at again. Where
that is true the host asks a different question instead — does the failure
survive dropping the year that most favours the company — and where it is not
true, confirmation still counts filings.

On why the arithmetic here is checked against synthetic filings rather than
hand-read ones: what an averaged rate should be, given eight annual figures,
is the definition of the measure and not a fact about any company. The
expected values below are worked out from that definition, never through the
code path under test. Extraction from real filings — which IS a fact about a
company — is pinned against hand-read primary documents elsewhere, in
tests/fixtures/groundtruth.
"""

import pytest
from conftest import dur, filing, no_filer, symbols

from engine import bank, compute, contract
from engine.compute import compute_all


# ---------------------------------------------------------------------------
# builders
# ---------------------------------------------------------------------------

def years(series, concept="us-gaap:Revenues", extra=None):
    """A 10-K per fiscal year carrying that year's figure.

    `series` is {year: value}; `extra` is {year: [more facts]}. One filing per
    year, each filed the following February, which is what makes the eight
    annual observations tile and sit on one vintage.
    """
    out = []
    for y, v in sorted(series.items()):
        facts = [dur(concept, f"{y}-01-01", f"{y}-12-31", v)]
        facts.extend((extra or {}).get(y, []))
        out.append(filing(f"F-{y}", "10-K", f"{y + 1}-02-15",
                          f"{y}-12-31", facts))
    return out


def with_income(revenue, net_income):
    """Filings carrying both revenue and net income for the same years."""
    return years(revenue, extra={
        y: [dur("us-gaap:NetIncomeLoss", f"{y}-01-01", f"{y}-12-31", v)]
        for y, v in net_income.items()})


def one(filings, entry_id):
    return compute_all(filings, None, symbols("SYN"), industry=no_filer(),
                       entry_ids=[entry_id])[entry_id]


def averaged(values, span=5):
    """The expected rate, from the definition and not from the engine."""
    base = sum(values[:3]) / 3.0
    end = sum(values[-3:]) / 3.0
    return ((end / base) ** (1.0 / span) - 1) * 100.0


# ---------------------------------------------------------------------------
# Outcome 1 — every CAGR uses averaged endpoints
# ---------------------------------------------------------------------------

class TestTheCaseThatMotivatesIt:
    """A true 7.4% grower whose base year carried a one-off charge.

    Nothing about this company is unusual and nothing about the wrong answer
    looks wrong. That is the point: 20% on a business compounding at 7% is
    not caught by an upper band, because it is not absurd — it is the number
    a good business would produce. A reject silently becomes a buy and no
    rule anywhere fires.

    The charge sits in the year that was the BASE of the old six-year
    window, which is where it does the damage.
    """

    CLEAN = {y: 100.0 * (1.074 ** (y - 2019)) for y in range(2019, 2027)}
    CHARGED = {**CLEAN, 2021: CLEAN[2021] * 0.5717}
    FLAT = {y: 100_000.0 for y in range(2019, 2027)}

    def rate(self, ni):
        r = one(with_income(self.FLAT, ni), "net_income_cagr_5y")
        assert r["status"] == "computed"
        return r

    def endpoint(self, ni):
        """What the old construction served, worked out here from the same
        figures — the size of the change belongs on the record rather than
        in a comment."""
        base, last = ni[2021], ni[2026]
        return ((last / base) ** (1 / 5) - 1) * 100.0

    def test_the_averaged_rate_is_what_the_definition_says(self):
        r = self.rate(self.CHARGED)
        assert r["value"] == pytest.approx(
            averaged([self.CHARGED[y] for y in sorted(self.CHARGED)]),
            abs=1e-9)

    def test_the_charge_costs_the_old_construction_thirteen_points(self):
        assert self.endpoint(self.CLEAN) == pytest.approx(7.4, abs=0.1)
        assert self.endpoint(self.CHARGED) == pytest.approx(20.1, abs=0.3)

    def test_and_lands_it_mid_band_where_nothing_catches_it(self):
        """Not a rejection. 20% is inside any plausible fast-grower band, so
        every test passes and the reader is told a 7% company grows at 20%."""
        assert 15.0 < self.endpoint(self.CHARGED) < 25.0

    def test_averaging_absorbs_most_of_it(self):
        """Three years at each end leave a third of one year's distortion,
        not all of it. Four points of error against thirteen."""
        moved = self.rate(self.CHARGED)["value"] \
            - self.rate(self.CLEAN)["value"]
        assert 0 < moved < 4.0
        endpoint_moved = self.endpoint(self.CHARGED) \
            - self.endpoint(self.CLEAN)
        assert endpoint_moved > 12.0

    def test_dropping_the_charged_year_recovers_the_rest(self):
        """And so the leave-one-out reading, which is what a breach of a
        windowed measure has to survive, lands on the underlying rate."""
        r = self.rate(self.CHARGED)
        outs = {o["dropped"]: o["value"] for o in r["leave_one_out"]}
        assert outs["2021-12-31"] == pytest.approx(7.4, abs=1.0)


class TestEightYearsAndNoFallback:
    def test_seven_years_is_a_named_absence(self):
        r = one(years({y: 100.0 + y for y in range(2020, 2027)}),
                "revenue_cagr_5y")
        assert r["status"] == "absent"
        assert "7 fiscal year" in r["reason"] and "8 are needed" in r["reason"]

    def test_eight_years_computes(self):
        vals = {y: 100.0 * (1.08 ** (y - 2019)) for y in range(2019, 2027)}
        r = one(years(vals), "revenue_cagr_5y")
        assert r["status"] == "computed"
        assert r["value"] == pytest.approx(
            averaged([vals[y] for y in sorted(vals)]), abs=1e-9)

    def test_the_three_year_rate_needs_six_and_not_four(self):
        five = {y: 100.0 + y for y in range(2022, 2027)}
        assert one(years(five), "revenue_cagr_3y")["status"] == "absent"
        six = {y: 100.0 + y for y in range(2021, 2027)}
        got = one(years(six), "revenue_cagr_3y")
        assert got["status"] == "computed"
        assert got["value"] == pytest.approx(
            averaged([six[y] for y in sorted(six)], span=3), abs=1e-9)

    def test_a_thinner_window_is_never_quietly_substituted(self):
        """The absence has to stay an absence. A measure that silently
        becomes a two-year mean when the eighth year is missing reads
        identically on screen and answers a different question."""
        r = one(years({y: 100.0 + y for y in range(2020, 2027)}),
                "revenue_cagr_5y")
        assert r["status"] == "absent"
        assert "value" not in r


class TestTheSpreadsInheritIt:
    def test_a_spread_is_the_difference_of_two_averaged_rates(self):
        rev = {y: 1000.0 * (1.05 ** (y - 2019)) for y in range(2019, 2027)}
        ni = {y: 100.0 * (1.09 ** (y - 2019)) for y in range(2019, 2027)}
        got = one(with_income(rev, ni), "ni_minus_revenue_cagr_spread_5y")
        assert got["status"] == "computed"
        assert got["value"] == pytest.approx(
            averaged([ni[y] for y in sorted(ni)])
            - averaged([rev[y] for y in sorted(rev)]), abs=1e-9)

    def test_a_spread_drops_the_same_year_from_both_sides(self):
        """A difference between one rate missing FY2021 and another missing
        FY2019 is a number that answers nothing and reads like an answer."""
        rev = {y: 1000.0 * (1.05 ** (y - 2019)) for y in range(2019, 2027)}
        ni = {y: 100.0 * (1.09 ** (y - 2019)) for y in range(2019, 2027)}
        filings = with_income(rev, ni)
        spread = one(filings, "ni_minus_revenue_cagr_spread_5y")
        a = compute_all(filings, None, symbols("SYN"), industry=no_filer(),
                        entry_ids=["net_income_cagr_5y", "revenue_cagr_5y"])
        left = {o["dropped"]: o["value"]
                for o in a["net_income_cagr_5y"]["leave_one_out"]}
        right = {o["dropped"]: o["value"]
                 for o in a["revenue_cagr_5y"]["leave_one_out"]}
        for o in spread["leave_one_out"]:
            assert o["value"] == pytest.approx(
                left[o["dropped"]] - right[o["dropped"]], abs=1e-9)
        assert set(o["dropped"] for o in spread["leave_one_out"]) \
            == set(left) & set(right)


# ---------------------------------------------------------------------------
# Genuine smallness — the earnings that appeared rather than grew
# ---------------------------------------------------------------------------

class TestEarningsThatAppeared:
    """Both halves are required, and each exists because the other misfires.

    Measured against 380 real filers: the margin half alone fires on
    companies whose base-period earnings were substantial — it is
    algebraically a margin-expansion test, which this bank already publishes
    separately. The multiple half alone fires on a company whose revenue
    multiplied about as fast as its earnings, which is growth. Together they
    fired on one filer in 380, and that filer's earnings came from emerging
    from bankruptcy while its revenue shrank.
    """

    FLAT_REVENUE = {y: 1000.0 for y in range(2019, 2027)}

    def test_earnings_that_appeared_are_routed_not_greyed(self):
        # Net margin 0.5% at the base, 8% at the end, on flat revenue.
        ni = {2019: 5.0, 2020: 5.0, 2021: 5.0, 2022: 30.0,
              2023: 60.0, 2024: 80.0, 2025: 80.0, 2026: 80.0}
        r = one(with_income(self.FLAT_REVENUE, ni), "net_income_cagr_5y")
        assert r["status"] == "absent"
        assert "does not establish a grower" in r["reason"]
        assert "appeared" in r["reason"]
        # It points at the right question rather than saying "unanswerable".
        assert "margin recovery or a turnaround" in r["reason"]
        assert "0.50%" in r["reason"] and "8.00%" in r["reason"]

    def test_a_real_grower_whose_revenue_grew_too_is_not_refused(self):
        """Earnings multiplied nearly twentyfold and so did revenue. The multiple half fires and the margin half does not, so the
        rate stands — which is the whole reason both halves are required."""
        rev = {2019: 100.0, 2020: 110.0, 2021: 120.0, 2022: 400.0,
               2023: 900.0, 2024: 1500.0, 2025: 2000.0, 2026: 2400.0}
        ni = {y: v * 0.30 for y, v in rev.items()}
        r = one(with_income(rev, ni), "net_income_cagr_5y")
        assert r["status"] == "computed"

    def test_a_margin_expander_with_real_base_earnings_is_not_refused(self):
        """Net margin roughly doubled on a base that was already 10%. The margin half fires and the multiple half does not."""
        rev = {y: 1000.0 * (1.14 ** (y - 2019)) for y in range(2019, 2027)}
        ni = {y: v * (0.10 if y < 2022 else 0.21) for y, v in rev.items()}
        r = one(with_income(rev, ni), "net_income_cagr_5y")
        assert r["status"] == "computed"

    def test_the_gate_reads_earnings_and_not_per_share(self):
        """Per-share growth is gated on net income, because a share count
        that halved says nothing about whether the company had earnings."""
        ni = {2019: 5.0, 2020: 5.0, 2021: 5.0, 2022: 30.0,
              2023: 60.0, 2024: 80.0, 2025: 80.0, 2026: 80.0}
        extra = {y: [dur("us-gaap:NetIncomeLoss",
                         f"{y}-01-01", f"{y}-12-31", v),
                     dur("us-gaap:EarningsPerShareDiluted",
                         f"{y}-01-01", f"{y}-12-31", v / 100.0)]
                 for y, v in ni.items()}
        r = one(years(self.FLAT_REVENUE, extra=extra), "eps_cagr_5y")
        assert r["status"] == "absent"
        assert "does not establish a grower" in r["reason"]

    def test_revenue_growth_is_never_gated_on_it(self):
        """A company selling ten times what it sold is a company selling ten
        times what it sold. Revenue has no margin under it and a small
        revenue base is the thing itself, not an artefact of one."""
        rev = {2019: 10.0, 2020: 12.0, 2021: 14.0, 2022: 200.0,
               2023: 600.0, 2024: 900.0, 2025: 1100.0, 2026: 1300.0}
        ni = {y: v * 0.02 for y, v in rev.items()}
        r = one(with_income(rev, ni), "revenue_cagr_5y")
        assert r["status"] == "computed"

    def test_an_unreadable_margin_check_refuses_rather_than_serves(self):
        """A tenfold rise in earnings with no revenue to check it against
        cannot be told from a margin coming back off the floor. If it cannot
        be right, it is absent — the caution would be read by a person and
        ignored by the arithmetic."""
        ni = {2019: 5.0, 2020: 5.0, 2021: 5.0, 2022: 30.0,
              2023: 60.0, 2024: 80.0, 2025: 80.0, 2026: 80.0}
        filings = years(ni, concept="us-gaap:NetIncomeLoss")
        r = one(filings, "net_income_cagr_5y")
        assert r["status"] == "absent"
        assert "Revenue could not be read" in r["reason"]


class TestARateRefusesInTheBanksWords:
    """Both of `_cagr`'s refusals are citations now, and one of them had
    nothing to cite.

    The helper wrote its own sentences, each opening "Not meaningful here:" —
    the shape `compute.not_meaningful` prints, which promises the words after
    the colon are the bank's and can be looked up. For the base-mean refusal
    that promise happened to be keepable. For the other it was not: a positive
    base falling to a negative end is a profit turning into a loss, which is
    ordinary, and no entry declared it anywhere. A reader who followed the
    sentence to the Metrics page found nothing, which is the exact failure the
    citation mechanism exists to end, reproduced by borrowing its opening.
    """

    EIGHT = tuple(range(2019, 2027))

    def _profit_turning_into_a_loss(self):
        """Positive at the base, negative at the end. Revenue stays healthy,
        so this is a real business losing money, not an arithmetic corner."""
        ni = dict(zip(self.EIGHT, (80.0, 90.0, 85.0, 40.0, 10.0,
                                   -30.0, -60.0, -90.0)))
        return with_income({y: 1000.0 for y in self.EIGHT}, ni)

    def test_a_negative_end_is_refused_and_says_so_in_the_banks_words(self):
        r = one(self._profit_turning_into_a_loss(), "net_income_cagr_5y")
        assert r["status"] == "absent"
        assert r["reason"].startswith(
            compute.NOT_MEANINGFUL
            + "mean net income over the three end years is negative")
        assert compute.CITES_THE_BANK in r["reason"]

    def test_the_condition_it_cites_is_one_the_entry_declares(self):
        """The half that makes the sentence worth printing. Every `data`
        condition reachable from here is checked against the entry's own
        declaration by `not_meaningful`, so this cannot drift into naming a
        test the Metrics page does not carry."""
        declared = bank.data_conditions()["net_income_cagr_5y"]
        assert "mean net income over the three end years is negative" \
            in declared
        r = one(self._profit_turning_into_a_loss(), "net_income_cagr_5y")
        assert any(c in r["reason"] for c in declared)

    def test_the_reading_travels_beside_the_condition_not_inside_it(self):
        """`detail` is what this filer's figures were, which the bank cannot
        know. It never restates the condition — that is what keeps one copy
        of the sentence."""
        r = one(self._profit_turning_into_a_loss(), "net_income_cagr_5y")
        assert "-60.00" in r["reason"] or "60.00" in r["reason"]

    def test_a_zero_or_negative_base_cites_its_own_condition(self):
        """The other refusal, which is a different fact and reads
        differently: this one says the rate had nowhere to start from."""
        ni = dict(zip(self.EIGHT, (-10.0, -5.0, 0.0, 20.0, 40.0,
                                   60.0, 80.0, 100.0)))
        r = one(with_income({y: 1000.0 for y in self.EIGHT}, ni),
                "net_income_cagr_5y")
        assert r["status"] == "absent"
        assert r["reason"].startswith(
            compute.NOT_MEANINGFUL
            + "mean net income over the three base years is zero or negative")


# ---------------------------------------------------------------------------
# Outcome 2 — the estimator, declared and enforced
# ---------------------------------------------------------------------------

class TestTheBankDeclaresHowEveryMeasureIsRead:
    def test_every_entry_declares_a_kind_the_host_knows(self):
        for e in bank.load_bank()["entries"]:
            est = contract.estimator_of(str(e["id"]))
            assert est is not None, e["id"]
            assert est["kind"] in contract.ESTIMATORS

    def test_an_entry_with_no_estimator_is_refused_at_load(self, tmp_path,
                                                           monkeypatch):
        """Refused rather than defaulted. Every fallback is either the strict
        one, which silently stops exits firing, or the loose one, which
        silently fires them on a single year."""
        (tmp_path / "holed.yaml").write_text(
            "schema: ledger.metric-bank/1\n"
            "entries:\n  - id: x\n    kind: computed\n", encoding="utf-8")
        monkeypatch.setattr(bank, "CONFIG_DIR", tmp_path)
        bank._bank_cache.clear()
        with pytest.raises(ValueError, match="declares no `estimator`"):
            bank.load_bank("holed")

    def test_an_unknown_kind_is_refused_at_load(self, tmp_path, monkeypatch):
        (tmp_path / "odd.yaml").write_text(
            "schema: ledger.metric-bank/1\n"
            "entries:\n  - id: x\n    kind: computed\n"
            "    estimator:\n      kind: vibes\n", encoding="utf-8")
        monkeypatch.setattr(bank, "CONFIG_DIR", tmp_path)
        bank._bank_cache.clear()
        with pytest.raises(ValueError, match="not one of"):
            bank.load_bank("odd")

    def test_a_windowed_kind_must_say_how_many_observations(self, tmp_path,
                                                            monkeypatch):
        """A three-point median and a five-point one do not resist an outlier
        equally, and the policy turns on exactly that."""
        (tmp_path / "vague.yaml").write_text(
            "schema: ledger.metric-bank/1\n"
            "entries:\n  - id: x\n    kind: computed\n"
            "    estimator:\n      kind: median\n", encoding="utf-8")
        monkeypatch.setattr(bank, "CONFIG_DIR", tmp_path)
        bank._bank_cache.clear()
        with pytest.raises(ValueError, match="how many annual observations"):
            bank.load_bank("vague")

    def test_every_estimator_that_asks_for_a_dropped_year_supplies_one(self):
        """The quiet failure this guards: an entry whose estimator demands
        the one-year-dropped reading and whose computation never forms one
        can never establish a breach, and nothing says so — the exit simply
        stops firing.
        """
        rev = {y: 1000.0 * (1.05 ** (y - 2019)) for y in range(2019, 2027)}
        ni = {y: 100.0 * (1.09 ** (y - 2019)) for y in range(2019, 2027)}
        filings = with_income(rev, ni)
        want = [str(e["id"]) for e in bank.load_bank()["entries"]
                if (contract.estimator_of(str(e["id"])) or {})
                .get("robustness") == "always"]
        assert want, "no measure asks for a dropped year, which cannot be right"
        got = compute_all(filings, None, symbols("SYN"), industry=no_filer(),
                          entry_ids=want)
        formed = [eid for eid, r in got.items()
                  if r.get("status") == "computed"]
        assert formed, "none of them computed on this fixture"
        for eid in formed:
            assert got[eid].get("leave_one_out"), eid
        # This fixture carries revenue and net income and nothing else, so
        # most of `want` goes absent on it and is checked by nobody. Named
        # here rather than left implicit, because a silent skip is how this
        # test came to cover six of thirteen while reading as though it
        # covered all of them — and the seven it missed include the entry
        # this whole split was about.
        skipped = sorted(set(want) - set(formed))
        assert skipped == [
            "eps_cagr_5y", "eps_growth_10y",
            "eps_minus_revenue_cagr_spread_5y",
            "goodwill_impairment_to_equity_5y", "gross_margin_range_5y",
            "gross_margin_range_relative_5y", "gross_margin_vs_3y_median",
            "incremental_roic_5y", "total_debt_to_avg_fcf_5y",
        ], skipped

    def test_a_formula_that_drops_a_year_declares_the_window_it_drops_from(
            self):
        """The other direction, and the one that was live.

        Forming a dropped-year reading is a statement that this measure is
        judged against a window of fiscal years — one of them can be taken
        out and the answer asked again. If the estimator declares no such
        window, that statement is made in the computation and nowhere a
        reader or a strategy can see it, and the robustness question is
        answered "no" by default.

        `total_debt_to_avg_fcf_5y` was exactly there: debt at one
        balance-sheet date over five fiscal years of free cash flow
        averaged, declared `instant` because the instant is the leg a new
        filing replaces — which is right, and which used to also decide that
        no year could be carrying it. A Buffett exit read it. That is what
        `estimator.window` is for.

        Not "robustness must be always": a five-point median deliberately
        does not demand the check (one observation cannot move it past the
        one beside it) and still offers the reading, because a strategy may
        cite `without` on any measure that has a window. What is refused is
        forming one with no window declared anywhere.
        """
        from conftest import balance_face, dur as _dur, inst as _inst
        rev = {y: 1000.0 * (1.05 ** (y - 2015)) for y in range(2015, 2027)}
        ni = {y: 100.0 * (1.09 ** (y - 2015)) for y in range(2015, 2027)}
        extra = {y: [_dur("us-gaap:CostOfRevenue",
                          f"{y}-01-01", f"{y}-12-31", 600.0),
                     _dur("us-gaap:NetCashProvidedByUsedInOperating"
                          "Activities", f"{y}-01-01", f"{y}-12-31", 200.0,
                          stmt="CashFlowStatement"),
                     _dur("us-gaap:PaymentsToAcquirePropertyPlantAnd"
                          "Equipment", f"{y}-01-01", f"{y}-12-31", 50.0,
                          stmt="CashFlowStatement"),
                     _dur("us-gaap:PaymentsOfDividendsCommonStock",
                          f"{y}-01-01", f"{y}-12-31", 20.0,
                          stmt="CashFlowStatement"),
                     _dur("us-gaap:NetIncomeLoss",
                          f"{y}-01-01", f"{y}-12-31", ni[y])]
                 + balance_face(f"{y}-12-31", extra=[
                     _inst("us-gaap:LongTermDebtNoncurrent",
                           f"{y}-12-31", 300.0),
                     _inst("us-gaap:StockholdersEquity",
                           f"{y}-12-31", 400.0),
                 ])
                 for y in rev}
        got = compute_all(years(rev, extra=extra), None, symbols("SYN"),
                          industry=no_filer())
        offenders, checked = [], []
        for eid, r in got.items():
            if r.get("status") != "computed" or not r.get("leave_one_out"):
                continue
            est = contract.estimator_of(eid) or {}
            checked.append(eid)
            if est.get("kind") not in contract.WINDOW_STATISTICS \
                    and not est.get("window"):
                offenders.append(eid)
        assert offenders == [], (
            "these form a dropped-year reading and declare no window to drop "
            "it from — say what they are judged against, under "
            "`estimator.window`: " + ", ".join(sorted(offenders)))
        assert "total_debt_to_avg_fcf_5y" in checked, (
            "the entry this check was written for did not compute on this "
            "fixture, so it proved nothing")


class TestADroppedYearNeverFlatters:
    """A leave-one-out reading exists so a breach can be asked whether one
    year produced it. It must never be the way a wrong number gets in.

    The failure it guards is specific to a ratio. Every measure here is
    guarded against a meaningless denominator on the full window — but
    dropping a year can produce one where the full window had none, and the
    arithmetic then returns either a crash or a NEGATIVE figure. On a
    lower-is-better measure a negative reads as the company being in
    outstanding shape, so the flattering answer arrives through the one door
    marked robustness, at exactly the moment a breach was being tested.
    """

    YEARS = ["2019-12-31", "2020-12-31", "2021-12-31", "2022-12-31",
             "2023-12-31"]

    # Debt of 100 against five years of free cash flow, one of them badly
    # negative and one of them very good. The window averages +2, so the
    # measure is computable and reads 50 years of cash flow owed.
    CARRIED = [-38.0, 5.0, 6.0, 7.0, 30.0]

    @staticmethod
    def years_owed(values):
        return 100.0 / (sum(values) / len(values))

    def test_a_year_whose_removal_empties_the_denominator_is_skipped(self):
        """Drop the good year and the average goes negative. That reading is
        not offered, rather than offered as an improvement."""
        full, outs = compute._with_one_out(
            self.CARRIED, self.YEARS, self.years_owed,
            lambda rest: sum(rest) / len(rest) > 0)
        assert full == pytest.approx(50.0)
        assert "2023-12-31" not in [o["dropped"] for o in outs]
        assert len(outs) == 4
        assert all(o["value"] > 0 for o in outs)

    def test_without_the_guard_the_same_window_reads_as_excellent(self):
        """The number this refuses, shown once so the guard is not mistaken
        for tidiness. Dropping the good year takes the reading from 50 years
        of cash flow owed to MINUS 20 — and on a measure where lower is
        better, minus 20 is the best figure on the page."""
        _full, unguarded = compute._with_one_out(
            self.CARRIED, self.YEARS, self.years_owed)
        assert {o["dropped"]: o["value"]
                for o in unguarded}["2023-12-31"] < 0

    def test_a_zero_denominator_would_take_the_whole_measure_down(self):
        """The other half. Where a dropped year leaves an average of exactly
        nought, the unguarded version raises — and `compute_all` turns that
        into 'computation failed' for an entry that was perfectly
        computable. Absence for the wrong reason is still a measure that
        stopped working, and it reads identically to a company with no
        filings."""
        values = [-15.0, 5.0, 5.0, 5.0, 5.0]
        with pytest.raises(ZeroDivisionError):
            compute._with_one_out(values, self.YEARS, self.years_owed)
        _full, outs = compute._with_one_out(
            values, self.YEARS, self.years_owed,
            lambda rest: sum(rest) / len(rest) > 0)
        assert [o["dropped"] for o in outs] == ["2019-12-31"]


# ---------------------------------------------------------------------------
# what confirm() does with each kind
# ---------------------------------------------------------------------------

QUARTERS = ["2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31",
            "2026-03-31"]


def ctx_for(measure, current, points=(), leave_one_out=None, limit=1.0):
    """A context shaped exactly as engine/context.py builds one, holding one
    measure and one setting."""
    cur = ({"status": "known", "value": current, "source": "computed",
            "cautions": [], "provenance": []}
           if current is not None
           else {"status": "absent", "reason": "not on record"})
    if leave_one_out is not None:
        cur["leave_one_out"] = list(leave_one_out)
    return {
        "measures": {measure: {
            "current": cur,
            "series": {"cadence": "quarterly", "note": None,
                       "truncated": False,
                       "points": [{"period_end": p, "filed": p,
                                   "form": "10-Q", "accession": "A",
                                   "value": v, "reason":
                                       None if v is not None else "no data",
                                   "cautions": [], "provenance": []}
                                  for p, v in points]}}},
        "values": {"floor": limit},
        "today": "2026-08-10",
    }


def item(measure, comparator="at_least"):
    return {"measure": measure, "comparator": comparator,
            "threshold_from": "floor"}


class TestConfirmationFollowsTheEstimator:
    def test_a_five_year_median_fires_on_the_first_breach(self):
        """One outlier cannot move a median past the observation next to it —
        the window already did the smoothing confirmation is for, and the
        next reading shares four of the same five years."""
        ctx = ctx_for("roic_median_5y", 8.0,
                      [(q, 20.0) for q in QUARTERS[:-1]]
                      + [(QUARTERS[-1], 8.0)], limit=12.0)
        got = contract.confirm(ctx, item("roic_median_5y"))
        assert got["confirmation"] == contract.CONFIRMED
        assert got["needs"] == 0
        assert "already done the smoothing" in got["why"]

    def test_a_reading_at_one_date_takes_two_filings(self):
        """A bond issued the week before the year end is in the balance
        sheet, and the next filing brings a wholly new reading."""
        one_bad = ctx_for("current_ratio", 0.9,
                          [(q, 2.4) for q in QUARTERS[:-1]]
                          + [(QUARTERS[-1], 0.9)], limit=1.2)
        assert contract.confirm(one_bad, item("current_ratio"))[
            "confirmation"] == contract.BREACHED

        two_bad = ctx_for("current_ratio", 0.9,
                          [(q, 2.4) for q in QUARTERS[:-2]]
                          + [(q, 0.9) for q in QUARTERS[-2:]], limit=1.2)
        got = contract.confirm(two_bad, item("current_ratio"))
        assert got["confirmation"] == contract.CONFIRMED
        assert got["needs"] == 2 and got["periods"] == QUARTERS[::-1][:2]

    def test_two_readings_at_each_end_take_one_filing(self):
        """Not a long-window measure however many years it spans: two
        observations, and the next filing replaces the one carrying the
        noise. One confirmation, never four."""
        none_yet = ctx_for("diluted_share_count_change_5y", 14.0,
                           [(q, 0.0) for q in QUARTERS], limit=0.0)
        got = contract.confirm(none_yet,
                               item("diluted_share_count_change_5y",
                                    "at_most"))
        assert got["confirmation"] == contract.BREACHED and got["needs"] == 1

        one_bad = ctx_for("diluted_share_count_change_5y", 14.0,
                          [(q, 0.0) for q in QUARTERS[:-1]]
                          + [(QUARTERS[-1], 14.0)], limit=0.0)
        assert contract.confirm(one_bad,
                                item("diluted_share_count_change_5y",
                                     "at_most"))[
            "confirmation"] == contract.CONFIRMED

    def test_a_count_of_annual_reports_asks_for_nothing_on_top(self):
        """The unit is annual reports, so the level already says how many
        filings it takes. Two losing years spans two annual reports;
        demanding two consecutive filings would quietly demand a third."""
        ctx = ctx_for("consecutive_annual_loss_years", 2.0, [], limit=2.0)
        got = contract.confirm(ctx, item("consecutive_annual_loss_years",
                                         "below"))
        assert got["confirmation"] == contract.CONFIRMED
        assert got["needs"] == 0 and got["run"] == 0

    def test_a_measure_needing_no_confirmation_fires_without_any_filings(
            self):
        """The consequence worth naming: a journal driven by hand-entered
        figures has no filing series at all, so an exit that counted filings
        could never fire in one however bad the number got. Where the
        estimator asks for none, it can."""
        ctx = ctx_for("roic_median_5y", 3.0, [], limit=12.0)
        assert contract.confirm(ctx, item("roic_median_5y"))[
            "confirmation"] == contract.CONFIRMED

    def test_a_gap_neither_confirms_a_breach_nor_forgives_one(self):
        ctx = ctx_for("current_ratio", 0.9,
                      [(QUARTERS[0], 2.4), (QUARTERS[1], 0.9),
                       (QUARTERS[2], None), (QUARTERS[3], 0.9),
                       (QUARTERS[4], 0.9)], limit=1.2)
        assert contract.confirm(ctx, item("current_ratio"))[
            "confirmation"] == contract.CONFIRMED

    def test_absence_is_unreadable_and_never_a_confirmation(self):
        ctx = ctx_for("current_ratio", None,
                      [(q, 0.9) for q in QUARTERS], limit=1.2)
        got = contract.confirm(ctx, item("current_ratio"))
        assert got["confirmation"] == contract.UNREADABLE
        assert got["run"] == 0

    def test_a_requirement_that_holds_is_clear(self):
        ctx = ctx_for("current_ratio", 2.4,
                      [(q, 2.4) for q in QUARTERS], limit=1.2)
        assert contract.confirm(ctx, item("current_ratio"))[
            "confirmation"] == contract.CLEAR


class TestTheDroppedYear:
    """A range over five years is the least robust statistic there is: one
    year sets the top of it single-handed, and that year stays in the window
    for as long as the window is long. Waiting cannot help."""

    def test_a_breach_one_year_is_carrying_waits(self):
        ctx = ctx_for("gross_margin_range_5y", 9.0, [],
                      leave_one_out=[{"dropped": "2022-12-31", "value": 3.0},
                                     {"dropped": "2023-12-31", "value": 8.8}],
                      limit=6.0)
        got = contract.confirm(ctx, item("gross_margin_range_5y", "at_most"))
        assert got["confirmation"] == contract.BREACHED
        assert got["robust"] is False
        assert "one year is carrying this" in got["why"]

    def test_a_breach_the_record_carries_fires_now(self):
        ctx = ctx_for("gross_margin_range_5y", 9.0, [],
                      leave_one_out=[{"dropped": "2022-12-31", "value": 8.2},
                                     {"dropped": "2023-12-31", "value": 8.8}],
                      limit=6.0)
        got = contract.confirm(ctx, item("gross_margin_range_5y", "at_most"))
        assert got["confirmation"] == contract.CONFIRMED
        assert got["robust"] is True

    def test_a_check_that_cannot_be_made_never_passes_itself(self):
        """A robustness check that silently falls back to the number it was
        checking is not a check."""
        ctx = ctx_for("gross_margin_range_5y", 9.0, [], limit=6.0)
        got = contract.confirm(ctx, item("gross_margin_range_5y", "at_most"))
        assert got["confirmation"] == contract.BREACHED
        assert got["robust"] is None
        assert "could not be worked out" in got["why"]

    def test_the_dropped_year_is_the_one_that_most_favours_the_company(self):
        """Cited, so a reader can check the rule rather than take it on
        trust — and it is the host that picks which year, from the direction
        of the test."""
        ctx = ctx_for("gross_margin_range_5y", 9.0, [],
                      leave_one_out=[{"dropped": "2022-12-31", "value": 3.0},
                                     {"dropped": "2023-12-31", "value": 8.8}],
                      limit=6.0)
        rendered, errors = contract.resolve_evidence(
            {"values": [{"id": "floor", "label": "Widest swing",
                         "type": "number", "unit": "percentage_points",
                         "source": {"name": "invented", "reasoning": False},
                         "explain": "x" * 130}]},
            ctx, [{**item("gross_margin_range_5y", "at_most"),
                   "without": "one-year"}])
        assert errors == []
        assert rendered[0]["observed"]["value"] == 3.0
        assert rendered[0]["outcome"] == contract.PASS
        assert "most favourable year dropped" in rendered[0]["subject"]["label"]
        assert "2022-12-31" in rendered[0]["observed"]["provenance"][0]


class TestWhatAConfirmationRefuses:
    def test_a_citation_with_no_requirement_raises(self):
        ctx = ctx_for("current_ratio", 2.4, [])
        with pytest.raises(ValueError, match="nothing for a filing to confirm"):
            contract.confirm(ctx, {"measure": "current_ratio"})

    def test_a_subject_with_no_filing_history_raises(self):
        ctx = ctx_for("current_ratio", 2.4, [])
        with pytest.raises(ValueError, match="needs a citation naming"):
            contract.confirm(ctx, {"fact": "position.weight",
                                   "comparator": "at_most",
                                   "threshold_from": "floor"})

    def test_a_dropped_year_beside_a_past_reading_is_refused(self):
        errors = contract.validate_decision(
            {"states": [{"id": "s", "render": "hold", "name": "S"}]},
            {"state": "s", "payload": {},
             "reason": {"rule": "r", "summary": "s", "note": None,
                        "groups": [],
                        "evidence": [{"measure": "roic_median_5y",
                                      "at": "2025-12-31",
                                      "without": "one-year"}]}})
        assert any("different questions" in e for e in errors)

    def test_an_invented_robustness_form_is_refused(self):
        errors = contract.validate_decision(
            {"states": [{"id": "s", "render": "hold", "name": "S"}]},
            {"state": "s", "payload": {},
             "reason": {"rule": "r", "summary": "s", "note": None,
                        "groups": [],
                        "evidence": [{"measure": "roic_median_5y",
                                      "without": "two-years"}]}})
        assert any("never invents one" in e for e in errors)


class TestNoStrategyStatesAConfirmationCount:
    def test_no_shipped_bundle_declares_one(self):
        """The structural half of the change. A setting that could ask for
        four readings of a five-year median is not discouraged, it is
        unavailable — including to whoever writes the next bundle and does
        not know why it mattered."""
        from engine import strategy_loader
        loaded, _reports = strategy_loader.discover()
        assert loaded
        for record in loaded.values():
            for spec in record.get("values") or []:
                assert "confirmation" not in spec["id"], \
                    f'{record["id"]} declares {spec["id"]}'
                assert "quarters" not in spec["id"], \
                    f'{record["id"]} declares {spec["id"]}'


# ---------------------------------------------------------------------------
# and across the boundary a strategy actually reads
# ---------------------------------------------------------------------------

class TestTheDroppedYearReachesAStrategy:
    """The one-out readings are computed in the engine and consumed in the
    contract, and everything above tests those two ends separately. This is
    the join.

    It is worth its own test because of how it fails: stop carrying them over
    the boundary and nothing raises, nothing renders wrong, and no measure
    goes absent — every exit on a windowed measure simply stops firing, for
    ever, in silence.
    """

    def _stored(self, cik, margins):
        """Five fiscal years of gross margin, from one filing each."""
        from engine import facts_store
        for i, (y, gm) in enumerate(sorted(margins.items())):
            rev = 1000.0
            f = filing(f"G-{y}", "10-K", f"{y + 1}-02-15", f"{y}-12-31", [
                dur("us-gaap:Revenues", f"{y}-01-01", f"{y}-12-31", rev),
                dur("us-gaap:GrossProfit", f"{y}-01-01", f"{y}-12-31",
                    rev * gm / 100.0),
            ])
            f["cik"] = cik
            facts_store.save_filing(cik, f)

    def test_a_strategy_can_ask_whether_a_breach_survives_a_dropped_year(
            self):
        from engine import context
        # Four steady years and one that swings the range wide on its own.
        self._stored(4242, {2022: 40.0, 2023: 41.0, 2024: 40.5,
                            2025: 41.5, 2026: 28.0})
        sec = {"ticker": "SYN", "name": "Synthetic Co", "cik": 4242,
               "lots": []}
        ctx = context.build_context(sec, [sec], {"floor": 6.0}, {})

        cur = ctx["measures"]["gross_margin_range_5y"]["current"]
        assert cur["status"] == "known"
        assert cur["leave_one_out"], \
            "the one-out readings did not cross the boundary"

        cite = {"measure": "gross_margin_range_5y", "comparator": "at_most",
                "threshold_from": "floor"}
        got = contract.confirm(ctx, cite)
        # The full window is far over the limit; drop the one bad year and it
        # is comfortably inside. One year is carrying it, so nothing fires.
        assert contract.test(ctx, cite) == contract.FAIL
        assert got["confirmation"] == contract.BREACHED
        assert got["robust"] is False
        assert contract.test(ctx, {**cite, "without": "one-year"}) \
            == contract.PASS


# ---------------------------------------------------------------------------
# the clock a breach is counted on
# ---------------------------------------------------------------------------

def _priced_filer():
    """A filer whose book equity is readable and whose cover states a count,
    so the price-bearing entries reach a price instead of refusing above it."""
    from conftest import balance_face, inst
    end = "2025-12-31"
    facts = balance_face(end, extra=[
        inst("us-gaap:StockholdersEquity", end, 400.0),
    ]) + [{**inst("dei:EntityCommonStockSharesOutstanding", "2026-01-05",
                  100.0, stmt=None), "unit": "shares", "currency": None}]
    return [filing("K1", "10-K", "2026-02-10", end, facts)]


def _sessions(cik, closes, events=()):
    from engine import price_store
    doc = price_store.load(cik)
    price_store.merge_series(doc, "ACME", "test",
                             [[d, c, 100] for d, c in closes],
                             [list(e) for e in events])
    return doc


def _series(cik, closes, today):
    from engine import instruments
    from engine.context import _series_for
    fs = _priced_filer()
    return _series_for(fs, _sessions(cik, closes), 
                       instruments.company_symbols(fs, ["ACME"]),
                       today, ind=no_filer())


class TestAPriceIsReadEverySession:
    """`instant`'s case for two confirmations is that the next filing brings a
    wholly new reading. True of a balance sheet. False of a price ratio, where
    every day brings one — and the filing series doing the waiting cannot see
    any of it.

    So a measure carrying a quoted price is counted on the series it actually
    changes on. Everything downstream is unchanged: the same point shape, the
    same run, the same `confirm`. What moved is which series says when a new
    reading exists.
    """

    CLOSES = [(f"2026-03-0{d}", 10.0 + d) for d in range(2, 7)]

    def test_a_price_measure_is_read_on_trading_days(self):
        s = _series(920, self.CLOSES, "2026-03-06")["price_to_book"]
        assert s["cadence"] == "daily"
        assert [p["period_end"] for p in s["points"]] == \
            [d for d, _ in self.CLOSES]
        # a different reading each session, which is the whole argument
        assert len({p["value"] for p in s["points"]}) == len(self.CLOSES)

    def test_a_filing_measure_is_still_read_on_filings(self):
        s = _series(921, self.CLOSES, "2026-03-06")["current_ratio"]
        assert s["cadence"] == "quarterly"
        assert [p["period_end"] for p in s["points"]] == ["2025-12-31"]

    def test_only_days_the_series_holds_a_close_for_are_boundaries(self):
        """`price_store.close_on` reaches back to the nearest earlier trading
        day. A boundary on a day with no row would serve the day before's
        close a second time, and the run would count one observation twice —
        the same failure the filing frontier rule exists to prevent, arriving
        by a different route."""
        closes = [("2026-03-02", 12.0), ("2026-03-06", 13.0)]
        s = _series(922, closes, "2026-03-10")["price_to_book"]
        assert [p["period_end"] for p in s["points"]] == \
            ["2026-03-02", "2026-03-06"]

    def test_a_session_reading_never_names_a_filing(self):
        """No document produced it. An accession here would attribute a figure
        to a filing that never contained it — and `portfolio._snapshot` freezes
        whatever it is handed, for good."""
        s = _series(923, self.CLOSES, "2026-03-06")["price_to_book"]
        for p in s["points"]:
            assert p["form"] is None and p["accession"] is None

    def test_a_session_reading_says_where_it_came_from(self):
        ctx = {"measures": {"m": {
            "current": {"status": "known", "value": 1.0},
            "series": {"cadence": "daily", "points": [
                {"period_end": "2026-03-02", "filed": "2026-03-02",
                 "form": None, "accession": None, "value": 4.0,
                 "reason": None, "cautions": [], "provenance": []}]}}}}
        got = contract._measure_observation(
            ctx, {"measure": "m", "at": "2026-03-02"})[0]
        assert "the close of 2026-03-02" in got["provenance"][0]
        assert "filed" not in got["provenance"][0]

    def test_no_price_history_says_what_to_fetch(self):
        s = _series(924, [], "2026-03-06")["price_to_book"]
        assert s["points"] == []
        assert "trading days" in s["note"] and "price history" in s["note"]


class TestTheClockIsTheHostsWordAndNotAStrategys:
    def test_a_quoted_measure_counts_trading_days(self):
        est = contract.estimator_of("peg_trailing")
        assert est["clock"] == "sessions"
        assert est["counts"] == "trading days"
        assert est["counts_one"] == "trading day"

    def test_a_filing_measure_counts_filings(self):
        est = contract.estimator_of("current_ratio")
        assert est["clock"] == "filings"
        assert est["counts"] == "filings"

    def test_every_estimator_kind_names_a_clock_the_host_knows(self):
        for kind, spec in contract.ESTIMATORS.items():
            assert spec["clock"] in contract.CLOCKS, kind

    def test_no_shipped_strategy_writes_the_unit_itself(self):
        """The noun belongs to the host. Three bundles used to write
        "consecutive filings" into their own reasons — a strategy stating a
        fact about machinery it does not own, and false the day a second clock
        existed."""
        import pathlib
        for p in pathlib.Path("strategies").glob("*/strategy.py"):
            src = p.read_text(encoding="utf-8")
            for line in src.splitlines():
                if "consecutive filings" not in line:
                    continue
                # narrative prose about a measure that genuinely is on the
                # filing clock is fine; a formatted count is not
                assert "needs" not in line and "{f[" not in line, \
                    f"{p}: {line.strip()}"


class TestTheBankCannotDeclareTheWrongClock:
    """The one contradiction between a declaration and the arithmetic under it
    that can be settled exactly — so it is refused at load rather than pinned
    by a test that only runs under pytest. The bank is a file the program
    re-reads when its mtime moves.
    """

    def _bank_with(self, tmp_path, monkeypatch, entry_id, kind):
        import copy
        doc = copy.deepcopy(bank.load_bank())
        for e in doc["entries"]:
            if str(e.get("id")) == entry_id:
                e["estimator"]["kind"] = kind
        import ruamel.yaml
        y = ruamel.yaml.YAML()
        with open(tmp_path / "probe.yaml", "w", encoding="utf-8") as f:
            y.dump(doc, f)
        monkeypatch.setattr(bank, "CONFIG_DIR", tmp_path)
        bank._bank_cache.clear()
        return "probe"

    def test_a_price_entry_declared_as_a_filing_reading_is_refused(
            self, tmp_path, monkeypatch):
        name = self._bank_with(tmp_path, monkeypatch, "price_to_book",
                               "instant")
        with pytest.raises(ValueError, match="reads a quoted price"):
            bank.load_bank(name)

    def test_a_filing_entry_declared_quoted_is_refused(self, tmp_path,
                                                       monkeypatch):
        name = self._bank_with(tmp_path, monkeypatch, "current_ratio",
                               "quoted")
        with pytest.raises(ValueError, match="reads no price"):
            bank.load_bank(name)

    def test_the_shipped_bank_agrees_with_its_own_formulas(self):
        priced = compute.price_driven_entries()
        assert len(priced) == 20, sorted(priced)
        for eid in compute.REGISTRY:
            est = contract.estimator_of(eid) or {}
            assert (est.get("kind") == "quoted") == (eid in priced), eid

    def test_every_price_door_the_context_offers_is_watched(self):
        """The derivation is only exact while every price arrives through a
        door it knows about. A third one added to Ctx without being named
        here would make a price-bearing entry look price-free."""
        doors = {n for n in dir(compute.Ctx)
                 if n.startswith("price_") and callable(
                     getattr(compute.Ctx, n))}
        assert doors - {"price_dates_served"} == set(compute._PRICE_DOORS)


class TestAStreakThatRunsOffTheRecord:
    """A streak that reaches the edge of the recorded filings without
    breaking is a floor, not a point. Served as a point it fails any test
    asking for more years than the record holds — a fifty-seven-year payer
    with thirteen machine-readable years FAILS a twenty-year requirement,
    which is a false fail on a knockout. The bound is part of the value and
    the comparison consumes it (contract._bounded_outcome); a caution would
    only have been read by a person and ignored by the arithmetic."""

    def _paying(self, first, last):
        return years({y: 1_000_000 for y in range(first, last + 1)},
                     concept="us-gaap:PaymentsOfDividends")

    def test_the_run_off_the_edge_is_bounded_not_asserted(self):
        r = one(self._paying(2018, 2025), "consecutive_dividend_years")
        assert r["status"] == "computed"
        assert r["value"] == 8
        assert r["bound"] == "at_least"
        assert "oldest fiscal year held" in r["bound_reason"]

    def test_a_streak_the_record_ends_is_a_plain_point(self):
        filings = years(
            {**{y: 1_000_000 for y in range(2020, 2026)}, 2019: 0},
            concept="us-gaap:PaymentsOfDividends")
        r = one(filings, "consecutive_dividend_years")
        assert r["status"] == "computed"
        assert r["value"] == 6
        assert "bound" not in r

    def test_the_bound_survives_to_the_strategy_context(self):
        from engine import dataview
        r = one(self._paying(2018, 2025), "consecutive_dividend_years")
        node = dataview.resolve({"ticker": "SYN"},
                                {"consecutive_dividend_years": r})
        got = node["consecutive_dividend_years"]
        assert got["bound"] == "at_least"
        assert got["bound_reason"] == r["bound_reason"]
