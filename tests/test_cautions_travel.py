"""A qualified number is never handed over bare.

Some figures rest on something the reader has to be told about: a share class
valued at a sibling's close, a balance-sheet line matched by its label rather
than by a mapped concept, a price too old to be current. The host says so in
`cautions`, and this file holds the rule that the sentence goes wherever the
number goes — onto the screen, into an append-only snapshot, and through a
per-filing series point.

The snapshot is the serious one. A frozen record is written once and never
recomputed, so a caution dropped on the way in is dropped forever, and the
record then states a figure as more certain than the evidence supported. That
is not a display gap; it is the audit trail asserting something nothing ever
established.

Market capitalization drives most of these, on purpose. It is the one
admitted approximation in the compute layer, it was kept on the explicit
condition that its qualification reaches the reader, and it feeds P/E,
enterprise value, dividend yield and both cash-to-cap ratios — so a caution
lost here is lost from a third of the bank at once.
"""

import itertools

import pytest
from conftest import (MULTICLASS_PRICED, MULTICLASS_UNPRICED, journal_for,
                      multiclass_company)

from engine import dataview, journals

from app import Api

_CIK = itertools.count(7100)


class TestTheMarketCapChain:
    """The specific chain the blend was kept on: which classes were blended,
    what share of the company was assumed, and how stale the oldest close in
    it is — reaching the reader at every stop."""

    @pytest.fixture(autouse=True)
    def _journal(self, strategies):
        strategies("qualified")
        journal_for("qualified", "Chain")

    def _seed(self, closes=None):
        cik = next(_CIK)
        multiclass_company(cik, closes)
        api = Api()
        assert api.add_security("SYN", "Synthetic Co")["ok"]
        journal = journals.load(journals.resolve_open())
        journal["securities"][0]["cik"] = cik
        journals.save(journal)
        return api

    def _blend_note(self, cautions):
        return next((c for c in cautions if "no stored close" in c), None)

    def test_the_engine_states_all_three_things(self):
        """Read once at the source, so the tests below are about the trip and
        not about whether there was anything to carry."""
        api = self._seed(closes=[("2024-01-02", 20.0)])   # deliberately old
        s = api.get_state()["securities"][0]
        cautions = s["_computed"]["market_cap"]["cautions"]
        blend = self._blend_note(cautions)
        assert blend is not None
        assert "Class B" in blend                       # which class
        assert "10.0% of the share count" in blend      # how much of it
        assert "SYN close of 2024-01-02" in blend       # valued at whose
        assert "assumption" in blend and "not a measurement" in blend
        # The price's age, stated always rather than only past some line the
        # host had picked. A six-day-old close used to say nothing about its
        # age and an eight-day-old one did, so "no age mentioned" meant
        # either current or nobody asked, and the reader could not tell.
        age = next(c for c in cautions if "priced at the close of" in c)
        assert "2024-01-02" in age and "days before today" in age

    def test_it_reaches_the_screen_with_the_value(self):
        api = self._seed()
        s = api.get_state()["securities"][0]
        entry = s["_computed"]["market_cap"]
        assert entry["status"] == "computed"
        assert entry["value"] == (MULTICLASS_PRICED
                                  + MULTICLASS_UNPRICED) * 20.0
        assert self._blend_note(entry["cautions"])

    def test_it_reaches_the_data_page(self):
        api = self._seed()
        rows = api.get_coverage("SYN")["coverage"]["entries"]
        row = next(r for r in rows if r["id"] == "market_cap")
        assert self._blend_note(row["cautions"])

    def test_it_reaches_the_strategys_evidence(self):
        """The strategy cites; the host answers. The answer carries what
        qualified the figure, because a strategy may never restate it."""
        api = self._seed()
        d = api.get_state()["securities"][0]["_decision"]
        cited = [e for e in d["reason"]["evidence"]
                 if e["subject"]["id"] == "market_cap" and "at" not in
                 e["subject"]]
        assert cited, d
        assert self._blend_note(cited[0]["observed"]["cautions"])

    def test_it_reaches_a_reading_cited_at_a_past_period(self):
        """A per-filing series point is a reading of the same measure and is
        qualified the same way. This was the one route that returned the
        number alone."""
        api = self._seed()
        d = api.get_state()["securities"][0]["_decision"]
        at = [e for e in d["reason"]["evidence"]
              if e["subject"]["id"] == "market_cap" and "at" in e["subject"]]
        assert at, d
        assert self._blend_note(at[0]["observed"]["cautions"])

    def test_it_is_frozen_into_the_purchase_record(self):
        """The correctness half. This record can never be asked again."""
        api = self._seed()
        assert api.open_position("SYN", 5, 9.5, "2025-06-30", "in")["ok"]
        journal = journals.load(journals.resolve_open())
        snap = journal["securities"][0]["lots"][-1]["snapshot"]
        frozen = snap["metrics"]["market_cap"]
        assert frozen["value"] is not None
        assert self._blend_note(frozen["cautions"])
        assert frozen["provenance"]
        # and inside the frozen decision, where the verdict's own figures are
        cited = [e for e in snap["decision"]["reason"]["evidence"]
                 if e["subject"]["id"] == "market_cap"]
        assert cited and all(self._blend_note(e["observed"]["cautions"])
                             for e in cited)

    def test_it_is_frozen_into_the_sale_record_too(self):
        api = self._seed()
        assert api.open_position("SYN", 5, 9.5, "2025-06-30", "in")["ok"]
        assert api.sell_shares("SYN", "Panic", 12.0, "2025-07-30")["ok"]
        journal = journals.load(journals.resolve_open())
        snap = journal["securities"][0]["lots"][-1]["snapshot"]
        assert self._blend_note(snap["metrics"]["market_cap"]["cautions"])


class TestASnapshotRefusesABareNumber:
    """Structural rather than remembered. Three carriers dropped cautions by
    each holding a plain float; the shape that made that possible is gone,
    and the write refuses the old one."""

    def test_merged_values_stamp_the_banks_words_in_force(self):
        """What a purchase or a snapshot freezes carries the label and
        format the bank held THAT day, so a measure renamed afterwards
        cannot silently relabel history — the comparison screens read the
        frozen words first and consult today's bank only for records that
        predate the fields."""
        from engine import bank
        node = {"status": "computed", "value": 2.5,
                "provenance": ["a test sentence"], "cautions": []}
        got = dataview.merged_values({"ticker": "SYN"},
                                     {"current_ratio": node})
        meta = bank.meta()["current_ratio"]
        assert got["current_ratio"]["label"] == meta["label"]
        assert got["current_ratio"]["format"] == meta["format"]

    def test_a_qualified_value_has_exactly_the_six_parts(self):
        """Four qualifiers, plus the bank's words in force when the value
        was composed — the label and format keys are always present (None
        where the bank did not speak), so a frozen record can never be
        relabelled by today's bank without it being visible that the words
        were simply never stamped."""
        v = dataview.qualified(1.0, "computed", ["a caution"], ["a source"])
        assert set(v) == {"value", "source", "cautions", "provenance",
                          "label", "format"}
        assert v["label"] is None and v["format"] is None
        stamped = dataview.qualified(1.0, "computed", label="Market cap",
                                     format="$0,0")
        assert stamped["label"] == "Market cap"
        assert stamped["format"] == "$0,0"

    def test_the_snapshot_refuses_a_number_on_its_own(self):
        from engine import portfolio
        s = portfolio.new_security("SYN", "Synthetic Co")
        with pytest.raises(ValueError) as e:
            portfolio.add_lot(s, None, 1, 10.0, "2025-01-02",
                              values={"market_cap": 1000.0})
        assert "bare float" in str(e.value)


class TestThePriceSaysWhenItWasAPrice:
    """The host carries a price's date and never judges it.

    There were four rules for one question and no policy. Market cap
    mentioned a price's age only past seven days; the as-of path refused a
    close eight days out; live market value and weight said nothing at all;
    and a delisted series served its last close unmarked. Seven days is a
    judgement — it differs between a screen built on three-year average
    earnings and a rule about position size — and it belonged to nobody.

    What the host owes is the fact: which day the market last set this price,
    how long ago that was, and whether the series has ended. What is too old
    is the strategy's call, and `price.days_since_close` is what lets it make
    one.
    """

    # A strategy that asks for free cash, because weight and the account
    # total are the two figures this class is about and neither exists
    # without it — and a cash record for it to be worked out from.
    ANSWERS = {"stance": "building", "keeps-reserve": False, "first-buy": 4}

    @pytest.fixture(autouse=True)
    def _journal(self, strategies):
        strategies("awkward")
        journal_for("awkward", "Prices", inputs=dict(self.ANSWERS),
                    cash_opening=40000.0)

    def _held(self, closes, price=None):
        """One holding, priced from `closes`, with the position figures a
        sizing rule fires on."""
        from engine import facts_store, price_store
        cik = next(_CIK)
        multiclass_company(cik, closes)
        api = Api()
        assert api.add_security("SYN", "Synthetic Co")["ok"]
        journal = journals.load(journals.resolve_open())
        journal["securities"][0]["cik"] = cik
        journals.save(journal)
        assert api.open_position("SYN", 10, 5.0, None, "recording")["ok"]
        if price is not None:
            assert api.save_metrics("SYN", {}, price)["ok"]
        return api, cik, facts_store, price_store

    def test_the_age_is_stated_however_young_the_price_is(self):
        """Conditional was the worst of the three designs. A six-day-old
        close said nothing about its age and an eight-day-old one did, so
        "no age mentioned" meant either "this is current" or "nobody asked",
        and there is no way to tell those apart from a silence."""
        from datetime import date, timedelta
        fresh = (date.today() - timedelta(days=2)).isoformat()
        api, cik, *_ = self._held([(fresh, 20.0)])
        mcap = dataview.computed_results(cik, ["SYN"],
                                         ["market_cap"])["market_cap"]
        age = [c for c in mcap["cautions"] if "priced at the close of" in c]
        assert age and fresh in age[0], mcap
        # And the same on the position side, which is the other half of the
        # policy: two days is as much a fact about a weight as two months.
        ctx = _context_for(api, "SYN")
        for path in (("position", "market_value"), ("position", "weight")):
            node = ctx
            for step in path:
                node = node[step]
            assert any(fresh in c for c in node["cautions"]), path

    def test_weight_and_the_account_total_say_which_day_they_are_from(self):
        """The two figures a sizing rule actually binds on, and the two that
        said least about the price underneath them. A weight worked out from
        a two-month-old close and one from this morning's read identically —
        to the reader and to a strategy citing `position.weight`."""
        api, *_ = self._held([("2024-01-02", 20.0)])
        ctx = _context_for(api, "SYN")
        for path in (("position", "weight"),
                     ("position", "market_value"),
                     ("portfolio", "account_value")):
            node = ctx
            for step in path:
                node = node[step]
            assert node["status"] == "known", path
            assert any("2024-01-02" in c for c in node["cautions"]), path

    def test_a_strategy_can_count_the_days_and_the_host_will_not(self):
        """The load-bearing half. A date on its own does not let a strategy
        decide anything — it has a date and no way to subtract one — so the
        host offers the arithmetic it already owns, on the same footing as
        `position.months_held`, and holds no view about the answer."""
        from datetime import date, timedelta
        from engine import contract
        old = (date.today() - timedelta(days=40)).isoformat()
        api, *_ = self._held([(old, 20.0)])
        ctx = _context_for(api, "SYN")
        assert ctx["price"]["latest"]["days_since_close"] == 40
        assert contract.test(ctx, {"fact": "price.days_since_close",
                                   "comparator": "at_most",
                                   "threshold": 30}) == "fail"
        assert contract.test(ctx, {"fact": "price.days_since_close",
                                   "comparator": "at_most",
                                   "threshold": 60}) == "pass"
        # And nothing in the host has an opinion of its own about 40 days.
        from engine import compute
        assert not hasattr(compute, "STALE_PRICE_DAYS")

    def test_a_hand_entered_price_counts_no_days_rather_than_nought(self):
        """Nought would be a claim that the price is today's. Nothing here
        knows when it was typed, so the count is absent and says why — and
        the screen says it too, rather than leaving a reader to notice a
        blank where every other record shows a day."""
        api, *_ = self._held([("2024-01-02", 20.0)], price=31.5)
        ctx = _context_for(api, "SYN")
        assert ctx["price"]["latest"]["value"] == 31.5
        assert ctx["price"]["latest"]["days_since_close"] is None
        s = api.get_state()["securities"][0]
        assert "carries no date" in (s["_price"]["undated"] or "")

    def test_a_series_that_has_ended_says_so_wherever_its_price_appears(self):
        """A fact, not a judgement about age. A series quiet for a month and
        one that will never trade again are identical in a list of closes,
        and only one of them still has a price. It was stated on a tab a
        novice has no reason to open, and nowhere else — not on the price,
        not on what the holding is worth, not on its share of the account.
        """
        api, cik, _fs, ps = self._held([("2024-01-02", 20.0)])
        doc = ps.load(cik)
        ps.mark_terminal(doc, "SYN", "delisted")
        ps.save(cik, doc)
        dataview.invalidate(cik)

        s = api.get_state()["securities"][0]
        assert s["_price"]["value"] == 20.0, "the last close is still served"
        assert s["_price"]["terminal"]["reason"] == "delisted"

        ctx = _context_for(api, "SYN")
        assert ctx["price"]["latest"]["terminal"]["reason"] == "delisted"
        for path in (("position", "market_value"), ("position", "weight")):
            node = ctx
            for step in path:
                node = node[step]
            said = " ".join(node["provenance"] + node["cautions"])
            assert "has ended" in said and "delisted" in said, (path, said)

    def test_the_date_survives_the_crossing_into_a_strategys_evidence(self):
        """It did not. `_fact_observation` forwarded the value, the cautions
        and the provenance and dropped everything else, so the one node that
        carried a structured date lost it at the boundary — and a purchase
        snapshot is written once, so a fact dropped there is gone."""
        from engine import contract
        api, *_ = self._held([("2024-01-02", 20.0)])
        ctx = _context_for(api, "SYN")
        rendered, errors = contract.resolve_evidence(
            {"values": [], "inputs": []}, ctx, [{"fact": "price.latest"}])
        assert errors == []
        assert rendered[0]["observed"]["date"] == "2024-01-02"
        assert rendered[0]["observed"]["ticker"]


def _context_for(api, ticker):
    """The context a strategy is handed for one security, built the way the
    evaluator builds it — not assembled by hand, so what these tests assert
    is what a strategy actually receives."""
    from engine import context
    journal, record, chain, _ = api._open()
    security = next(s for s in journal["securities"]
                    if s["ticker"] == ticker)
    declared = {f["id"] for f in (record.get("inputs") or [])}
    supplied = {k: v for k, v in (journal.get("inputs") or {}).items()
                if k in declared}
    return context.build_context(security, journal["securities"],
                                 chain["values"], supplied, record=record,
                                 journal=journal)


class TestADeadSeriesReachesEveryFigureBuiltOnIt:
    """A terminal mark that reaches some price measures and not others.

    It was logged against `pe_ttm` and `pe_3y_avg_eps`, which dropped a mark
    `market_cap` carried, so one dead series read as current in two places and
    not in a third. That is closed — the pricing rework routed every
    whole-company figure through one blend, and the caution comes off it — but
    only by construction of the call graph, and nothing asserted the general
    property. A price measure added tomorrow that reads a close its own way
    would drop the mark again, silently, and the first sign of it would be a
    P/E on a delisted company reading like a live quote.

    So the property is the test: every entry the bank says reads a price, that
    computes at all against an ended series, says so. It cannot grow quietly —
    a new price-declaring entry is in the list the moment it declares one.
    """

    def _company(self, cik):
        from conftest import balance_face, dur, filing, inst
        from engine import price_store

        years = [(f"{y}-01-01", f"{y}-12-31") for y in range(2019, 2024)]
        out = []
        for i, (s, e) in enumerate(years):
            facts = [
                dur("us-gaap:Revenues", s, e, 1000.0),
                dur("us-gaap:NetIncomeLoss", s, e, 120.0),
                dur("us-gaap:OperatingIncomeLoss", s, e, 130.0),
                dur("us-gaap:EarningsPerShareDiluted", s, e, 1.2),
                dur("us-gaap:NetCashProvidedByUsedInOperatingActivities",
                    s, e, 200.0, stmt="CashFlowStatement"),
                dur("us-gaap:PaymentsToAcquirePropertyPlantAndEquipment",
                    s, e, 50.0, stmt="CashFlowStatement"),
                dur("us-gaap:PaymentsOfDividendsCommonStock", s, e, 30.0,
                    stmt="CashFlowStatement"),
                {**inst("dei:EntityCommonStockSharesOutstanding",
                        e[:4] + "-02-20", 100.0, stmt=None),
                 "unit": "shares", "currency": None},
            ] + balance_face(e, assets=2000.0, extra=[
                inst("us-gaap:StockholdersEquity", e, 800.0),
                inst("us-gaap:LongTermDebtNoncurrent", e, 100.0),
                inst("us-gaap:CashAndCashEquivalentsAtCarryingValue", e, 50.0),
                inst("us-gaap:RetainedEarningsAccumulatedDeficit", e, 400.0),
                inst("us-gaap:AssetsCurrent", e, 600.0),
                inst("us-gaap:LiabilitiesCurrent", e, 300.0),
            ])
            out.append(filing(f"D-{i}", "10-K", e[:4] + "-02-20", e, facts))

        doc = price_store.load(cik)
        price_store.merge_series(
            doc, "SYN", "test",
            [[f"{y}-02-20", 10.0, 100] for y in range(2019, 2025)], [])
        price_store.mark_terminal(doc, "SYN", "delisted in the ticker map")
        return out, doc

    def test_every_price_measure_that_computes_says_the_series_ended(self):
        from conftest import no_filer, symbols
        from engine import bank
        from engine.compute import compute_all

        filings, prices = self._company(9310)
        declares_a_price = [str(e.get("id"))
                            for e in bank.load_bank()["entries"]
                            if (e.get("inputs") or {}).get("prices")]
        assert len(declares_a_price) > 10, "the bank stopped declaring prices"

        results = compute_all(filings, prices, symbols("SYN"),
                              industry=no_filer(),
                              entry_ids=declares_a_price)
        computed = {eid: r for eid, r in results.items()
                    if r.get("status") == "computed"}
        # The control. A fixture that computed nothing would pass the
        # assertion below without exercising a single measure.
        assert len(computed) >= 10, sorted(computed)
        assert "pe_ttm" in computed and "market_cap" in computed

        silent = [eid for eid, r in computed.items()
                  if not any("series has ended" in c
                             for c in (r.get("cautions") or []))]
        assert silent == [], (
            "these price measures compute against an ended series and do not "
            "say so, so a delisted company's last close renders as a live "
            "quote in them: " + ", ".join(sorted(silent)))

    def test_the_mark_is_absent_when_the_series_is_alive(self):
        """The other direction, so the test above cannot pass by a caution
        that is always attached."""
        from conftest import no_filer, symbols
        from engine.compute import compute_all
        from engine import price_store

        filings, prices = self._company(9311)
        (prices.get("series") or {})["SYN"].pop("terminal", None)
        price_store.save(9311, prices)
        r = compute_all(filings, prices, symbols("SYN"), industry=no_filer(),
                        entry_ids=["pe_ttm", "market_cap"])
        for eid in ("pe_ttm", "market_cap"):
            assert r[eid]["status"] == "computed"
            assert not any("series has ended" in c
                           for c in r[eid]["cautions"]), eid
