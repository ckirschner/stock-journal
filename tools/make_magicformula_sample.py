"""Builds data.template/sample-magic-formula.json — the fourth journal.

Every company and every figure below is invented. Nothing here is a
recommendation, a model portfolio, or a real security; the tickers are made
up, the numbers are made up, and the two lists are made up. In particular
neither list is anything Greenblatt's screen ever returned — they exist to
show what a journal looks like once you have imported one.

Run from the project root:

    python tools/make_magicformula_sample.py

What this one is for
--------------------
The other three samples are about judging companies. This one is about a
journal that judges none, and the story it has to tell is a *shape* rather
than a set of verdicts: two lists a year apart, positions started a few at a
time off the first, one that has gone all the way round the loop, and one
that came back on the second list and had its year restarted.

It is deliberately **mid-build**, because that is where a user of this method
spends their first year and it is the state the other three samples have no
equivalent of. It holds six names against a target of twenty-five and is
still staging: the journal is not broken, it is eight months into a job that
takes about eight months, and a reader who does not know that will think the
tool has stopped working.

Three states, and why the sample cannot show them
-------------------------------------------------
Five of the strategy's seven states are here. The two that are missing are
missing for the same structural reason, and it is worth understanding before
reading the stories, because it is a real property of this strategy rather
than a gap in this file.

**Three of the seven states are facts about the JOURNAL, not about a name**,
and no two of them can be true on the same day:

- `waiting-on-a-list` needs the current list to be too old to buy from.
- `not-time-yet` needs the portfolio full, or enough names started inside the
  staging window.
- `buy-it` needs neither of those.

Whichever is true is true of every unheld name at once. So one journal on one
day can show exactly one of the three, and this one shows `buy-it` — because
a sample in which nothing may be bought would leave the "Where capital goes"
screen empty, which is the screen this method's staging rule is actually
about. The other two are walked in tests/test_strategy_magicformula.py.

That exclusivity is not an accident of the sample. It follows from the method:
whether it is time to buy is a question about your portfolio and your list,
and the same answer is owed to every name on the list at once. Every other
strategy in this program answers per security because every other strategy is
screening per security.

The stories worth reading
-------------------------
- **The loop closing.** MARLBK was bought off the first list, held its
  year, and was sold the day after it fell due — with the strategy's own
  verdict standing behind the sale. It is now not on the second list and sits
  in Previous holdings. That whole circuit is the method.
- **A year restarting.** FENWCK was bought in August 2025 and is on the
  August 2026 list too, so it was chosen again on fresh prices and fresh
  accounts. It is held, not sold and rebought, and its year now runs from the
  new list's day. This is the one design call in the strategy Greenblatt does
  not make himself.
- **A purchase against the signal.** HALSTD is on neither list. The journal
  said so and it was bought anyway, with the reason on the record — which is
  the third documented way people stop getting this method's results, caught
  where it happens rather than described in a note nobody reads.
- **A name declined.** SUTTBY is on the current list and the verdict says
  buy it. It has been passed over, with a reason, and the verdict has not
  changed — because the strategy's job is to say what the rules say and not
  to agree with you. Whether passing over keeps working out is a question
  about the list, and the record is what makes it answerable later.
- **A name bought off an almost-stale list.** KINVER was bought in July 2026
  off a list pulled the previous August. It was inside the freshness limit by
  a month, and one month later the same purchase would have been refused.
"""

from sample_kit import (buy, import_list, journal, pass_over, sell, security,
                        write)

# The day the stories are written against. Fixed rather than relative, so the
# sample reads the same on the day it is built and a year later.
TODAY = "2026-08-13"

FREE_CASH = 48_000.0

# The two lists. A real pull is thirty or fifty names; these are ten and
# eleven, because a sample carrying fifty ticker strings nobody can act on
# teaches nothing that ten does not and buries the five that have stories.
#
# The floor is what the screen was asked for, and it is provenance rather
# than a rule — nothing reads it. It is here because "ten names" means
# something different at a fifty-million floor than at a billion.
FLOOR = 1_000_000_000.0

FIRST_PULL = "2025-08-04"
FIRST_LIST = ["MARLBK", "BRAMLY", "FENWCK", "TARRNT", "WOOLSN",
              "KINVER", "CRANWL", "ALDERT", "GRIMSB", "NETHRB"]

SECOND_PULL = "2026-08-03"
SECOND_LIST = ["FENWCK", "ODDGLY", "SUTTBY", "ALDERT", "PENKRG",
               "WHARRM", "BEAUDR", "COLNEY", "TREGRN", "MELVRL",
               "STANDH"]

# The two figures the ranking was run on. They are shown beside every verdict
# and they gate nothing — which is the whole reason they are here, because a
# reader looking at a Magic Formula page has to be able to find out what put a
# name in front of them without being told a test was passed.
#
# Entered by hand, like every other figure in a sample: no company here is
# linked to a filer, so nothing is computed from a filing.
def figures(yield_pct, roc_pct):
    return {"earnings_yield": yield_pct, "return_on_capital": roc_pct}


STORIES = {
    "MARLBK": "not-on-your-list",
    "BRAMLY": "time-is-up",
    "FENWCK": "back-on-the-list",
    "TARRNT": "still-running",
    "WOOLSN": "still-running",
    "KINVER": "still-running",
    "HALSTD": "still-running",
    "ODDGLY": "buy-it",
    "SUTTBY": "buy-it",
    "CRANWL": "not-on-your-list",
}


def build():
    journal("Sample — Magic Formula", "magic-formula",
            {"free-cash": FREE_CASH})

    # ---------------------------------------------------------------- year one
    import_list(FIRST_PULL, FIRST_LIST, FLOOR)

    security("MARLBK", "Marlbrook Ceramics", 41.20,
             figures(13.9, 44.0), FIRST_PULL,
             notes=[(FIRST_PULL,
                     "Third on the list I pulled. I have no idea what they "
                     "make beyond the name and that is the method working — "
                     "the ranking looked at three thousand of these and I "
                     "looked at none of them.")])
    security("BRAMLY", "Bramley Tool Works", 27.60,
             figures(15.2, 38.5), FIRST_PULL)
    security("FENWCK", "Fenwick Abrasives", 18.40,
             figures(12.1, 51.0), FIRST_PULL)
    security("TARRNT", "Tarrant Freight", 55.10,
             figures(11.4, 29.8), FIRST_PULL)
    security("WOOLSN", "Woolston Fasteners", 9.85,
             figures(14.6, 33.2), FIRST_PULL)
    security("KINVER", "Kinver Packaging", 62.30,
             figures(10.8, 41.7), FIRST_PULL)
    security("CRANWL", "Cranwell Instruments", 33.75,
             figures(12.7, 36.1), FIRST_PULL)

    # The first tranche: three names a week after the pull. Not ten — the
    # staging rule is the discipline this method lives on.
    buy("MARLBK", 300, 38.10, "2025-08-11")
    buy("BRAMLY", 420, 25.40, "2025-08-11")
    buy("FENWCK", 610, 17.05, "2025-08-18")

    # The second tranche. Dated later than the story strictly needs, and the
    # reason is worth knowing before moving it back: tests/test_sample.py
    # evaluates this journal live, with no pinned clock, so every holding here
    # flips to `time-is-up` on its own anniversary and takes the suite with
    # it. A sample whose only exit is a calendar has a shelf life; what can be
    # controlled is that every name in it turns over at roughly the same
    # distance rather than one of them going first and quietly.
    buy("TARRNT", 190, 52.80, "2026-05-11")

    # ------------------------------------------------- still buying, a year on
    # Both off the FIRST list, which was still inside the freshness limit —
    # ten months old, then eleven. A month later either purchase would have
    # been refused and the journal would have asked for a fresh pull.
    buy("WOOLSN", 900, 9.10, "2026-06-15")
    buy("KINVER", 130, 58.90, "2026-07-06",
        recollection="Last one off the old list. It was eleven months old "
                     "and I could feel the deadline; I would rather have "
                     "waited three weeks and bought off the new one.")

    # A name on neither list, bought anyway. The journal said so.
    security("HALSTD", "Halstead Marine", 14.05,
             figures(9.2, 18.4), "2026-07-18",
             notes=[("2026-07-18",
                     "A friend's tip. Not on the list, and I know that is "
                     "the whole thing I am supposed to not do.")])
    buy("HALSTD", 700, 13.60, "2026-07-20",
        override_reason="Not on either list. I bought it because somebody I "
                        "trust likes it, which is exactly the judgement this "
                        "method exists to keep me from making. Writing it "
                        "down so I can check in a year whether my judgement "
                        "or the list was right.")

    # ------------------------------------------------------ the second pull
    import_list(SECOND_PULL, SECOND_LIST, FLOOR)

    security("ODDGLY", "Oddingley Chemical", 71.90,
             figures(16.3, 47.2), SECOND_PULL)
    security("SUTTBY", "Sutterby Glassworks", 24.15,
             figures(13.1, 39.6), SECOND_PULL)

    # The loop closes: bought off the first list, held its year, sold the day
    # after it fell due, with the strategy's own verdict behind the sale.
    sell("MARLBK", "Hit valuation", 47.80, "2026-08-12")

    # A name the list gave and the reader declined. The verdict does not
    # change — that is principle 2 — and the reason is on the record.
    pass_over("SUTTBY",
              "Second glass company I have been handed in two years and the "
              "first one went nowhere. That is not a reason, it is a "
              "feeling, and I am writing it down so I can find out which.",
              "2026-08-05")

    write("sample-magic-formula.json", "magic-formula", FREE_CASH, TODAY,
          STORIES)


if __name__ == "__main__":
    build()
