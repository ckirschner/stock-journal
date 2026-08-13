"""Per-filing series: the behaviours that would fail silently.

A filing boundary counted twice, an amendment rewriting a period that was
already read, a same-day catch-up batch reading as several separate
observations, a stale close pinned to the wrong day, an entry with no
cadence quietly getting no series at all — none of these crash. They produce
plausible wrong readings, so each one is pinned here with deliberately
awkward filing sequences.

This is the series a strategy reads through `measures[id].series`. What a
strategy then *does* with a run of readings — count it, require N of them,
reset on a clear one — is the strategy's own logic and is tested against the
contract, not here. The host's job is that the readings themselves are
right, in the right order, and honest about what could not be read.
"""

from conftest import balance_face, filing, inst, no_filer, symbols

from engine import price_store
from engine.compute import (CADENCE, REGISTRY, Ctx, confirmation_boundaries,
                            confirmation_history)


def rd(period_end, filed, value, reason=None, form="10-K", accession="A-1",
       priced=None):
    return {"period_end": period_end, "filed": filed, "accession": accession,
            "form": form, "value": value, "reason": reason, "priced": priced}


# -- boundaries -------------------------------------------------------------

def _f(accession, form, filed, period):
    return filing(accession, form, filed, period, [])


class TestBoundaries:
    def test_each_new_period_is_a_boundary_and_amendments_are_not(self):
        fs = [_f("K1", "10-K", "2025-02-20", "2024-12-31"),
              _f("Q1", "10-Q", "2025-05-10", "2025-03-31"),
              _f("K1A", "10-K/A", "2025-06-01", "2024-12-31"),
              _f("Q2", "10-Q", "2025-08-08", "2025-06-30")]
        got = confirmation_boundaries(fs, "quarterly")
        assert [b["accession"] for b in got] == ["K1", "Q1", "Q2"]

    def test_a_same_day_catch_up_batch_is_one_observation(self):
        """A delinquent filer posting three quarters at once produced one
        moment of new information, not three chances to confirm a breach."""
        fs = [_f("Q1", "10-Q", "2025-06-15", "2024-09-30"),
              _f("Q2", "10-Q", "2025-06-15", "2024-12-31"),
              _f("Q3", "10-Q", "2025-06-15", "2025-03-31")]
        got = confirmation_boundaries(fs, "quarterly")
        assert len(got) == 1
        assert got[0]["period_end"] == "2025-03-31"

    def test_a_late_filed_old_quarter_is_not_a_boundary(self):
        fs = [_f("K1", "10-K", "2025-03-01", "2024-12-31"),
              _f("Q2-OLD", "10-Q", "2025-05-01", "2024-06-30")]
        got = confirmation_boundaries(fs, "quarterly")
        assert [b["accession"] for b in got] == ["K1"]

    def test_annual_cadence_ignores_quarterly_reports(self):
        fs = [_f("K1", "10-K", "2025-02-20", "2024-12-31"),
              _f("Q1", "10-Q", "2025-05-10", "2025-03-31"),
              _f("Q2", "10-Q", "2025-08-08", "2025-06-30"),
              _f("K2", "10-K", "2026-02-19", "2025-12-31")]
        got = confirmation_boundaries(fs, "annual")
        assert [b["accession"] for b in got] == ["K1", "K2"]

    def test_an_amendment_only_annual_period_still_counts_once(self):
        """The original never extracted; the amendment is the first filing to
        deliver that fiscal year, so it is the observation for it — but a
        second amendment adds nothing."""
        fs = [_f("K1", "10-K", "2024-02-20", "2023-12-31"),
              _f("K2A", "10-K/A", "2025-06-01", "2024-12-31"),
              _f("K2AA", "10-K/A", "2025-07-01", "2024-12-31")]
        got = confirmation_boundaries(fs, "annual")
        assert [b["accession"] for b in got] == ["K1", "K2A"]

    def test_undated_filings_are_never_boundaries(self):
        fs = [_f("K1", "10-K", "2025-02-20", "2024-12-31"),
              filing("X", "10-K", None, "2025-12-31", [])]
        got = confirmation_boundaries(fs, "annual")
        assert [b["accession"] for b in got] == ["K1"]


# -- per-filing readings from real stores -----------------------------------

def _quarter(accession, filed, period, ca, cl=100.0):
    extra = [inst("us-gaap:AssetsCurrent", period, ca)]
    if cl is not None:
        extra.append(inst("us-gaap:LiabilitiesCurrent", period, cl))
    return filing(accession, "10-Q", filed, period,
                  balance_face(period, extra=extra))


class TestHistoryReadings:
    def test_readings_are_per_filing_and_newest_first(self):
        fs = [_quarter("Q1", "2025-05-10", "2025-03-31", 200.0),
              _quarter("Q2", "2025-08-09", "2025-06-30", 150.0),
              _quarter("Q3", "2025-11-08", "2025-09-30", 110.0)]
        h = confirmation_history(fs, None, symbols("SYN"), "current_ratio",
                                 industry=no_filer())
        assert h["cadence"] == "quarterly"
        vals = [(r["period_end"], r["value"]) for r in h["readings"]]
        assert vals == [("2025-09-30", 1.1), ("2025-06-30", 1.5),
                        ("2025-03-31", 2.0)]

    def test_a_later_amendment_cannot_rewrite_an_earlier_reading(self):
        """The reading at a boundary is what was observable when that filing
        arrived; a restating amendment filed later is invisible to it."""
        fs = [_quarter("Q1", "2025-05-10", "2025-03-31", 200.0),
              _quarter("Q2", "2025-08-09", "2025-06-30", 150.0),
              {**_quarter("Q1A", "2025-09-01", "2025-03-31", 50.0),
               "form": "10-Q/A"}]
        h = confirmation_history(fs, None, symbols("SYN"), "current_ratio",
                                 industry=no_filer())
        by_period = {r["period_end"]: r for r in h["readings"]}
        assert by_period["2025-03-31"]["value"] == 2.0
        assert by_period["2025-03-31"]["accession"] == "Q1"

    def test_an_uncomputable_boundary_is_an_honest_gap(self):
        fs = [_quarter("Q1", "2025-05-10", "2025-03-31", 200.0),
              _quarter("Q2", "2025-08-09", "2025-06-30", 150.0, cl=None),
              _quarter("Q3", "2025-11-08", "2025-09-30", 110.0)]
        h = confirmation_history(fs, None, symbols("SYN"), "current_ratio",
                                 industry=no_filer())
        bad = [r for r in h["readings"] if r["period_end"] == "2025-06-30"][0]
        assert bad["value"] is None
        assert bad["reason"]

    def test_no_filings_says_so(self):
        h = confirmation_history([], None, symbols("SYN"), "current_ratio",
                                 industry=no_filer())
        assert h["readings"] == []
        assert "no filings are stored" in h["note"]

    def test_an_undated_filing_enters_no_as_of_prefix(self):
        """A filing that cannot be placed in time is no boundary (tested
        above) and must not leak into other boundaries' readings either —
        every prefix reading would silently reflect it."""
        undated = _quarter("X", None, "2025-06-30", 50.0)
        fs = [_quarter("Q1", "2025-05-10", "2025-03-31", 200.0), undated]
        h = confirmation_history(fs, None, symbols("SYN"), "current_ratio",
                                 industry=no_filer())
        assert len(h["readings"]) == 1
        assert h["readings"][0]["accession"] == "Q1"
        assert h["readings"][0]["value"] == 2.0

    def test_no_price_lookup_in_compute_bypasses_the_context(self):
        """Under a price_cutoff every close must come through Ctx, or an
        as-of reading silently prices at today (the multi-class market-cap
        path did exactly that). The one allowed call lives inside Ctx.

        It was two. The second belonged to a reader that took every symbol
        mapped to the company and kept the newest close, which is gone —
        there is no longer any way to ask this module for "the company's
        price" without naming one instrument.
        """
        from pathlib import Path

        import engine.compute as compute_mod
        src = Path(compute_mod.__file__).read_text(encoding="utf-8")
        assert src.count("price_store.latest_close(") == 1

    def test_price_cutoff_reaches_per_class_prices(self):
        doc = price_store.load(3)
        price_store.merge_series(doc, "SYNB", "tiingo",
                                 [["2025-01-02", 10.0, 0],
                                  ["2025-06-30", 99.0, 0]], [])
        ctx = Ctx([], doc, symbols("SYN"), price_cutoff="2025-01-05",
                  industry=no_filer())
        got = ctx.price_for("SYNB")
        assert got == ("2025-01-02", 10.0, 3)
        assert "2025-01-02" in ctx.price_dates_served

    def test_an_unknown_entry_says_so(self):
        h = confirmation_history([], None, symbols("SYN"), "no_such_entry",
                                 industry=no_filer())
        assert h["readings"] == []
        assert "no computation" in h["note"]


class TestPricePinning:
    def _prices(self):
        doc = price_store.load(1)
        price_store.merge_series(doc, "SYN", "tiingo",
                                 [["2025-01-02", 10.0, 0],
                                  ["2025-06-30", 20.0, 0]], [])
        return doc

    def test_price_cutoff_serves_the_close_of_that_day_not_the_newest(self):
        ctx = Ctx([], self._prices(), symbols("SYN"), price_cutoff="2025-01-05",
                  industry=no_filer())
        got = ctx.price_for("SYN")
        assert got[1] == 10.0 and got[0] == "2025-01-02"
        assert "2025-01-02" in ctx.price_dates_served

    def test_without_a_cutoff_the_newest_close_serves(self):
        ctx = Ctx([], self._prices(), symbols("SYN"), industry=no_filer())
        assert ctx.price_for("SYN")[1] == 20.0

    def test_a_cutoff_before_the_whole_series_is_absent_not_borrowed(self):
        """Never reach forward. A close after the day being rebuilt for is a
        price from a world that day had not seen, and it is the one direction
        that is always wrong — unlike reaching back, which is how far the
        answer is, not whether there is one."""
        ctx = Ctx([], self._prices(), symbols("SYN"), price_cutoff="2024-01-01",
                  industry=no_filer())
        assert ctx.price_for("SYN") is None


# -- cadence ----------------------------------------------------------------

_QUARTERLY_HELPERS = {"ttm", "ttm_at", "instant_latest", "instant_pair_yoy",
                      "quarterly_observation_fis",
                      "newest_quarterly_after_annual", "latest_fi",
                      "latest_balance_fi"}
_ANNUAL_HELPERS = {"annual_window", "instant_series_annual", "annual_points",
                   "latest_annual_fi", "latest_fiscal_years"}


class _RecordingSB:
    def __init__(self, sb):
        object.__setattr__(self, "_sb", sb)
        object.__setattr__(self, "touched", set())

    def __getattr__(self, name):
        attr = getattr(self._sb, name)
        if callable(attr):
            def wrapped(*a, **k):
                self.touched.add(name)
                return attr(*a, **k)
            return wrapped
        return attr


def _rich_company():
    from conftest import dur
    fs = []
    for i, year in enumerate((2022, 2023, 2024)):
        end, start = f"{year}-12-31", f"{year}-01-01"
        facts = [
            dur("us-gaap:Revenues", start, end, 1000 + i),
            dur("us-gaap:NetIncomeLoss", start, end, 100 + i),
            dur("us-gaap:NetCashProvidedByUsedInOperatingActivities",
                start, end, 200, stmt="CashFlowStatement"),
            dur("us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",
                start, end, 50, stmt="CashFlowStatement"),
            dur("us-gaap:EarningsPerShareDiluted", start, end, 2.0,
                unit="usdPerShare", decimals=2),
            dur("us-gaap:PaymentsOfDividendsCommonStock", start, end, 20,
                stmt="CashFlowStatement"),
        ] + balance_face(end, extra=[
            inst("us-gaap:AssetsCurrent", end, 200),
            inst("us-gaap:LiabilitiesCurrent", end, 100),
            inst("us-gaap:StockholdersEquity", end, 400),
            inst("us-gaap:LongTermDebtNoncurrent", end, 100),
        ])
        fs.append(filing(f"K{year}", "10-K", f"{year + 1}-02-20", end, facts))
    q_end = "2025-03-31"
    fs.append(filing("Q1-2025", "10-Q", "2025-05-10", q_end,
                     [dur("us-gaap:Revenues", "2025-01-01", q_end, 260),
                      # A cover share count, so the price-bearing formulas
                      # reach a price instead of refusing above it. Without
                      # one, every entry on the session clock bails at
                      # `_cover_shares` and the probe below reports that it
                      # touched only filing helpers — a derivation that
                      # agrees with the wrong answer because the fixture was
                      # too thin to disagree.
                      {**inst("dei:EntityCommonStockSharesOutstanding",
                              q_end, 50.0, stmt=None),
                       "unit": "shares", "currency": None}]
                     + balance_face(q_end, extra=[
                         inst("us-gaap:AssetsCurrent", q_end, 210),
                         inst("us-gaap:LiabilitiesCurrent", q_end, 105),
                     ])))
    return fs


class TestCadence:
    def test_every_computed_entry_declares_a_cadence(self):
        assert set(CADENCE) == set(REGISTRY)
        assert set(CADENCE.values()) <= {"annual", "quarterly", "daily"}

    def test_declared_cadence_matches_what_the_formula_touches(self):
        """The table is a claim about each formula; this derives the fact
        from the formula itself.

        Three clocks now, and the price one is deliberately NOT derived
        here. Running a formula only shows what it reached before it
        refused, and every price-bearing entry refuses somewhere above its
        price on a fixture missing one input — `altman_z_score` needs an
        EBIT it has not got, and comes back looking price-free. A derivation
        that goes blind exactly when the fixture thins is one that agrees
        with a wrong declaration, so the price leg is settled statically by
        `compute.price_driven_entries` and enforced at bank load. This
        checks the filing arm, where the helpers are called at the top of
        every formula and running it is the honest test.
        """
        doc = price_store.load(2)
        price_store.merge_series(doc, "SYN", "tiingo",
                                 [["2025-05-12", 100.0, 0]], [])
        fs = _rich_company()
        untested = []
        for eid, fn in sorted(REGISTRY.items()):
            ctx = Ctx(fs, doc, symbols("SYN"), industry=no_filer())
            rec = _RecordingSB(ctx.sb)
            ctx.sb = rec
            try:
                fn(ctx)
            except Exception:       # noqa: BLE001 — touches already recorded
                pass
            if CADENCE[eid] == "daily":
                continue            # settled statically; see the docstring
            q = rec.touched & _QUARTERLY_HELPERS
            a = rec.touched & _ANNUAL_HELPERS
            if not q and not a:
                untested.append(eid)
                continue
            want = "quarterly" if q else "annual"
            assert CADENCE[eid] == want, \
                f"{eid}: declared {CADENCE[eid]}, touched {sorted(rec.touched)}"
        # Only entries that never consult period data (separate ingestion
        # paths) may go unclassified; anything else escaping the check would
        # gut the test silently.
        assert set(untested) <= {"insider_net_buying_6m",
                                 "institutional_ownership_pct"}, untested


# -- the cached provider ----------------------------------------------------

class TestDataviewProvider:
    def test_histories_are_cached_per_entry(self):
        """One reading of one entry is one answer. There used to be a second
        cache dimension for a computation's supplied parameters, and nothing
        supplied any — the one measure that declared a parameter could never
        receive it, so it never once computed. A measure needing a number
        nobody can hand over is not a measure; it is a strategy's question,
        and it went there."""
        from engine import compute, dataview, facts_store
        cik = 777
        for f in [_quarter("Q1", "2025-05-10", "2025-03-31", 200.0),
                  _quarter("Q2", "2025-08-09", "2025-06-30", 150.0)]:
            facts_store.save_filing(cik, f)
        dataview.invalidate(cik)
        h1 = dataview.confirmation_history(cik, ["SYN"], "current_ratio")
        assert [r["value"] for r in h1["readings"]] == [1.5, 2.0]
        assert dataview.confirmation_history(cik, ["SYN"],
                                             "current_ratio") is h1
        assert dataview.confirmation_history(
            cik, ["SYN"], "price_to_book") is not h1
        # And no computation is waiting on a figure nobody supplies: the
        # channel is gone, so a new one cannot be quietly added to it.
        assert not hasattr(
            compute.Ctx([], None, symbols("SYN"), industry=no_filer()), "params")
        assert not hasattr(compute, "compute_entry_with_params")
