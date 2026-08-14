"""Where capital goes: eligibility, order, conversion, target and standing.

Every failure pinned here is a silent one. This screen exists to answer "I
have money, where does it go", and every wrong answer it can give looks like
a right one:

  - a hold, a trim or an unreadable verdict quietly counted as eligible would
    put a name on a list whose whole meaning is "your rules say capital
    belongs here", with nothing on the row saying otherwise;
  - a condition the host decided had been met would move money on the host's
    opinion while wearing the strategy's authority;
  - the wrong ORDER is the doom loop. The top of this list is what gets read
    and acted on, and a list that happened to sort by what you already hold
    would recommend averaging down every single time, correctly formatted;
  - a size the host could not convert, rendered as $0, reads as "this can
    take nothing more" — a confident answer where the honest one is that the
    account value or the price is missing.

Nothing here evaluates anything. The verdicts arrive already taken, in the
contract's envelope, and the portfolio node arrives already computed — so
these tests build both by hand, the way the module is actually called.
"""

import pytest

from engine import allocation

STRATEGY = {"id": "fixture", "name": "Fixture", "version": 1,
            "values_version": 1, "contract": 5}


def known(value):
    return {"status": "known", "value": float(value)}


def absent(reason):
    return {"status": "absent", "reason": reason}


def security(ticker, name=None, shares=0.0):
    """A journal security exactly as the screen receives it: the stored
    record with the shares held decorated on, which is all this module reads
    off a security."""
    return {"ticker": ticker, "name": name or f"{ticker.title()} Industries",
            "_shares": float(shares)}


def decision(render, payload=None, state="a-state", rule="a-rule",
             summary="Because the rule said so."):
    """A verdict in the contract's envelope, already taken."""
    return {
        "render": render,
        "tier": "evaluation" if render in ("blocked", "unknown") else "position",
        "state": {"id": state, "name": state.replace("-", " ").title(),
                  "description": "What this state means.", "fix": None},
        "payload": payload if payload is not None else {},
        "reason": {"rule": rule, "summary": summary, "evidence": [],
                   "note": None},
        "produced_by": "strategy",
        "strategy": dict(STRATEGY),
    }


def size(unit, value):
    return {"unit": unit, "value": float(value)}


def commit(unit="weight", value=5.0, condition=None, plan=None, **over):
    payload = {"size": size(unit, value), "condition": condition}
    if plan is not None:
        payload["plan"] = plan
    return decision("commit", payload, state="buy", **over)


def tranche(unit, value, summary):
    return {"size": size(unit, value), "condition": {"summary": summary}}


def folio(cash=None, account_value=None, holdings=()):
    """The host's own portfolio node, as `context.portfolio_view` hands it
    over: free cash, the derived account total, and a market value per
    holding."""
    return {"cash": cash if cash is not None else known(20_000),
            "account_value": (account_value if account_value is not None
                              else known(50_000)),
            "slots": {"occupied": len(holdings)},
            "holdings": [dict(h) for h in holdings]}


def holding(ticker, market_value):
    return {"ticker": ticker, "name": f"{ticker.title()} Industries",
            "shares": 100.0, "opened": "2025-01-02",
            "market_value": market_value}


def by_ticker(entries):
    return {e["ticker"]: e for e in entries}


def tickers(entries):
    return [e["ticker"] for e in entries]


# The account every ordering test is measured against, and it is internally
# consistent on purpose: $20,000 free cash plus $19,000 of ANVIL, $600 of
# BRAMBLE and $10,400 of CINDER is the $50,000 account total. A folio whose
# parts did not add up would let an ordering test pass against arithmetic
# that could never occur.
DOOM_HOLDINGS = (holding("ANVIL", known(19_000)),
                 holding("BRAMBLE", known(600)),
                 holding("CINDER", known(10_400)))


def doom_loop():
    """The case this whole module exists for.

    ANVIL is the big holding, already near the size its strategy wants: $19,000
    of a $50,000 account, with 2% — $1,000 — of room left. BRAMBLE is the
    small one, far from where the same strategy wants it: $600 held, with 20%
    — $10,000 — of room.

    A screen ordered by anything resembling conviction, recency or position
    size puts ANVIL first. Adding to ANVIL is the trade that feels most like
    the obvious one and is most reliably the wrong one.
    """
    securities = [security("ANVIL", shares=200), security("BRAMBLE", shares=40),
                  security("CINDER", shares=80)]
    decisions = {"ANVIL": commit("weight", 2.0),
                 "BRAMBLE": commit("weight", 20.0),
                 "CINDER": decision("hold", state="sit",
                                    rule="already-at-weight",
                                    summary="It is where it should be.")}
    prices = {"ANVIL": known(95.0), "BRAMBLE": known(15.0),
              "CINDER": known(130.0)}
    return securities, decisions, prices, folio(holdings=DOOM_HOLDINGS)


class TestOnlyACommitCanReceiveCapital:
    """`commit` is the host's own word for "capital may go in". Reading it is
    the only judgement this module makes, and it is not a judgement about
    investing — every other render means the strategy said no, or could not
    say anything, and either way this screen has nothing to offer."""

    @pytest.mark.parametrize("render,state", [
        ("hold", "sit"), ("reduce", "trim"), ("close", "get-out"),
        ("blocked", "host:needs-answers"), ("unknown", "host:cannot-say")])
    def test_every_render_but_commit_is_excluded_with_its_own_reason(
            self, render, state):
        """A name that did not qualify is not a name that vanishes. The
        strategy turning eleven securities down is the useful half of an empty
        screen — and a row with no rule on it would be indistinguishable from
        one the screen failed to compute."""
        out = allocation.view(
            [security("DELVE", shares=10)],
            {"DELVE": decision(render, state=state, rule="the-first-test",
                               summary="The first test settled it.")},
            {"DELVE": known(12.0)}, folio())
        assert out["ready"] == [] and out["waiting"] == []
        [entry] = out["excluded"]
        assert entry["render"] == render
        assert entry["state"]["id"] == state
        assert entry["rule"] == "the-first-test"
        assert entry["summary"] == "The first test settled it."
        # and nothing on an excluded row invites a sum being taken from it
        assert "amount" not in entry and "target" not in entry

    def test_a_commit_with_nothing_holding_it_back_is_ready(self):
        out = allocation.view([security("DELVE")], {"DELVE": commit("usd", 500)},
                              {"DELVE": known(12.0)}, folio())
        assert tickers(out["ready"]) == ["DELVE"]
        assert out["waiting"] == [] and out["excluded"] == []

    def test_a_security_with_no_verdict_at_all_is_still_on_the_screen(self):
        """Evaluation can fail for one name — a strategy raising, a fetch that
        never landed — and the security does not stop existing. Dropping it
        would make the screen quietly shorter than the journal, which is the
        one discrepancy nobody counts."""
        out = allocation.view([security("DELVE", shares=10)], {}, {}, folio())
        [entry] = out["excluded"]
        assert entry["ticker"] == "DELVE"
        assert entry["render"] is None and entry["state"]["id"] is None

    def test_excluded_names_come_back_in_ticker_order(self):
        """Deterministic, because it is read as a list of what your rules
        turned down — and an order that shuffled between renders would read as
        the list having changed."""
        names = ["ZEBRA", "ANVIL", "MARROW"]
        out = allocation.view(
            [security(t) for t in names],
            {t: decision("hold") for t in names},
            {}, folio())
        assert tickers(out["excluded"]) == ["ANVIL", "MARROW", "ZEBRA"]


class TestAConditionIsReportedAndNeverEvaluated:
    """A commit carrying a condition is capital the strategy is holding back.
    The host reports the condition in the strategy's own words and never
    decides whether it has been met — the day it is met, the strategy returns
    that tranche as the size in front of you with no condition on it.

    A host that read the prose would be holding an opinion (principle 8), and
    a wrong reading has no symptom: the row simply moves to "ready" and looks
    exactly like one the strategy released."""

    def test_a_conditional_commit_waits_and_is_never_ready(self):
        cond = {"summary": "the share price closes below $30"}
        out = allocation.view([security("DELVE")],
                              {"DELVE": commit("usd", 2_000, condition=cond)},
                              {"DELVE": known(35.0)}, folio())
        assert out["ready"] == []
        assert tickers(out["waiting"]) == ["DELVE"]

    def test_the_condition_is_passed_through_word_for_word(self):
        cond = {"summary": "the next annual report shows current assets at "
                           "twice current liabilities"}
        out = allocation.view([security("DELVE")],
                              {"DELVE": commit("usd", 2_000, condition=cond)},
                              {"DELVE": known(35.0)}, folio())
        [entry] = out["waiting"]
        assert entry["condition"] == cond
        # a copy, so nothing upstream can rewrite what the screen showed
        assert entry["condition"] is not cond

    def test_a_condition_that_is_plainly_already_true_still_waits(self):
        """The strongest form of "never evaluated": the host has no idea what
        the sentence says, and a sentence anyone can see is satisfied gets
        exactly the same treatment as one nobody can check. Any host that
        started reading these would start here."""
        out = allocation.view(
            [security("DELVE")],
            {"DELVE": commit("usd", 2_000,
                             condition={"summary": "two is more than one"})},
            {"DELVE": known(35.0)}, folio())
        assert out["ready"] == []
        assert out["waiting"][0]["condition"]["summary"] == "two is more than one"

    def test_a_waiting_entry_still_says_what_it_would_take(self):
        """Held back is not unknown. The size the strategy stated is money the
        user is being asked to plan around, and a row that showed a condition
        with no figure beside it would hide the size of the commitment at the
        one moment it is being made calmly."""
        out = allocation.view(
            [security("DELVE")],
            {"DELVE": commit("usd", 2_000,
                             condition={"summary": "the price falls further"})},
            {"DELVE": known(35.0)}, folio())
        amount = out["waiting"][0]["amount"]
        assert amount["status"] == "known" and amount["value"] == 2_000.0


class TestTheOrderIsRoomLeftNotWhatYouAlreadyHold:
    """The ordering is the whole defence against the doom loop, and it is the
    single behaviour in this module that would fail without a symptom: a
    wrongly ordered list is still a well-formed list of eligible names, and
    the wrong one is at the top."""

    def test_the_small_position_far_from_target_outranks_the_big_one(self):
        """ANVIL is thirty times the holding BRAMBLE is, and has a tenth of
        the room. The screen is read top-down, so this ordering is the
        difference between the tool suggesting you finish building a small
        position and the tool suggesting you add to the one that is already
        large — which, on the day someone opens this screen, is nearly always
        the one that is down."""
        out = allocation.view(*doom_loop())
        assert tickers(out["ready"]) == ["BRAMBLE", "ANVIL"]
        rows = by_ticker(out["ready"])
        # ordered by room left, and by nothing else: ANVIL holds more, is
        # worth more, and is aiming at a bigger position — and still sorts
        # second, because it has less room.
        assert rows["ANVIL"]["committed"] == known(19_000)
        assert rows["BRAMBLE"]["committed"] == known(600)
        assert rows["ANVIL"]["target"]["value"] == 20_000
        assert rows["BRAMBLE"]["target"]["value"] == 10_600
        assert rows["BRAMBLE"]["amount"]["value"] == 10_000
        assert rows["ANVIL"]["amount"]["value"] == 1_000

    def test_the_name_that_did_not_qualify_never_reaches_the_list(self):
        out = allocation.view(*doom_loop())
        assert tickers(out["excluded"]) == ["CINDER"]
        assert out["excluded"][0]["rule"] == "already-at-weight"

    def test_equal_amounts_sort_by_ticker_so_the_order_never_drifts(self):
        """Two names with identical room have no ordering between them, and
        the honest answer is a stable one. A list that reshuffled on every
        render would look like the rules had changed when nothing had."""
        names = ["ZEBRA", "ANVIL", "MARROW"]
        out = allocation.view(
            [security(t) for t in names],
            {t: commit("usd", 2_500) for t in names},
            {t: known(20.0) for t in names}, folio())
        assert tickers(out["ready"]) == ["ANVIL", "MARROW", "ZEBRA"]

    def test_waiting_is_ordered_by_the_same_arithmetic(self):
        out = allocation.view(
            [security("ANVIL"), security("BRAMBLE")],
            {"ANVIL": commit("usd", 1_000,
                             condition={"summary": "the price falls"}),
             "BRAMBLE": commit("usd", 9_000,
                               condition={"summary": "the price falls"})},
            {"ANVIL": known(20.0), "BRAMBLE": known(20.0)}, folio())
        assert tickers(out["waiting"]) == ["BRAMBLE", "ANVIL"]


class TestASizeBecomesMoneyOrItBecomesNothing:
    """A strategy sizes in whatever unit suits it, and two sizes in different
    units cannot be ordered against each other without converting. Every
    conversion is arithmetic over figures the host already owns; every way one
    can fail is absence with its own reason."""

    def _one(self, decision_, price=None, account_value=None):
        out = allocation.view(
            [security("DELVE")], {"DELVE": decision_},
            {"DELVE": price} if price else {},
            folio(account_value=account_value))
        return (out["ready"] + out["waiting"])[0]

    def test_dollars_are_already_money(self):
        entry = self._one(commit("usd", 2_500), price=known(20.0))
        assert entry["amount"]["status"] == "known"
        assert entry["amount"]["value"] == 2_500.0
        assert entry["amount"]["provenance"] == [
            "the strategy sized this in dollars"]

    def test_a_weight_is_money_only_against_the_account_value(self):
        """Five percent of a $40,000 account is $2,000 — and the provenance
        names both halves, because a reader who cannot see which account
        total was used cannot tell a stale one from a current one."""
        entry = self._one(commit("weight", 5.0), price=known(20.0),
                          account_value=known(40_000))
        assert entry["amount"]["value"] == 2_000.0
        assert entry["amount"]["provenance"] == [
            "5% of an account of $40,000"]

    def test_a_share_count_is_money_only_against_a_price(self):
        entry = self._one(commit("shares", 10.0), price=known(12.50))
        assert entry["amount"]["value"] == 125.0
        # To the cent, so the line adds up. A price rounded to the dollar
        # beside a total of $125 is a provenance sentence the reader cannot
        # check, which is the only thing a provenance sentence is for.
        assert entry["amount"]["provenance"] == ["10 shares at $12.50"]

    def test_the_size_itself_is_kept_beside_the_money(self):
        """The conversion is the host's arithmetic; the size is what the
        strategy actually said. Showing only the dollars would make the
        strategy look like it had stated a dollar figure it never stated."""
        entry = self._one(commit("weight", 5.0), price=known(20.0),
                          account_value=known(40_000))
        assert entry["size"] == {"unit": "weight", "value": 5.0}


class TestAnAmountThatCannotBeReachedIsAbsentNotZero:
    """This figure decides what order the screen puts your holdings in. A
    fallback here — a zero, a carried-forward total, a price from yesterday's
    other holding — would produce a plausible dollar figure from a number that
    is not there, in the one place a confident wrong answer is acted on
    without being read (principle 4)."""

    def _amount(self, decision_, prices=None, account_value=None):
        out = allocation.view([security("DELVE")], {"DELVE": decision_},
                              prices or {}, folio(account_value=account_value))
        return (out["ready"] + out["waiting"])[0]["amount"]

    def test_a_weight_with_no_account_value_behind_it_is_absent(self):
        amount = self._amount(
            commit("weight", 5.0), {"DELVE": known(20.0)},
            account_value=absent("2 of 3 holdings have no price (CINDER, "
                                 "ZEBRA), so the account total cannot be "
                                 "reached without inventing one"))
        assert amount["status"] == "absent"
        assert "sized this as a share of the account" in amount["reason"]
        # …and the account's own reason travels, so the reader is told what to
        # go and fix rather than that "something" is missing
        assert "CINDER" in amount["reason"]
        assert "value" not in amount

    def test_a_share_count_with_no_price_is_absent(self):
        amount = self._amount(commit("shares", 10.0), {})
        assert amount["status"] == "absent"
        assert "sized this in shares" in amount["reason"]
        assert "no price is on record for DELVE" in amount["reason"]
        assert "value" not in amount

    def test_a_price_the_journal_could_not_reach_carries_its_own_reason(self):
        amount = self._amount(
            commit("shares", 10.0),
            {"DELVE": absent("the last close stored for DELVE is from 2024")})
        assert "the last close stored for DELVE is from 2024" in amount["reason"]

    def test_a_unit_the_host_cannot_turn_into_money_is_absent_and_names_it(
            self):
        """The contract refuses a unit outside its own set, so this cannot
        arrive from a loaded strategy today. It is pinned because the failure
        mode of a missing branch here is not a crash — it is a row with no
        amount, which the ordering would have to place somewhere, and any
        placement it invents is a claim about how much room the position has."""
        amount = self._amount(decision("commit", {
            "size": {"unit": "lots", "value": 3.0}, "condition": None}),
            {"DELVE": known(20.0)})
        assert amount["status"] == "absent"
        assert '"lots"' in amount["reason"]
        assert "cannot turn into money" in amount["reason"]
        assert "value" not in amount

    def test_unreachable_amounts_sort_last_in_ticker_order_and_are_kept(self):
        """Listed, never dropped and never ordered by a guess. A name silently
        missing from this screen is a name the user stops thinking about,
        and the reason it is missing — no price — is the fixable kind."""
        out = allocation.view(
            [security("ZEBRA"), security("MARROW"), security("ANVIL")],
            {"ZEBRA": commit("shares", 10.0), "MARROW": commit("shares", 10.0),
             "ANVIL": commit("usd", 700)},
            {"ANVIL": known(20.0)}, folio())
        assert tickers(out["ready"]) == ["ANVIL", "MARROW", "ZEBRA"]
        rows = by_ticker(out["ready"])
        assert rows["ANVIL"]["amount"]["value"] == 700.0
        for t in ("MARROW", "ZEBRA"):
            assert rows[t]["amount"]["status"] == "absent"
            assert rows[t]["amount"]["reason"].strip()
            assert "value" not in rows[t]["amount"]

    def test_no_absent_amount_anywhere_ever_reads_as_a_figure(self):
        """One assertion over every way it can go dark at once, because the
        damage is identical whichever branch produced it: a $0 in this column
        reads as "this position can take nothing more", which is a verdict
        the host has no business reaching."""
        cases = {"NOPRICE": commit("shares", 10.0),
                 "NOUNIT": decision("commit", {"size": {"unit": "lots",
                                                        "value": 3.0},
                                               "condition": None})}
        out = allocation.view(
            [security(t) for t in cases], cases, {},
            folio(account_value=absent("free cash is not recorded")))
        assert len(out["ready"]) == 2
        for entry in out["ready"]:
            assert entry["amount"]["status"] == "absent"
            assert entry["amount"].get("value") is None


class TestTheTargetIsMadeOfItsParts:
    """What the whole position is meant to come to: what is already in, plus
    what may go in now, plus what is being held back. Derived rather than
    declared so it cannot disagree with the parts — and absent whenever a part
    is, because a target that quietly dropped a tranche it could not price
    reads as a smaller commitment than the strategy described."""

    def test_the_target_is_what_is_in_plus_what_goes_in_plus_what_waits(self):
        """Read straight off the numbers, not through the module: $600 of
        BRAMBLE is held, 20% of a $50,000 account is $10,000 going in now, and
        one held-back tranche of 10% is $5,000 — $15,600 in all."""
        out = allocation.view(
            [security("BRAMBLE", shares=40)],
            {"BRAMBLE": commit("weight", 20.0, plan=[
                tranche("weight", 10.0, "the current ratio reaches 2.0")])},
            {"BRAMBLE": known(15.0)},
            folio(holdings=[holding("BRAMBLE", known(600))]))
        [entry] = out["ready"]
        assert entry["target"]["value"] == 15_600.0
        assert entry["target"]["provenance"] == [
            "what is already in, plus what may go in now, plus what is held "
            "back"]

    def test_a_first_purchase_has_nothing_in_and_still_has_a_target(self):
        """Nothing held is not $0 held — the question does not arise yet, and
        a confident zero in that column would be an answer to a question
        nobody asked. The target is still the sum of the parts that exist."""
        out = allocation.view(
            [security("DELVE")], {"DELVE": commit("usd", 2_500)},
            {"DELVE": known(20.0)}, folio())
        [entry] = out["ready"]
        assert entry["committed"] is None
        assert entry["target"]["value"] == 2_500.0
        assert entry["target"]["provenance"] == ["what may go in now"]

    def test_an_amount_that_could_not_be_worked_out_darkens_the_target(self):
        """And the reason names THAT part. The sentence opens by listing
        every part the target is made of, so looking for a part's name
        anywhere in it would pass whichever one went dark — it is the clause
        after "and" that carries the answer, and the answer is what sends
        the reader to the one price they have to go and find."""
        out = allocation.view(
            [security("DELVE", shares=10)], {"DELVE": commit("shares", 10.0)},
            {}, folio(holdings=[holding("DELVE", known(600))]))
        [entry] = out["ready"]
        assert entry["target"]["status"] == "absent"
        assert entry["target"]["reason"].endswith(
            "and what may go in now could not be worked out")
        assert "what is already in could not" not in entry["target"]["reason"]
        assert "value" not in entry["target"]

    def test_a_tranche_that_could_not_be_priced_darkens_the_target(self):
        out = allocation.view(
            [security("DELVE", shares=10)],
            {"DELVE": commit("shares", 10.0, plan=[
                tranche("shares", 10.0, "the price falls another 20%")])},
            {}, folio(holdings=[holding("DELVE", known(600))]))
        [entry] = out["ready"]
        assert entry["target"]["status"] == "absent"
        assert entry["target"]["reason"].endswith(
            "and what may go in now and what is held back could not be "
            "worked out")

    def test_a_holding_the_account_could_not_value_darkens_the_target(self):
        """When the account cannot be totalled, nothing downstream pretends
        it can. Two of the three parts go dark at once here and the target
        names both — one absent part is enough, and the reason has to say
        which so the reader knows there is one price to go and find."""
        out = allocation.view(
            [security("DELVE", shares=10)], {"DELVE": commit("weight", 5.0)},
            {}, folio(account_value=absent("1 of 1 holdings have no price "
                                           "(DELVE), so the account total "
                                           "cannot be reached without "
                                           "inventing one"),
                      holdings=[holding("DELVE", absent("no close is stored "
                                                        "for DELVE"))]))
        [entry] = out["ready"]
        assert entry["target"]["status"] == "absent"
        assert entry["target"]["reason"].endswith(
            "and what is already in and what may go in now could not be "
            "worked out")


class TestAStagedPlanSaysWhatItIsHoldingBack:
    """A staged entry is one decision, not several. The plan is what a single
    tranche cannot say — that this 2% is the first third of an intended 6% —
    and the user seeing that at the moment of the first purchase is the whole
    value of sizing a position while calm."""

    def test_each_tranche_keeps_its_own_condition_and_its_own_money(self):
        conds = ["the current ratio reaches 2.0",
                 "the annual report shows a profit"]
        out = allocation.view(
            [security("DELVE")],
            {"DELVE": commit("weight", 2.0, plan=[
                tranche("weight", 2.0, conds[0]),
                tranche("weight", 2.0, conds[1])])},
            {"DELVE": known(20.0)}, folio())
        plan = out["ready"][0]["plan"]
        assert [t["condition"]["summary"] for t in plan["tranches"]] == conds
        # 2% of a $50,000 account, twice
        assert [t["amount"]["value"] for t in plan["tranches"]] == \
            [1_000.0, 1_000.0]
        assert plan["held_back"]["value"] == 2_000.0
        assert plan["held_back"]["provenance"] == ["2 tranches held back"]

    def test_one_unpriceable_tranche_makes_the_whole_total_absent(self):
        """A total quietly missing one tranche would understate what is being
        committed to — and it would look like a smaller, safer plan than the
        strategy actually described, which is the direction that gets acted
        on. The reason says how many went dark so the number is checkable."""
        out = allocation.view(
            [security("DELVE")],
            {"DELVE": commit("shares", 10.0, plan=[
                tranche("shares", 10.0, "the price falls 20%"),
                tranche("shares", 10.0, "the price falls 40%")])},
            {}, folio())
        held_back = out["ready"][0]["plan"]["held_back"]
        assert held_back["status"] == "absent"
        assert "2 of the 2 tranches" in held_back["reason"]
        assert "value" not in held_back

    def test_a_commit_with_no_plan_has_no_plan_rather_than_an_empty_one(self):
        """"Nothing is held back" and "an empty schedule" are different
        claims, and an empty shape on the row would render as a plan with no
        tranches in it — a staged entry that stages nothing."""
        out = allocation.view([security("DELVE")],
                              {"DELVE": commit("usd", 2_500)},
                              {"DELVE": known(20.0)}, folio())
        assert out["ready"][0]["plan"] is None


class TestAnEmptyScreenStillSaysSomething:
    """Holding cash because nothing qualifies is a position — it is the
    position, most of the time — and a blank screen teaches nothing and reads
    as a load failure. Four standings, because they call for four different
    things and one message covering all of them would be wrong three times."""

    def test_a_journal_tracking_nothing_invites_the_first_security(self):
        out = allocation.view([], {}, {}, folio())
        assert out["standing"]["id"] == "empty"
        # the only standing with an action, because it is the only one where
        # there is an action
        assert out["standing"]["action"] == "Add a security"

    def test_somewhere_to_put_money_and_none_to_put_is_unfunded(self):
        """Reported, never enforced. The list still says where money would
        go — principle 2 — and the standing names the thing nobody recorded
        rather than refusing to show what the strategy said."""
        out = allocation.view(
            [security("DELVE")], {"DELVE": commit("usd", 10_000)},
            {"DELVE": known(20.0)}, folio(cash=known(500)))
        assert out["standing"]["id"] == "unfunded"
        assert "1 position" in out["standing"]["headline"]
        assert tickers(out["ready"]) == ["DELVE"]      # still shown

    def test_cash_that_covers_the_top_of_the_list_is_open(self):
        out = allocation.view(*doom_loop())
        assert out["standing"]["id"] == "open"
        assert "2 positions" in out["standing"]["headline"]

    def test_a_journal_that_never_recorded_cash_is_not_called_unfunded(self):
        """"There is not enough money" and "nobody said how much money there
        is" are different facts, and asserting the first from the second would
        put a shortfall on screen that the journal has no evidence for."""
        out = allocation.view(
            [security("DELVE")], {"DELVE": commit("usd", 10_000)},
            {"DELVE": known(20.0)},
            folio(cash=absent("this journal has no answer for it yet")))
        assert out["standing"]["id"] == "open"

    def test_nothing_qualifying_is_the_strategy_working(self):
        out = allocation.view(
            [security("ANVIL", shares=100), security("BRAMBLE")],
            {"ANVIL": decision("hold", state="sit", rule="already-at-weight",
                               summary="It is where it should be."),
             "BRAMBLE": decision("blocked", state="host:needs-answers",
                                 rule="the-entry-screen",
                                 summary="It is too expensive today.")},
            {}, folio())
        standing = out["standing"]
        assert standing["id"] == "cash"
        assert standing["headline"] == "Nothing qualifies today."
        assert "2 securities" in standing["detail"]
        assert "1 of which you hold" in standing["detail"]
        assert "cash is a position" in standing["detail"]

    def test_the_cash_standing_still_names_every_rule_that_said_no(self):
        """The claim the standing makes — "every name is below with the rule
        that turned it down" — is the useful half of an empty screen, and it
        is a claim about a list this module builds. A name missing from that
        list makes the sentence false with nothing on screen to show it."""
        turned_down = {
            "ANVIL": ("hold", "already-at-weight"),
            "BRAMBLE": ("reduce", "over-its-weight"),
            "CINDER": ("close", "the-sell-rule"),
            "DELVE": ("blocked", "needs-an-answer"),
            "ZEBRA": ("unknown", "nothing-could-be-read")}
        out = allocation.view(
            [security(t) for t in turned_down],
            {t: decision(r, state=f"{t.lower()}-state", rule=rule,
                         summary=f"{rule} settled it.")
             for t, (r, rule) in turned_down.items()},
            {}, folio())
        assert out["standing"]["id"] == "cash"
        assert tickers(out["excluded"]) == sorted(turned_down)
        for entry in out["excluded"]:
            rule = turned_down[entry["ticker"]][1]
            assert entry["rule"] == rule
            assert entry["summary"] == f"{rule} settled it."
            assert entry["state"]["name"]

    def test_only_waiting_is_still_cash_and_the_wait_is_counted(self):
        """A conditional commit is not somewhere to put money today. Counting
        it as open would put a screen in front of the user saying capital may
        go in now when the strategy said the opposite."""
        out = allocation.view(
            [security("ANVIL"), security("BRAMBLE")],
            {"ANVIL": commit("usd", 1_000,
                             condition={"summary": "the price falls 20%"}),
             "BRAMBLE": decision("hold", rule="already-at-weight")},
            {"ANVIL": known(20.0)}, folio())
        assert out["ready"] == []
        assert out["standing"]["id"] == "cash"
        assert "1 is waiting on a condition it stated" in \
            out["standing"]["detail"]


class TestTheScreenMeasuresTheSameAccountTheVerdictsDid:
    """This screen summarises the security pages beside it. An account value
    here that differed from the one behind a weight there would make both
    untrustworthy without either being visibly wrong — so nothing is
    recomputed and nothing is re-priced."""

    def test_the_cash_and_account_figures_are_the_folios_own(self):
        f = folio(holdings=DOOM_HOLDINGS)
        out = allocation.view(*doom_loop()[:3], f)
        assert out["cash"] is f["cash"]
        assert out["account_value"] is f["account_value"]

    def test_a_folio_with_no_figures_at_all_still_renders(self):
        """A journal that has never been asked for a cash balance is the
        ordinary first state, not an error. Every figure that depends on the
        account goes absent with its reason and the screen still lists what
        the strategy said."""
        out = allocation.view([security("DELVE")],
                              {"DELVE": commit("weight", 5.0)},
                              {"DELVE": known(20.0)}, {})
        assert out["cash"]["status"] == "absent"
        assert out["account_value"]["status"] == "absent"
        assert out["ready"][0]["amount"]["status"] == "absent"
        assert out["standing"]["id"] == "open"

    def test_what_is_already_in_is_the_price_the_account_was_built_from(self):
        """`committed` is read off the folio's holdings rather than from the
        price map, because that is the figure the account total was made of.
        Two ways to value the same holding is two screens disagreeing about
        one position, with nothing to say which is wrong."""
        f = folio(holdings=[holding("DELVE", known(1_234))])
        out = allocation.view([security("DELVE", shares=10)],
                              {"DELVE": commit("usd", 500)},
                              {"DELVE": known(99.0)}, f)
        assert out["ready"][0]["committed"] is f["holdings"][0]["market_value"]


class TestAgainstTheHostsOwnPortfolioNode:
    """Everything above hands `view` a folio this file wrote, which is the
    right way to drive an unpriced holding or an absent account without
    building a filing to do it. What it cannot check is that the node the
    HOST builds has the shape this module reads — and the two screens have to
    agree about the account value or both become untrustworthy without either
    being visibly wrong.

    So one pass with nothing between the allocation view and the stores, and
    one assertion that the totals on this screen are the same totals the
    verdicts it summarises were measured against.
    """

    @staticmethod
    def _journal():
        from conftest import entered, journal_for
        from engine import contract, context, dataview, portfolio
        journal, record = journal_for("graham", cash_opening=50_000.0)
        held = portfolio.new_security("ARBR", "Arbor Mills")
        held["price"] = 20.0
        entered(held, current_ratio=2.4, altman_z_score=3.6,
                debt_to_equity=0.6, ltd_to_working_capital=0.4,
                consecutive_annual_loss_years=0)
        portfolio.add_lot(held, None, shares=100.0, price=17.0,
                          opened="2026-01-05",
                          values=dataview.merged_values(held, {}),
                          price_seen={"value": 17.0, "source": "manual",
                                      "date": None, "ticker": "ARBR"})
        idea = portfolio.new_security("DELVE", "Delve Holdings")
        idea["price"] = 8.0
        journal["securities"] = [held, idea]
        effective, _ = contract.check_inputs(record, journal["inputs"],
                                             _chain(record))
        roles = contract.input_roles(record, effective,
                                     context.host_role_answers(journal))
        return journal, record, context.portfolio_view(journal["securities"],
                                                       roles)

    def test_the_hosts_node_has_the_shape_this_module_reads(self):
        _journal, _record, folio = self._journal()
        assert folio["cash"]["status"] == "known"
        assert folio["cash"]["value"] == 50_000.0
        # 100 shares at $20 plus $50,000 free.
        assert folio["account_value"]["value"] == 52_000.0
        assert [h["ticker"] for h in folio["holdings"]] == ["ARBR"]
        assert folio["holdings"][0]["market_value"]["value"] == 2_000.0

    def test_the_screen_and_the_verdicts_measure_against_one_account(self):
        """The reason this reads the host's node rather than working the
        total out again. A second implementation agrees until it does not,
        and the day it stops, one screen reports a weight against $52,000 and
        the other a dollar figure against something else — with nothing
        saying which is wrong."""
        from engine import context
        journal, record, folio = self._journal()
        ctx = context.build_context(journal["securities"][0],
                                    journal["securities"], _chain(record),
                                    journal["inputs"], record=record,
                                    journal=journal)
        assert ctx["portfolio"]["account_value"]["value"] == \
            folio["account_value"]["value"]
        # A weight is market value over that account; a size in weight is
        # converted back against the same figure, so the round trip has to
        # land on the market value it started from.
        weight = ctx["position"]["weight"]["value"]
        out = allocation.view(
            journal["securities"],
            {"ARBR": commit("weight", weight)},
            {"ARBR": known(20.0), "DELVE": known(8.0)}, folio)
        entry = out["ready"][0]
        assert round(entry["amount"]["value"], 6) == 2_000.0
        assert entry["committed"]["value"] == 2_000.0

    def test_a_holding_with_no_price_darkens_the_account_not_the_screen(self):
        """One unpriced HOLDING makes the account total absent — not a
        missing cash answer, which is a different absence with a different
        fix. So the cash role is answered here and the second holding is the
        only thing missing, or the test would pass for the wrong reason.

        What the screen does with it is the point: every weight-sized amount
        goes absent with the account's own reason, and every name still
        renders. An entry that vanished because a figure could not be reached
        would be the tool hiding a decision it could not score.
        """
        from engine import context, contract, portfolio
        journal, record, _folio = self._journal()
        dark = portfolio.new_security("MURK", "Murk Industries")
        portfolio.add_lot(dark, None, shares=10.0, price=5.0,
                          opened="2026-02-01", values={},
                          price_seen={"value": 5.0, "source": "manual",
                                      "date": None, "ticker": "MURK"})
        journal["securities"].append(dark)
        effective, _ = contract.check_inputs(record, journal["inputs"],
                                             _chain(record))
        folio = context.portfolio_view(
            journal["securities"],
            contract.input_roles(record, effective,
                                 context.host_role_answers(journal)))
        assert folio["cash"]["status"] == "known"
        assert folio["account_value"]["status"] == "absent"
        assert "MURK" in folio["account_value"]["reason"]

        out = allocation.view(
            journal["securities"],
            {"ARBR": commit("weight", 3.0)},
            {"ARBR": known(20.0)}, folio)
        assert len(out["ready"]) == 1
        assert out["ready"][0]["amount"]["status"] == "absent"
        assert "MURK" in out["ready"][0]["amount"]["reason"]
        # Both names the strategy said nothing about are still listed.
        assert {e["ticker"] for e in out["excluded"]} == {"DELVE", "MURK"}


def _chain(record):
    from engine import strategy_values
    chain = strategy_values.resolve(record, [])
    assert chain["errors"] == [], chain["errors"]
    return chain["values"]


class TestWhatUnfundedActuallyMeans:
    """The list is ordered by how much each position could take, so its first
    entry is the LARGEST. A funding check that asked only about that one
    would report the entry a reader can least act on as the whole answer —
    "the cash does not cover the first of them" over four smaller names it
    covers comfortably."""

    def _standing(self, sizes, free):
        out = allocation.view(
            [security(t) for t, _ in sizes],
            {t: commit("usd", v) for t, v in sizes},
            {t: known(10.0) for t, _ in sizes},
            folio(cash=known(free)))
        return out["standing"], out

    def test_cash_that_covers_the_smallest_is_not_unfunded(self):
        standing, out = self._standing([("ACME", 9_000), ("DELVE", 400)], 500)
        assert [e["ticker"] for e in out["ready"]] == ["ACME", "DELVE"]
        assert standing["id"] == "open"

    def test_cash_that_covers_nothing_is_unfunded(self):
        standing, _ = self._standing([("ACME", 9_000), ("DELVE", 400)], 50)
        assert standing["id"] == "unfunded"
        assert "does not cover any of them" in standing["headline"]

    def test_the_reason_names_the_smallest_rather_than_the_first(self):
        """What a reader needs when nothing is affordable is the gap they
        have to close, and that is the cheapest entry — not the one at the
        top, which is the furthest out of reach."""
        _standing, out = self._standing([("ACME", 9_000), ("DELVE", 400)], 50)
        line = allocation._affordable(out["ready"],
                                      known(50))["provenance"][0]
        assert "$400" in line and "$9,000" not in line
