"""Concept resolution: candidate order, face-disjoint aggregation, the
completeness rule's guard rails, and per-class cover shares."""

from conftest import dur, filing, inst, balance_face

from engine import concept_map as cm


def _fi(facts, form="10-K", period="2023-12-31"):
    return cm.FilingIndex(filing("X-1", form, "2024-02-01", period, facts))


class TestCandidates:
    def test_first_present_candidate_wins(self):
        fi = _fi([dur("us-gaap:Revenues", "2023-01-01", "2023-12-31", 500),
                  dur("us-gaap:SalesRevenueNet", "2023-01-01", "2023-12-31", 499)])
        r = cm.resolve_duration(fi, "revenue", "2023-01-01", "2023-12-31")
        # Revenues outranks the deprecated pre-606 tag in the chain
        assert r["concept"] == "us-gaap:Revenues"
        assert r["value"] == 500

    def test_cautioned_candidate_carries_its_caution(self):
        fi = _fi([dur("us-gaap:NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
                      "2023-01-01", "2023-12-31", 70, stmt="CashFlowStatement")])
        r = cm.resolve_duration(fi, "cfo", "2023-01-01", "2023-12-31")
        assert r["value"] == 70
        assert any("Continuing" in c or "continuing" in c for c in r["cautions"])

    def test_refused_concepts_never_serve(self):
        # PaymentsForCapitalImprovements is a measured wrong answer for capex
        fi = _fi([dur("us-gaap:PaymentsForCapitalImprovements",
                      "2023-01-01", "2023-12-31", 121, stmt="CashFlowStatement")])
        r = cm.resolve_duration(fi, "capex", "2023-01-01", "2023-12-31")
        assert cm.is_absent(r)
        assert "value" not in r
        # And says which way it failed. A concept the map deliberately does
        # not accept is a different fact from a filer that tagged nothing —
        # the first is a decision this program made, the second is a gap.
        assert "no concept this program maps to" in r["reason"]


class TestAggregates:
    def test_face_lines_sum_and_are_recorded(self):
        d = "2023-12-31"
        fi = _fi(balance_face(d, extra=[
            inst("us-gaap:CommercialPaper", d, 5),
            inst("us-gaap:LongTermDebtCurrent", d, 7),
            inst("us-gaap:LongTermDebtNoncurrent", d, 88),
        ]))
        r = cm.resolve_instant(fi, "total_debt", d)
        assert r["value"] == 100
        assert {p["concept"] for p in r["parts"]} == {
            "us-gaap:CommercialPaper", "us-gaap:LongTermDebtCurrent",
            "us-gaap:LongTermDebtNoncurrent"}

    def test_note_facts_never_enter_an_aggregate(self):
        """A debt concept tagged in the notes (not the face) must not sum —
        note disclosures overlap the face and would double count."""
        d = "2023-12-31"
        fi = _fi(balance_face(d, extra=[
            inst("us-gaap:LongTermDebtNoncurrent", d, 88),
            inst("us-gaap:SecuredDebt", d, 88, stmt="Notes"),
        ]))
        r = cm.resolve_instant(fi, "total_debt", d)
        assert r["value"] == 88

    def test_extension_debt_line_included_by_label_loudly(self):
        """The measured REIT case: an extension-tagged revolver line on the
        face is summed, marked uncertain, and says so."""
        d = "2023-12-31"
        fi = _fi(balance_face(d, extra=[
            inst("o:LineOfCreditAndCommercialPaper", d, 1130,
                 label="Line of credit payable and commercial paper"),
            inst("us-gaap:NotesPayable", d, 22657, label="Notes payable, net"),
        ]))
        r = cm.resolve_instant(fi, "total_debt", d)
        assert r["value"] == 1130 + 22657
        pattern_parts = [p for p in r["parts"]
                         if p["matched_by"] == "label_pattern"]
        assert [p["concept"] for p in pattern_parts] == \
            ["o:LineOfCreditAndCommercialPaper"]
        assert any("label match" in c for c in r["cautions"])

    def test_debt_free_face_is_zero_by_completeness(self):
        d = "2023-12-31"
        fi = _fi(balance_face(d, extra=[inst("us-gaap:AssetsCurrent", d, 400)]))
        r = cm.resolve_instant(fi, "total_debt", d)
        assert r["value"] == 0
        assert r["matched"] == "zero_by_completeness"

    def test_no_face_means_no_zero(self):
        """Without a located balance-sheet face there is no completeness
        argument: absence stays absent."""
        d = "2023-12-31"
        fi = _fi([inst("us-gaap:StockholdersEquity", d, 50,
                       stmt="StatementOfEquity")])
        assert cm.resolve_instant(fi, "total_debt", d) is None

    def test_rollforward_dates_are_not_a_face(self):
        """Equity-rollforward facts arrive tagged BalanceSheet at extra dates.
        Those dates carry no statement totals, so they must never count as a
        located face — this exact case once produced a confident zero debt."""
        d_real, d_roll = "2023-12-31", "2021-12-31"
        fi = _fi(balance_face(d_real, extra=[
            inst("us-gaap:LongTermDebtNoncurrent", d_real, 88),
            inst("us-gaap:StockholdersEquity", d_roll, 40),  # rollforward
        ]))
        assert d_roll not in fi.balance_dates()
        assert cm.resolve_instant(fi, "total_debt", d_roll) is None


class TestCoverShares:
    def test_single_class(self):
        fi = _fi([{**inst("dei:EntityCommonStockSharesOutstanding",
                          "2024-01-25", 7_433_038_381, stmt=None),
                   "unit": "shares", "currency": None}])
        r = cm.resolve_cover_shares(fi)
        assert r["total"] == 7_433_038_381
        assert r["classes"] is None

    def test_multi_class_kept_per_class_with_symbols(self):
        axis = "us-gaap:StatementClassOfStockAxis"
        def cls(member, shares, symbol):
            out = [{**inst("dei:EntityCommonStockSharesOutstanding",
                           "2025-01-28", shares, stmt=None),
                    "unit": "shares", "currency": None,
                    "dimensions": {axis: member}}]
            if symbol:
                out.append({**inst("dei:TradingSymbol", "2025-01-28", 0,
                                   stmt=None),
                            "value": symbol, "unit": None, "currency": None,
                            "dimensions": {axis: member}})
            return out
        facts = (cls("us-gaap:CommonClassAMember", 5.833e9, "GOOGL")
                 + cls("us-gaap:CommonClassBMember", 8.6e8, None)
                 + cls("us-gaap:CommonClassCMember", 5.497e9, "GOOG"))
        r = cm.resolve_cover_shares(_fi(facts))
        assert len(r["classes"]) == 3
        by_member = {c["member"]: c for c in r["classes"]}
        assert by_member["us-gaap:CommonClassAMember"]["symbol"] == "GOOGL"
        assert by_member["us-gaap:CommonClassBMember"]["symbol"] is None
        assert r["total"] == 5.833e9 + 8.6e8 + 5.497e9
