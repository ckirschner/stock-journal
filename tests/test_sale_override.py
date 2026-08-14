"""A sale that goes against the strategy carries a written reason.

A purchase against the signal has demanded one since the first override work.
A sale did not — and the asymmetry was backwards, because panic-selling is the
specific behaviour this program exists to catch. Somebody closing a position
their own rules still say to hold, in a bad week, is the canonical failure, and
the record had a place for why you bought against advice and nowhere for why
you sold against it.

Three things have to hold.

**The boundary is exact.** Selling what the strategy told you to sell is not
against anything. Selling what it said to hold is. Selling something it could
not evaluate is neither — and asking for a sentence there is the over-prompt
that trains people to type nothing into the field the real one belongs in.

**Nothing is blocked.** The sale is recorded whatever the verdict said and
whether or not a reason was written. A screen that refuses to appear is a gate
however it is described.

**The analytics can group by it**, over sales recorded before the sentence
existed as well as after — because how a sale went is derived from the verdict
frozen with it, not from the new field.
"""

import pytest

from engine import contract, portfolio


def decision(render, state="a-state", rule="r", produced_by="strategy",
             evidence=()):
    return {"state": {"id": state, "name": state.replace("-", " ").title(),
                      "render": render},
            "render": render,
            "tier": contract.RENDER_TYPES[render]["tier"],
            "produced_by": produced_by,
            "strategy": {"id": "fixture", "name": "Fixture", "version": 1},
            "payload": {},
            "reason": {"rule": rule, "summary": "because.",
                       "evidence": list(evidence), "groups": []}}


def held(shares=10, price=20.0, when="2026-01-05"):
    s = portfolio.new_security("SYN", "Synthetic Co")
    portfolio.add_lot(s, decision("commit"), shares, price, when, values={},
                      price_seen={"value": price, "source": "manual",
                                  "date": None, "ticker": "SYN"})
    return s


def sell(s, d, reason="Panic", shares=10, price=30.0, when="2026-08-08",
         basis="live", override_reason=""):
    return portfolio.sell_lots(
        s, d, reason, shares, price, when, values={},
        price_seen={"value": price, "source": "manual", "date": None,
                    "ticker": "SYN"},
        evaluation={"basis": basis, "as_of": when},
        override_reason=override_reason)


class TestWhereTheBoundarySits:
    @pytest.mark.parametrize("render", ["close", "reduce"])
    def test_selling_what_the_strategy_told_you_to_sell_is_not_against_it(
            self, render):
        """`close` MEANS full exit and `reduce` MEANS partial exit. Reading
        them is reading the host's own vocabulary, not an opinion about
        investing."""
        lot = sell(held(), decision(render))
        assert portfolio.sale_recorded_as(decision(render), "live") == "with"
        assert portfolio.sold_as(lot) == "with"
        assert lot["override"] is None
        assert portfolio.sale_reason_owed(decision(render), "live") is False

    @pytest.mark.parametrize("render", ["hold", "commit"])
    def test_selling_against_a_verdict_that_did_not_call_for_it_is_against(
            self, render):
        """The panic sale. A hold is the strategy still saying to own it, and
        a commit is it saying to own more."""
        lot = sell(held(), decision(render),
                   override_reason="Down 30% and I could not sleep.")
        assert portfolio.sold_as(lot) == "against"
        assert lot["override"]["kind"] == "against"
        assert lot["override"]["state"] == render.title().replace("-", " ") \
            or lot["override"]["state"] == "A State"
        assert lot["override"]["rule"] == "r"
        assert lot["override"]["reason"] == "Down 30% and I could not sleep."
        assert portfolio.sale_reason_owed(decision(render), "live") is True

    def test_a_blocked_state_the_strategy_declared_is_a_verdict_to_defy(self):
        """"Read this again before you act" is an answer, and going ahead
        anyway is going against it — the same rule the purchase path already
        applies."""
        d = decision("blocked", produced_by="strategy")
        assert portfolio.sale_reason_owed(d, "live") is True
        assert portfolio.sold_as(sell(held(), d)) == "against"

    def test_a_blocked_state_the_host_produced_is_not(self):
        """The host's blocked states mean "we could not ask". There is no
        verdict behind them and nothing to go against."""
        d = decision("blocked", produced_by="host")
        assert portfolio.sale_reason_owed(d, "live") is False
        assert portfolio.sold_as(sell(held(), d)) == "without"

    def test_selling_with_no_verdict_is_recorded_and_never_prompted(self):
        """Where the purchase path parts company with this one, deliberately.
        Buying into a name nothing could evaluate is putting capital behind a
        blank. Selling one reduces exposure, it is the ordinary outcome for a
        name with no data fetched, and a prompt there would fire constantly on
        decisions with nothing to defy — which is how the field somebody
        should write in becomes one they have learned to skip."""
        lot = sell(held(), decision("unknown"))
        assert portfolio.sale_reason_owed(decision("unknown"), "live") is False
        assert portfolio.sold_as(lot) == "without"
        # Recorded all the same, so the analytics can still tell a defied
        # verdict from an absent one.
        assert lot["override"]["kind"] == "without"

    def test_a_missing_strategy_is_an_absence_and_not_a_defiance(self):
        assert portfolio.sale_reason_owed(None, "live") is False
        assert portfolio.sold_as(sell(held(), None)) == "without"

    def test_a_reconstruction_that_reached_nothing_is_neither(self):
        """Nobody was standing in front of a screen. Filed as an override it
        would put decisions nobody made into the figures that measure
        somebody's judgement — and a backfill puts a pile of them there at
        once."""
        lot = sell(held(), decision("unknown"), when="2026-03-01",
                   basis="reconstructed")
        assert portfolio.sold_as(lot) == "unreconstructed"
        assert lot["override"] is None
        assert portfolio.sale_reason_owed(decision("unknown"),
                                          "reconstructed") is False

    def test_a_reconstruction_that_did_reach_a_verdict_is_still_against(self):
        lot = sell(held(), decision("hold"), when="2026-03-01",
                   basis="reconstructed")
        assert portfolio.sold_as(lot) == "against"
        assert lot["override"]["basis"] == "reconstructed"

    def test_a_basis_nobody_stated_is_refused_rather_than_guessed(self):
        with pytest.raises(ValueError, match="not a basis"):
            portfolio.sale_recorded_as(decision("hold"), "whenever")

    def test_which_renders_sanction_an_exit_is_read_off_the_host_table(self):
        """Not a tuple written out at the point of use. A render type added
        to the contract arrives here without this file being edited, which is
        the only version of the guarantee worth having."""
        assert set(contract.EXIT_RENDERS) == {
            r for r, spec in contract.RENDER_TYPES.items() if spec["exits"]}
        assert set(contract.EXIT_RENDERS) == {"reduce", "close"}


class TestNothingIsBlocked:
    def test_a_sale_against_the_signal_with_no_reason_still_records(self):
        """The tool records decisions and never blocks them. A sale the
        journal refused to write is a sale that happened and is not on the
        record, which is worse than one recorded with nothing said."""
        s = held()
        lot = sell(s, decision("hold"))
        assert lot["shares"] == 10
        assert lot["override"]["reason"] == "No reason given."
        assert portfolio.shares_held(s) == 0

    def test_the_sentence_lands_in_the_journal_where_it_will_be_read(self):
        s = held()
        sell(s, decision("hold"), override_reason="Needed the money.")
        note = s["notes"][-1]["text"]
        assert "against the signal" in note
        assert "Needed the money." in note

    def test_a_sale_the_strategy_called_for_writes_no_override_note(self):
        s = held()
        sell(s, decision("close"))
        assert not any("against the signal" in n["text"]
                       for n in s.get("notes") or [])


class TestTheSentenceIsNeverDiscarded:
    def test_a_reason_written_before_the_verdict_moved_is_kept(self):
        """The dialog asks for a sentence while the verdict says hold; the
        verdict is worked out again at the write and can have moved to a
        `close` by then. Dropping the sentence loses the only record that at
        the moment they decided, they were going against something — the same
        rule the purchase path already follows."""
        s = held()
        lot = sell(s, decision("close"), override_reason="Could not sleep.")
        assert portfolio.sold_as(lot) == "with"
        assert lot["override"] is None
        note = s["notes"][-1]["text"]
        assert "with the signal" in note
        assert "Could not sleep." in note

    def test_the_record_says_whether_a_sentence_was_actually_written(self):
        """"No reason given." is the host's own words. A screen that could not
        tell it from the user's would say their reason is on the record when
        nothing is."""
        written = sell(held(), decision("hold"), override_reason="Because.")
        assert written["override"]["reason_given"] is True
        silent = sell(held(), decision("hold"))
        assert silent["override"]["reason_given"] is False
        assert silent["override"]["reason"] == "No reason given."


class TestTheExitAnalyticsCanGroupByIt:
    @staticmethod
    def _priced(_s):
        return {"value": 40.0, "source": "manual", "date": None,
                "ticker": "SYN"}

    def _journal(self):
        with_signal = held(shares=10, price=20.0)
        sell(with_signal, decision("close"), reason="Hit valuation")
        panicked = held(shares=10, price=20.0)
        sell(panicked, decision("hold"), reason="Panic",
             override_reason="Bad week.")
        blind = held(shares=10, price=20.0)
        sell(blind, decision("unknown"), reason="Panic")
        return [with_signal, panicked, blind]

    def test_every_group_splits_four_ways_and_the_split_covers_it_whole(self):
        """A subset that reads like the total is the failure this shape
        exists against, so the four counts add up to the group's own."""
        card = portfolio.exit_scorecard(self._journal(), self._priced)
        assert card["Panic"]["n"] == 2
        assert card["Panic"]["signal"] == {"with": 0, "against": 1,
                                           "without": 1,
                                           "unreconstructed": 0}
        assert card["Hit valuation"]["signal"]["with"] == 1
        for group in card.values():
            assert sum(group["signal"].values()) == group["n"]

    def test_the_against_group_carries_its_own_aftermath(self):
        """"You panicked twice and the price rose after" is about a habit.
        "Of those two, one was sold against a hold your own rules were still
        giving" is about a rule being defied at a moment."""
        card = portfolio.exit_scorecard(self._journal(), self._priced)
        assert card["Panic"]["against"]["n"] == 1
        assert card["Panic"]["against"]["n_after"] == 1
        # Sold at 30, worth 40 now.
        assert card["Panic"]["against"]["avg_after"] == pytest.approx(33.3)

    def test_it_runs_over_sales_recorded_before_the_sentence_existed(self):
        """Derived from `rule_triggered` and the frozen evaluation, not from
        the new field — so a journal's whole history splits, and nothing
        invents a reason for the sales that never had one."""
        old = held()
        lot = sell(old, decision("hold"))
        del lot["override"]                     # as an older record
        assert portfolio.sold_as(lot) == "against"
        card = portfolio.exit_scorecard([old], self._priced)
        assert card["Panic"]["signal"]["against"] == 1
