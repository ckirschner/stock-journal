"""Citing how far a measure has moved since one of your own purchases.

The two baselines are the only place in the contract where the host does
arithmetic *between* two of its own figures, and that is the whole reason
they exist. A strategy can already reach a frozen reading and a current one
and take one from the other — what it cannot do is cite the answer, because
an evidence item compares an observation against a limit, and a limit is a
number stated outright or the id of a setting. "At least five points below
what it was when you bought" is neither.

So what is pinned here is what would go wrong *quietly* if the host did not
own that subtraction:

- a change in a percentage rendered as a percentage. Forty per cent to
  thirty-four is six points, not six per cent, and "6%" beside a margin
  reads as the margin. A reader sanity-checking it gets a plausible answer
  and moves on.
- absence coming out as anything but unknown. Three different things can be
  missing — the purchase, the reading at it, the reading now — and each one
  says which, because "we could not compare" and "there is nothing to
  compare against" send a reader to different places.
- the two anchors quietly becoming one. They answer different questions and
  the day they part company is the day of the second purchase; a test that
  only ever exercises a singly-bought position would never notice them being
  wired to the same lot.
- the baseline being recomputed rather than read. That one is checked where
  the record lives, in tests/test_position_baselines.py — here the context is
  hand-built, so what is checked is that the host reads what it is handed and
  states nothing of its own.
"""

import pytest

from engine import contract

MARGIN = "gross_margin_ttm"      # a percent measure in the shipped bank
RATIO = "current_ratio"          # a ratio measure
YEARS = "consecutive_dividend_years"


def known(value, cautions=(), source="computed"):
    return {"status": "known", "value": value, "source": source,
            "cautions": list(cautions), "provenance": []}


def absent(reason):
    return {"status": "absent", "reason": reason}


def anchor(when, values, lot="l1"):
    return {"status": "known", "date": when, "lot": lot,
            "measures": {mid: (v if isinstance(v, dict) else known(v))
                         for mid, v in values.items()}}


def ctx(now=None, first=None, last=None, values=None):
    """A context with only what a baseline citation reads. Everything else a
    strategy is handed is exercised in tests/test_context.py; a smaller
    context here makes it obvious which figure a failure is about."""
    now = now or {}
    return {
        "contract": contract.CONTRACT_VERSION,
        "today": "2026-08-09",
        "measures": {mid: {"current": (v if isinstance(v, dict) else known(v)),
                           "series": {"cadence": None, "points": [],
                                      "note": None, "truncated": False}}
                     for mid, v in now.items()},
        "position": {
            "held": True, "shares": 100.0, "opened": "2024-02-01",
            "last_purchase": "2025-11-14", "purchases": 2,
            "baselines": {
                "first-purchase": first if first is not None
                else absent("no position is held, so there is no purchase to "
                            "measure from"),
                "last-purchase": last if last is not None
                else absent("no position is held, so there is no purchase to "
                            "measure from"),
            }},
        "portfolio": {}, "values": values or {}, "inputs": {},
    }


RECORD = {
    "id": "probe", "name": "Probe", "summary": "a bundle for these tests",
    "version": 1, "contract": contract.CONTRACT_VERSION,
    "changelog": {1: "first"},
    "states": [{"id": "watch", "render": "hold", "name": "Watching",
                "description": "nothing to do"}],
    "inputs": [], "values": [
        {"id": "drift-limit", "label": "Worst fall you will add behind",
         "type": "number", "unit": "percentage_points", "explain": "how far",
         "source": {"name": "these tests", "reasoning": True}}],
}


def resolve(item, context, record=RECORD):
    rows, errors = contract.resolve_evidence(record, context, [item])
    assert errors == [], errors
    return rows[0]


class TestTheHostOwnsTheSubtraction:
    """A strategy names the measure and the anchor. Every number in the row
    is the host's — which is what makes the figure checkable, and what makes
    it impossible for a strategy to state a drift its own evidence does not
    support."""

    def test_the_change_is_now_minus_then(self):
        row = resolve({"measure": MARGIN, "since": "first-purchase"},
                      ctx(now={MARGIN: 34.0},
                          first=anchor("2024-02-01", {MARGIN: 40.0})))
        assert row["observed"]["status"] == "known"
        assert row["observed"]["value"] == pytest.approx(-6.0)

    def test_the_provenance_names_both_readings_and_the_purchase_date(self):
        """The row has to be checkable without leaving the screen. A change
        with no sign of where either side came from is a number the reader
        has to take on trust, and it is the one number here nobody can look
        up in a filing."""
        row = resolve({"measure": MARGIN, "since": "first-purchase"},
                      ctx(now={MARGIN: 34.0},
                          first=anchor("2024-02-01", {MARGIN: 40.0})))
        line = row["observed"]["provenance"][0]
        assert "40" in line and "34" in line and "2024-02-01" in line
        assert "not worked out again" in line

    def test_the_label_says_which_purchase_it_measures_from(self):
        first = resolve({"measure": MARGIN, "since": "first-purchase"},
                        ctx(now={MARGIN: 34.0},
                            first=anchor("2024-02-01", {MARGIN: 40.0})))
        last = resolve({"measure": MARGIN, "since": "last-purchase"},
                       ctx(now={MARGIN: 34.0},
                           last=anchor("2025-11-14", {MARGIN: 36.0})))
        assert "first bought" in first["subject"]["label"]
        assert "last bought" in last["subject"]["label"]
        assert first["subject"]["label"] != last["subject"]["label"]

    def test_a_change_is_its_own_subject_kind(self):
        """Not the measure with a note on it. The screen formats a change
        differently, explains it differently and must never let it be read as
        the level it moved from — and the only thing carrying that
        distinction to the view is the kind."""
        row = resolve({"measure": MARGIN, "since": "first-purchase"},
                      ctx(now={MARGIN: 34.0},
                          first=anchor("2024-02-01", {MARGIN: 40.0})))
        assert row["subject"]["kind"] == "change"
        assert row["subject"]["id"] == MARGIN
        assert row["subject"]["since"] == "first-purchase"

    def test_the_explanation_covers_the_change_and_the_measure(self):
        """Every value explains itself in place, and a change needs two
        explanations: what a move since a purchase means, and what the thing
        moving is. A reader who has never valued a company needs the second
        before the first is worth anything."""
        row = resolve({"measure": MARGIN, "since": "first-purchase"},
                      ctx(now={MARGIN: 34.0},
                          first=anchor("2024-02-01", {MARGIN: 40.0})))
        explain = row["subject"]["explain"]
        assert "frozen" in explain
        assert len(explain.split("\n\n")) >= 2


class TestAChangeInAPercentageIsNotAPercentage:
    """The quietest failure in this file. A six-point fall in a margin
    rendered as "6%" reads as the margin itself, and it also reads as a
    relative move — which is a different number pointing the same way, so a
    reader checking it against the filing finds something plausible."""

    def test_a_percent_measure_changes_in_percentage_points(self):
        row = resolve({"measure": MARGIN, "since": "first-purchase"},
                      ctx(now={MARGIN: 34.0},
                          first=anchor("2024-02-01", {MARGIN: 40.0})))
        assert row["subject"]["unit"] == "percentage_points"

    def test_the_measure_itself_still_renders_as_a_percentage(self):
        """The change is a different unit from the reading. Both render on
        one screen and confusing them is the whole risk."""
        row = resolve({"measure": MARGIN}, ctx(now={MARGIN: 34.0}))
        assert row["subject"]["unit"] == "percent"

    def test_every_other_unit_keeps_its_own(self):
        """The distance between two ratios is a ratio. Only percentages have
        a distinct unit for their difference."""
        row = resolve({"measure": RATIO, "since": "first-purchase"},
                      ctx(now={RATIO: 2.4},
                          first=anchor("2024-02-01", {RATIO: 3.6})))
        assert row["subject"]["unit"] == "ratio"
        assert row["observed"]["value"] == pytest.approx(-1.2)


class TestAbsenceIsNeverAPass:
    """Three different things can be missing and each sends the reader
    somewhere different: fetch data, record a purchase, or nothing — the
    record simply never held it. A single shrug covering all three is worse
    than any of them."""

    def _outcome(self, context, comparator="at_least", threshold=-5.0):
        item = {"measure": MARGIN, "since": "first-purchase",
                "comparator": comparator, "threshold": threshold}
        row = resolve(item, context)
        assert contract.test(context, item) == row["outcome"]
        return row

    def test_no_purchase_to_measure_from_is_unknown(self):
        row = self._outcome(ctx(now={MARGIN: 34.0}))
        assert row["outcome"] == contract.UNKNOWN
        assert "no position is held" in row["observed"]["reason"]

    def test_no_reading_frozen_at_the_purchase_is_unknown(self):
        row = self._outcome(ctx(now={MARGIN: 34.0},
                                first=anchor("2024-02-01", {RATIO: 3.6})))
        assert row["outcome"] == contract.UNKNOWN
        assert "on record when you bought on 2024-02-01" \
            in row["observed"]["reason"]

    def test_no_reading_now_is_unknown_and_says_which_side_is_missing(self):
        row = self._outcome(
            ctx(now={MARGIN: absent("no filing gives a margin")},
                first=anchor("2024-02-01", {MARGIN: 40.0})))
        assert row["outcome"] == contract.UNKNOWN
        assert "no filing gives a margin" in row["observed"]["reason"]
        assert "how far it has moved" in row["observed"]["reason"]

    def test_the_three_reasons_are_all_different(self):
        """Collapsing them is the failure. Each one is a different next step
        for the reader, and a shared sentence would send two of the three to
        the wrong place."""
        reasons = {
            self._outcome(ctx(now={MARGIN: 34.0}))["observed"]["reason"],
            self._outcome(ctx(now={MARGIN: 34.0},
                              first=anchor("2024-02-01", {RATIO: 3.6})
                              ))["observed"]["reason"],
            self._outcome(ctx(now={MARGIN: absent("nothing on record")},
                              first=anchor("2024-02-01", {MARGIN: 40.0})
                              ))["observed"]["reason"],
        }
        assert len(reasons) == 3

    @pytest.mark.parametrize("comparator", list(contract.COMPARATORS))
    def test_absence_satisfies_no_comparator_in_either_direction(self,
                                                                 comparator):
        """Not "usually unknown". A missing figure must not come out as a
        pass under ANY comparison — including the ones where an absent value
        would flatter the strategy, which is where it matters."""
        item = {"measure": MARGIN, "since": "first-purchase",
                "comparator": comparator, "threshold": -5.0}
        assert contract.test(ctx(now={MARGIN: 34.0}), item) == contract.UNKNOWN

    def test_a_purchase_with_no_frozen_record_reads_differently_from_one_with_a_gap(self):
        """A journal that never froze anything and a filing that never held
        this measure are different problems. The first is fixed by recording
        purchases properly; the second cannot be fixed at all."""
        no_record = ctx(now={MARGIN: 34.0},
                        first=absent("the purchase on 2024-02-01 that is the "
                                     "purchase that took this holding up from "
                                     "nothing has no frozen record of what "
                                     "was true then, so there is nothing to "
                                     "measure against"))
        gap = ctx(now={MARGIN: 34.0}, first=anchor("2024-02-01", {RATIO: 3.6}))
        a = resolve({"measure": MARGIN, "since": "first-purchase"}, no_record)
        b = resolve({"measure": MARGIN, "since": "first-purchase"}, gap)
        assert "no frozen record" in a["observed"]["reason"]
        assert "no frozen record" not in b["observed"]["reason"]


class TestTheTwoAnchorsAnswerDifferentQuestions:
    """The reason both exist. A business-deterioration rule anchored to the
    first purchase fires on a position you consciously re-underwrote last
    quarter; a drift rule anchored to the last purchase can never see six
    quarters of small declines. A position bought once cannot tell them
    apart, which is exactly why the test buys twice."""

    def _both(self, comparator="at_least", threshold=-5.0):
        context = ctx(
            now={MARGIN: 34.0},
            first=anchor("2024-02-01", {MARGIN: 44.0}, lot="l1"),
            last=anchor("2025-11-14", {MARGIN: 36.0}, lot="l7"))
        return {a: contract.test(context, {"measure": MARGIN, "since": a,
                                           "comparator": comparator,
                                           "threshold": threshold})
                for a in contract.BASELINE_ANCHORS}, context

    def test_the_same_tolerance_passes_one_anchor_and_fails_the_other(self):
        """Two points down since you last bought, ten down since you started.
        A five-point tolerance says yes to one and no to the other, and both
        answers are correct about the question they were asked."""
        outcomes, _ = self._both()
        assert outcomes["last-purchase"] == contract.PASS
        assert outcomes["first-purchase"] == contract.FAIL

    def test_each_anchor_reads_its_own_lot(self):
        _outcomes, context = self._both()
        rows = [resolve({"measure": MARGIN, "since": a}, context)
                for a in ("first-purchase", "last-purchase")]
        assert [r["observed"]["value"] for r in rows] == \
            pytest.approx([-10.0, -2.0])

    def test_neither_is_an_average_of_the_purchases(self):
        """A weighted average of the two readings is wrong for both
        questions: it describes a day nothing happened on and cannot be
        checked against any filing. Neither answer may be the midpoint."""
        _outcomes, context = self._both()
        values = [resolve({"measure": MARGIN, "since": a},
                          context)["observed"]["value"]
                  for a in ("first-purchase", "last-purchase")]
        assert -6.0 not in values          # the midpoint of -10 and -2


class TestOneComputationNotTwo:
    """`test` and `resolve_evidence` answer the same question from the same
    context through the same code. Two implementations could disagree, and a
    verdict returned beside evidence saying the opposite is the failure the
    whole evidence arrangement exists to refuse."""

    @pytest.mark.parametrize("now,then,expected", [
        (34.0, 40.0, contract.FAIL),
        (39.0, 40.0, contract.PASS),
        (44.0, 40.0, contract.PASS),
    ])
    def test_both_paths_agree(self, now, then, expected):
        context = ctx(now={MARGIN: now},
                      first=anchor("2024-02-01", {MARGIN: then}))
        item = {"measure": MARGIN, "since": "first-purchase",
                "comparator": "at_least", "threshold": -5.0}
        assert contract.test(context, item) == expected
        assert resolve(item, context)["outcome"] == expected

    def test_a_limit_read_out_of_a_setting_is_the_hosts_to_read(self):
        """The strategy names its setting; the host reads the number. A drift
        tolerance restated in the citation is a tolerance that can be
        restated wrongly, and nothing on screen would catch it."""
        context = ctx(now={MARGIN: 34.0},
                      first=anchor("2024-02-01", {MARGIN: 40.0}),
                      values={"drift-limit": -5.0})
        item = {"measure": MARGIN, "since": "first-purchase",
                "comparator": "at_least", "threshold_from": "drift-limit"}
        row = resolve(item, context)
        assert row["test"]["threshold"] == -5.0
        assert row["test"]["threshold_from"]["id"] == "drift-limit"
        assert row["outcome"] == contract.FAIL

    def test_a_tolerance_nobody_answered_is_unknown_not_passed(self):
        context = ctx(now={MARGIN: 34.0},
                      first=anchor("2024-02-01", {MARGIN: 40.0}))
        item = {"measure": MARGIN, "since": "first-purchase",
                "comparator": "at_least", "threshold_from": "drift-limit"}
        assert contract.test(context, item) == contract.UNKNOWN


class TestQualificationsTravelFromBothSides:
    """A change is exactly as trustworthy as the less trustworthy of the two
    readings behind it. Dropping either half is how a figure built on an
    approximated market cap arrives on screen looking exact — and the half
    that goes missing is always the older one."""

    def test_both_readings_cautions_reach_the_row(self):
        context = ctx(
            now={MARGIN: known(34.0, ["the newest filing is an amendment"])},
            first=anchor("2024-02-01",
                         {MARGIN: known(40.0, ["a debt line was matched "
                                               "loosely"])}))
        cautions = resolve({"measure": MARGIN, "since": "first-purchase"},
                           context)["observed"]["cautions"]
        assert any("amendment" in c for c in cautions)
        assert any("matched" in c for c in cautions)

    def test_each_caution_says_which_reading_it_belongs_to(self):
        """Two qualifications about two different days, in one list. Without
        the attribution a reader cannot tell whether the doubt is about what
        they bought or about what they hold."""
        context = ctx(
            now={MARGIN: known(34.0, ["approximated"])},
            first=anchor("2024-02-01", {MARGIN: known(40.0, ["approximated"])}))
        cautions = resolve({"measure": MARGIN, "since": "first-purchase"},
                           context)["observed"]["cautions"]
        assert cautions == ["the reading now — approximated",
                            "the reading you bought at — approximated"]


class TestVocabularyIsRefusedRatherThanGuessed:
    """A misspelling must not read as a missing figure. Absence is a real
    answer about the security; an invented anchor is a fault in the strategy,
    and the two must not arrive on screen looking the same."""

    def test_an_unknown_anchor_is_refused_at_validation(self):
        errors = contract.validate_decision(RECORD, {
            "state": "watch", "payload": {},
            "reason": {"rule": "r", "summary": "s", "evidence": [
                {"measure": MARGIN, "since": "when-i-felt-like-it"}]}})
        assert any("since" in e and "first-purchase" in e for e in errors)

    def test_since_on_anything_but_a_measure_is_refused(self):
        for subject in ({"fact": "position.weight"}, {"value": "drift-limit"},
                        {"label": "Something", "unit": "percent",
                         "actual": 1.0}):
            errors = contract.validate_decision(RECORD, {
                "state": "watch", "payload": {},
                "reason": {"rule": "r", "summary": "s",
                           "evidence": [{**subject,
                                         "since": "first-purchase"}]}})
            assert any("only means something alongside `measure`" in e
                       for e in errors), subject

    def test_at_and_since_together_are_refused(self):
        """One citation answers one question. A reading at a moment and a
        distance between two moments are different figures with different
        units, and a row carrying both would have to pick one silently."""
        errors = contract.validate_decision(RECORD, {
            "state": "watch", "payload": {},
            "reason": {"rule": "r", "summary": "s", "evidence": [
                {"measure": MARGIN, "at": "2025-12-31",
                 "since": "first-purchase"}]}})
        assert any("both `at` and `since`" in e for e in errors)

    def test_a_measure_the_bank_does_not_hold_raises_rather_than_shrugging(self):
        with pytest.raises(ValueError) as e:
            contract.test(ctx(now={MARGIN: 34.0},
                              first=anchor("2024-02-01", {MARGIN: 40.0})),
                          {"measure": "invented_measure",
                           "since": "first-purchase"})
        assert "not in the metric bank" in str(e.value)

    def test_a_change_between_non_numbers_raises(self):
        """A distance only means something between numbers. A yes/no measure
        cited this way is a fault in the strategy, not a fact about the
        security, so it must not come back as unknown."""
        context = ctx(now={YEARS: known(True)},
                      first=anchor("2024-02-01", {YEARS: known(False)}))
        with pytest.raises(ValueError) as e:
            contract.test(context, {"measure": YEARS,
                                    "since": "first-purchase"})
        assert "only means something between numbers" in str(e.value)


class TestHowFarHasTwoHonestAnswers:
    """`change: proportion` — the second strategy's one demand on the
    contract, and the thing v5 could not say at all.

    A distance is the right answer for a measure whose levels mean something
    on their own: half a turn off a current ratio is half a turn wherever it
    started. It is the wrong answer for one whose levels do not. A rule
    reading "the returns have fallen by a third" is a claim about proportion,
    and a single tolerance in points either fires on a decline a high-return
    business shrugs off or never fires on a low-return one.

    What is pinned here is what would go wrong *quietly*:

    - the two forms sharing a unit. "-6" and "-15%" describing one decline is
      the entire point, and a screen rendering both the same way makes the
      difference invisible exactly where it decides something.
    - a signed denominator. A margin that was -4% and is now -8% has got
      twice as bad, and dividing by a negative reports that as +100% — a
      worsening rendered as an improvement, in a figure an exit fires on.
    - a nought baseline producing a number. There is no share of nought, and
      inventing an enormous one is principle 4 failing in the direction that
      sells something.
    - the default drifting. Every citation written before this key existed
      means `distance`, and it has to go on meaning it bit for bit.
    """

    def _both(self, then, now, measure=MARGIN):
        context = ctx(now={measure: now},
                      first=anchor("2024-02-01", {measure: then}))
        return (resolve({"measure": measure, "since": "first-purchase"},
                        context),
                resolve({"measure": measure, "since": "first-purchase",
                         "change": "proportion"}, context))

    def test_a_proportion_is_the_move_over_what_it_was(self):
        _distance, share = self._both(40.0, 34.0)
        assert share["observed"]["value"] == pytest.approx(-15.0)

    def test_the_same_decline_is_two_different_numbers(self):
        distance, share = self._both(40.0, 34.0)
        assert distance["observed"]["value"] == pytest.approx(-6.0)
        assert share["observed"]["value"] == pytest.approx(-15.0)

    def test_a_proportion_is_a_percent_whatever_it_was_taken_of(self):
        """Not the measure's unit and not the distance's. It is no longer in
        the measure's units at all — it is the share of the old reading the
        move came to."""
        distance, share = self._both(3.6, 2.4, measure=RATIO)
        assert distance["subject"]["unit"] == "ratio"
        assert share["subject"]["unit"] == "percent"
        assert share["observed"]["value"] == pytest.approx(-33.333, abs=0.01)

    def test_a_percent_measure_does_not_render_a_proportion_as_points(self):
        distance, share = self._both(40.0, 34.0)
        assert distance["subject"]["unit"] == "percentage_points"
        assert share["subject"]["unit"] == "percent"

    def test_the_label_says_which_of_the_two_it_is(self):
        distance, share = self._both(40.0, 34.0)
        assert "as a share of what it was then" in share["subject"]["label"]
        assert "as a share" not in distance["subject"]["label"]
        assert "since you first bought" in share["subject"]["label"]

    def test_it_explains_how_it_is_counted_as_well_as_what_it_is(self):
        """Three things a reader needs: which purchase, how the move is
        counted, and what the thing moving is. The middle one is new and is
        the one nobody would guess."""
        _distance, share = self._both(40.0, 34.0)
        explain = share["subject"]["explain"]
        assert "as a percentage of what it was at that purchase" in explain
        assert "frozen" in explain
        assert len(explain.split("\n\n")) >= 4

    def test_a_negative_baseline_getting_worse_reads_as_a_fall(self):
        """The sign trap. Measured against the size of the old reading and
        not its sign, so a margin that was -4% and is now -8% reads as -100%
        and not as +100%."""
        _distance, share = self._both(-4.0, -8.0)
        assert share["observed"]["value"] == pytest.approx(-100.0)

    def test_a_negative_baseline_recovering_reads_as_a_rise(self):
        _distance, share = self._both(-4.0, -2.0)
        assert share["observed"]["value"] == pytest.approx(50.0)

    def test_a_nought_baseline_is_absent_and_never_a_number(self):
        """There is no share of nought. Not an enormous number, not a zero,
        not quietly falling back to the distance — absent, with the reason,
        because a value that cannot be right must not feed a verdict."""
        context = ctx(now={MARGIN: 9.0},
                      first=anchor("2024-02-01", {MARGIN: 0.0}))
        row = resolve({"measure": MARGIN, "since": "first-purchase",
                       "change": "proportion"}, context)
        assert row["observed"]["status"] == "absent"
        assert "share of nought" in row["observed"]["reason"]

    def test_a_nought_baseline_can_never_come_out_as_a_pass(self):
        context = ctx(now={MARGIN: 9.0},
                      first=anchor("2024-02-01", {MARGIN: 0.0}))
        item = {"measure": MARGIN, "since": "first-purchase",
                "change": "proportion", "comparator": "at_least",
                "threshold": -33.0}
        assert contract.test(context, item) == contract.UNKNOWN
        assert resolve(item, context)["outcome"] == contract.UNKNOWN

    def test_a_nought_baseline_still_has_a_distance(self):
        """The absence belongs to the proportion and not to the pair of
        readings. Nought to nine is a rise of nine points, and saying so is
        still honest."""
        row = resolve({"measure": MARGIN, "since": "first-purchase"},
                      ctx(now={MARGIN: 9.0},
                          first=anchor("2024-02-01", {MARGIN: 0.0})))
        assert row["observed"]["value"] == pytest.approx(9.0)

    def test_left_out_it_is_a_distance(self):
        """The default is what every citation written before this key existed
        already computed. A default that changed the arithmetic would be the
        silent misreading the contract version exists to refuse."""
        stated = resolve({"measure": MARGIN, "since": "first-purchase",
                          "change": "distance"},
                         ctx(now={MARGIN: 34.0},
                             first=anchor("2024-02-01", {MARGIN: 40.0})))
        omitted = resolve({"measure": MARGIN, "since": "first-purchase"},
                          ctx(now={MARGIN: 34.0},
                              first=anchor("2024-02-01", {MARGIN: 40.0})))
        assert stated == omitted

    def test_the_proportion_carries_both_readings_qualifications(self):
        """A change is exactly as trustworthy as the less trustworthy of the
        two readings behind it, whichever way it is counted."""
        context = ctx(
            now={MARGIN: known(34.0, cautions=["the cost line was matched "
                                               "loosely"])},
            first=anchor("2024-02-01",
                         {MARGIN: known(40.0, cautions=["approximated"])}))
        row = resolve({"measure": MARGIN, "since": "first-purchase",
                       "change": "proportion"}, context)
        joined = " ".join(row["observed"]["cautions"])
        assert "the reading now" in joined
        assert "the reading you bought at" in joined

    def test_the_provenance_states_the_proportion_it_worked_out(self):
        _distance, share = self._both(40.0, 34.0)
        line = share["observed"]["provenance"][0]
        assert "40" in line and "34" in line and "2024-02-01" in line
        assert "-15.0%" in line

    def test_a_form_the_host_does_not_have_is_refused(self):
        errors = contract.validate_decision(RECORD, {
            "state": "watch", "payload": {},
            "reason": {"rule": "r", "summary": "s", "evidence": [
                {"measure": MARGIN, "since": "first-purchase",
                 "change": "ratio"}]}})
        assert any("`change` must be one of" in e for e in errors)

    def test_a_form_with_no_baseline_is_refused(self):
        """On its own there are not two readings to have moved between, so a
        `change` without a `since` is a citation that means nothing."""
        errors = contract.validate_decision(RECORD, {
            "state": "watch", "payload": {},
            "reason": {"rule": "r", "summary": "s", "evidence": [
                {"measure": MARGIN, "change": "proportion"}]}})
        assert any("only means something alongside `since`" in e
                   for e in errors)

    def test_absence_on_either_side_is_still_absence(self):
        """The new form changes the arithmetic and nothing about what happens
        when there is nothing to do arithmetic on."""
        item = {"measure": MARGIN, "since": "first-purchase",
                "change": "proportion", "comparator": "at_least",
                "threshold": -33.0}
        no_purchase = ctx(now={MARGIN: 34.0})
        no_reading_then = ctx(now={MARGIN: 34.0},
                              first=anchor("2024-02-01", {}))
        no_reading_now = ctx(now={MARGIN: absent("nothing is on record")},
                             first=anchor("2024-02-01", {MARGIN: 40.0}))
        for context in (no_purchase, no_reading_then, no_reading_now):
            assert contract.test(context, item) == contract.UNKNOWN
            assert resolve(item, context)["observed"]["status"] == "absent"

    def test_a_form_the_host_does_not_have_is_refused_while_deciding_too(self):
        """Not only at validation. `test` is asked how a comparison came out
        WHILE a strategy is choosing its state, before anything validates the
        decision — so a misspelled form that quietly fell back to `distance`
        would change the arithmetic a verdict was picked by, and the row
        rendered underneath would agree with it. Loud in both places or the
        guarantee is only half there."""
        context = ctx(now={MARGIN: 34.0},
                      first=anchor("2024-02-01", {MARGIN: 40.0}))
        item = {"measure": MARGIN, "since": "first-purchase",
                "change": "proprtion", "comparator": "at_least",
                "threshold": -33.0}
        with pytest.raises(ValueError) as e:
            contract.test(context, item)
        assert "not one of the ways the host counts a move" in str(e.value)
        # And the same citation is refused legibly on the rendering path.
        _rows, errors = contract.resolve_evidence(RECORD, context, [item])
        assert errors and "counts a move" in errors[0]


class TestADriftCitationCannotBeConfirmed:
    """The third way a `since` citation fell through machinery written before
    it existed, and the one that acts.

    `confirm` counts consecutive filings that each carry a failure on their
    own reading, by re-asking the same citation `at` each past period. A
    baseline is frozen at a purchase and never re-read, so there is no
    reading of a drift at an older filing — which is exactly why an evidence
    item carrying both `at` and `since` is refused.

    The loop synthesised that pair itself. `_observation` reads `since`
    first, so `at` was ignored and every filing in the record was answered
    with the identical comparison: the run came back as the length of the
    history, `periods` named filings nobody had re-read, and the drop-a-year
    reading compared the number against itself and always survived. An exit
    that waits for a breach to be established was told it had been, on
    evidence that did not exist.
    """

    def context(self):
        return ctx(now={RATIO: 1.2},
                   first=anchor("2024-06-01", {RATIO: 3.0}))

    def item(self, **over):
        return {"measure": RATIO, "since": "first-purchase",
                "comparator": "at_least", "threshold": -0.5, **over}

    def test_it_is_refused_rather_than_answered_from_nothing(self):
        with pytest.raises(ValueError) as e:
            contract.confirm(self.context(), self.item())
        assert "frozen at the purchase" in str(e.value)

    def test_the_level_underneath_it_confirms_exactly_as_before(self):
        """The refusal is about the drift and not about the measure. A
        strategy that wants both cites the level and confirms that."""
        got = contract.confirm(self.context(),
                               {"measure": RATIO, "comparator": "at_least",
                                "threshold": 2.0})
        assert got["confirmation"] in contract.CONFIRMATIONS

    def test_the_refusal_names_the_citation_it_is_refusing(self):
        """A fault in the strategy rather than a fact about the security, so
        the sentence has to be enough to find the rule that wrote it."""
        with pytest.raises(ValueError) as e:
            contract.confirm(self.context(), self.item())
        assert RATIO in str(e.value)
        assert "since you first bought" in str(e.value)
