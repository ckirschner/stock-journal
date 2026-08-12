"""Period assembly: fiscal years, TTM, quarters — and the basis rule.

The rule this module enforces, from the task's decisions: **every period inside
a multi-year window must sit on the same accounting basis, never mixed.** The
subtle failure it is built against: a restated figure and the as-printed
original can live under *different tags*, so tracking original-versus-latest
within a tag never catches it. Here, mixing is impossible by construction:

- Values are resolved per filing (concept_map), so every value carries the
  accession of the filing whose statements it came from. A filing is one
  basis.
- A fiscal year's value is taken from the NEWEST filing that reports it — the
  latest restated basis, which is the default the decisions name.
- Every pair of filings that report the same year is compared at the resolved-
  input level. A disagreement is a restatement (or reclassification) event,
  timestamped by the filing that introduced it.
- A window is served only if no restatement event splits it: if any year in
  the window was last reported *before* a restatement that another year in
  the window sits *after*, the window is refused — absent, with the reason
  naming the year, the filings and both values. No code path returns a
  spliced series.
- Revenue additionally carries tag families (pre-ASC-606 / post). A window
  whose resolved tags span families is refused even when no numeric
  disagreement exists — the modified-retrospective case, where prior years
  were never restated and the numbers can't disagree because no year was ever
  reported on both bases.
- Windows must tile: consecutive fiscal years must abut (each start follows
  the previous end by a day). A fiscal-year change leaves a transition stub in
  the seam; any window spanning it is refused, because a "year over year"
  across a 6-month stub is arithmetic on different-length periods.

Everything here returns plain dicts. `absent` returns carry a `reason` a
person can act on; a reason is never an apology, it says what happened.
"""

from __future__ import annotations

from datetime import date, timedelta

from . import concept_map as cm

ANNUAL_DAYS = (340, 385)     # 53-week years reach 371
QUARTER_DAYS = (80, 100)
REL_TOL = 1e-6               # resolved values from the same basis match exactly
ABS_TOL = 0.005              # per-share figures: sub-cent noise only

ANNUAL_FORMS = ("10-K", "10-K/A", "10-KT", "10-KT/A")
QUARTER_FORMS = ("10-Q", "10-Q/A", "10-QT", "10-QT/A")


def _days(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def _agree(a: float, b: float) -> bool:
    return abs(a - b) <= max(ABS_TOL, REL_TOL * max(abs(a), abs(b)))


def absent(reason: str) -> dict:
    return {"absent": True, "reason": reason}


def _why(a, fallback: str) -> dict:
    """A resolver's own reason where it gave one, else the caller's sentence.

    The point of the channel: "did not resolve on the balance sheet dated
    2023-12-31" is what a reader was told when the line was there and refused
    on its sign. Where the resolver knows which way it failed, that is what
    they get.
    """
    if isinstance(a, dict) and a.get("reason"):
        return absent(str(a["reason"]))
    return absent(fallback)


def is_absent(x) -> bool:
    return x is None or (isinstance(x, dict) and x.get("absent"))


class SeriesBuilder:
    """Assembles series for one company from its stored filings."""

    def __init__(self, filings: list[dict]):
        docs = sorted(filings, key=lambda f: (f.get("filed") or "",
                                              f.get("accession") or ""))
        self.indices = [cm.FilingIndex(f) for f in docs]
        self.annual_fis = [fi for fi in self.indices if fi.form in ANNUAL_FORMS]
        self.quarter_fis = [fi for fi in self.indices if fi.form in QUARTER_FORMS]
        self._annual_cache: dict = {}

    # -- filing picks -------------------------------------------------------
    # "Newest" is always by reporting period first, then filed date within
    # the period: an amendment supersedes its own original, but a late-filed
    # amendment of an OLD quarter must never displace a newer quarter as
    # "current" — that would roll every TTM entry back in time silently.

    @staticmethod
    def _newest(fis):
        if not fis:
            return None
        return max(fis, key=lambda fi: (fi.period_of_report or "",
                                        fi.filed or "", fi.accession or ""))

    def latest_annual_fi(self):
        return self._newest(self.annual_fis)

    def latest_fi(self):
        return self._newest(self.indices)

    def newest_quarterly_after_annual(self):
        la = self.latest_annual_fi()
        if la is None:
            return None
        newer = [fi for fi in self.quarter_fis
                 if (fi.period_of_report or "") > (la.period_of_report or "")]
        return self._newest(newer)

    # -- annual series ------------------------------------------------------

    def _candidate_concepts(self, input_id: str) -> list[str]:
        spec = cm.input_spec(input_id)
        if spec.get("derive"):
            return self._candidate_concepts(spec["derive"])
        if spec.get("derive_sum"):
            out = []
            for sub in spec["derive_sum"]:
                out.extend(self._candidate_concepts(sub))
            return out
        out = []
        for cand in spec.get("candidates") or []:
            if "concept" in cand:
                out.append(cand["concept"])
            elif "sum" in cand:
                out.extend(cand["sum"])
        return out

    def annual_points(self, input_id: str) -> dict:
        """Every annual-duration resolution of an input, grouped by fiscal
        year end, each group newest-filed first."""
        if input_id in self._annual_cache:
            return self._annual_cache[input_id]
        concepts = self._candidate_concepts(input_id)
        zero_ok = bool(cm.input_spec(input_id).get("absent_means_zero"))
        by_end: dict[str, list] = {}
        for fi in self.indices:
            periods = set()
            for c in concepts:
                for (s, e) in fi.durations_of(c):
                    if ANNUAL_DAYS[0] <= _days(s, e) <= ANNUAL_DAYS[1]:
                        periods.add((s, e))
            if zero_ok:
                # The completeness zero can only materialise if the located
                # cash-flow statement's own periods are proposed: a year with
                # no dividends line has no dividend fact to discover a period
                # from, and without this a dividend suspension would leave
                # the year missing instead of zero — a stale streak.
                for (s, e) in fi._cf_periods:
                    if ANNUAL_DAYS[0] <= _days(s, e) <= ANNUAL_DAYS[1]:
                        periods.add((s, e))
            for (s, e) in periods:
                r = cm.resolve_duration(fi, input_id, s, e)
                if not cm.is_absent(r):
                    by_end.setdefault(e, []).append(r)
        for e in by_end:
            by_end[e].sort(key=lambda r: (r["filed"], r["accession"]),
                           reverse=True)
        self._annual_cache[input_id] = by_end
        return by_end

    def _restatement_events(self, by_end: dict) -> list[dict]:
        """Every value transition for a year across filing vintages.

        The event is stamped with the filing that INTRODUCED the changed
        value, not the newest filing that happens to repeat it — later
        filings re-reporting the restated figure are the same basis, and
        stamping them instead would refuse windows that sit entirely on the
        restated side."""
        events = []
        for e, rows in by_end.items():
            seq = sorted(rows, key=lambda r: (r["filed"], r["accession"]))
            for prev, nxt in zip(seq, seq[1:]):
                if not _agree(prev["value"], nxt["value"]):
                    events.append({
                        "year_end": e,
                        "restating_filed": nxt["filed"],
                        "restating_accession": nxt["accession"],
                        "older_filed": prev["filed"],
                        "older_accession": prev["accession"],
                        "older_value": prev["value"],
                        "newer_value": nxt["value"],
                    })
        return events

    def annual_window(self, input_id: str, n_obs: int) -> dict:
        """The last n_obs fiscal years of an input on one accounting basis,
        oldest first, or absent with the reason.

        Returns {"values": [...], "points": [...], "cautions": [...]} —
        points carry full provenance for every observation.
        """
        by_end = self.annual_points(input_id)
        if not by_end:
            return absent(f"no annual figure for {label(input_id)} could be "
                          "resolved from any stored filing")
        ends = sorted(by_end.keys())[-n_obs:]
        if len(ends) < n_obs:
            return absent(f"only {len(ends)} fiscal year(s) of "
                          f"{label(input_id)} are on record; {n_obs} are "
                          "needed for this window")
        points = [by_end[e][0] for e in ends]     # newest filing per year

        # tiling: consecutive years must abut (a transition stub or a hole
        # between them breaks every cross-year comparison)
        for prev, nxt in zip(points, points[1:]):
            gap = _days(prev["end"], nxt["start"])
            if not (0 <= gap <= 7):
                return absent(
                    f"the fiscal years of {label(input_id)} do not tile "
                    f"across this window: {prev['end']} is followed by a "
                    f"period starting {nxt['start']}. A fiscal-year change "
                    "or a missing year sits in between, and a window spanning "
                    "it would compare different-length periods")

        # basis: no restatement event may split the window's source vintages
        events = self._restatement_events(by_end)
        vintages = [p["filed"] for p in points]
        lo, hi = min(vintages), max(vintages)
        for ev in events:
            if lo < ev["restating_filed"] <= hi:
                stale = [p["end"] for p in points
                         if p["filed"] < ev["restating_filed"]]
                return absent(
                    f"{label(input_id)} for FY ending {ev['year_end']} was "
                    f"restated by filing {ev['restating_accession']} "
                    f"({ev['older_value']:,.2f} as first reported, "
                    f"{ev['newer_value']:,.2f} after), and the year(s) ending "
                    f"{', '.join(stale)} were never re-reported on the new "
                    "basis — this window would mix two accounting bases")

        # families: never splice pre-ASC-606 revenue onto post
        fams = {p.get("family") for p in points} - {None, "either"}
        if len(fams) > 1:
            return absent(
                f"{label(input_id)} switches tag family inside this window "
                f"({' and '.join(sorted(fams))}) — the ASC 606 transition "
                "changed what the number measures, and prior years were not "
                "restated onto the new definition")

        cautions = sorted({c for p in points for c in p.get("cautions", [])})
        return {"values": [p["value"] for p in points], "points": points,
                "cautions": cautions}

    def latest_fiscal_years(self, input_id: str, n: int) -> list[str]:
        by_end = self.annual_points(input_id)
        return sorted(by_end.keys())[-n:]

    # -- TTM ----------------------------------------------------------------

    def ttm(self, input_id: str, annual_fi=None, quarter_fi=None) -> dict:
        """Trailing twelve months of a flow input.

        FY from the newest annual report; when a newer quarterly report
        exists, FY − prior-year-to-date + current-year-to-date, with both
        year-to-date figures taken from the SAME quarterly filing (its own
        column and its comparative column), so the only cross-filing seam is
        the FY leg — and that seam is start-date-verified.
        """
        annual_fi = annual_fi or self.latest_annual_fi()
        if annual_fi is None:
            return absent(f"no annual report is on record, so a trailing "
                          f"twelve months of {label(input_id)} cannot start")
        fy_end = annual_fi.period_of_report
        fy_res = self._own_annual(annual_fi, input_id)
        if cm.is_absent(fy_res):
            # The resolver's own reason where it has one. "Did not resolve"
            # was said of a filer that tags no such caption AND of one whose
            # caption is right there tagged with the wrong sign — and only
            # the first of those is something to go and look for.
            return _why(fy_res,
                        f"{label(input_id)} did not resolve in the newest "
                        f"annual report (period {fy_end})")
        d_fy = _days(fy_res["start"], fy_res["end"])
        if not (ANNUAL_DAYS[0] <= d_fy <= ANNUAL_DAYS[1]):
            # A 10-KT's own period is a transition stub. Serving it as "the
            # trailing twelve months" would halve every TTM ratio, confidently.
            return absent(
                f"the newest annual report covers a transition stub of "
                f"{d_fy} days ({fy_res['start']} to {fy_res['end']}), not a "
                f"year; a trailing twelve months of {label(input_id)} cannot "
                "be assembled until a full year on the new fiscal calendar "
                "has been reported")
        q_fi = quarter_fi or self.newest_quarterly_after_annual()
        if q_fi is None:
            out = dict(fy_res)
            out["ttm_basis"] = "fiscal year (no newer quarterly report)"
            return out

        q_end = q_fi.period_of_report
        cur = self._ytd_resolution(q_fi, input_id, q_end)
        if cm.is_absent(cur):
            return _why(cur,
                        f"the year-to-date {label(input_id)} did not resolve "
                        f"in the newest quarterly report ({q_end})")
        prior = self._matching_prior_ytd(q_fi, input_id, cur)
        if cm.is_absent(prior):
            return _why(
                prior,
                f"the prior-year comparative for {label(input_id)} did not "
                f"resolve in the quarterly report ({q_end}), so the trailing "
                "twelve months cannot be assembled without mixing filings")
        if prior["start"] != fy_res["start"]:
            return absent(
                f"the trailing window for {label(input_id)} does not tile: "
                f"the fiscal year starts {fy_res['start']} but the "
                f"comparative year-to-date starts {prior['start']} — a "
                "fiscal-calendar shift sits inside this window")
        # The same discipline annual windows get, on the TTM's three legs:
        # never splice tag families (ASC 606 modified-retrospective), and
        # never combine an FY leg that was restated after the quarterly
        # report was prepared with that report's pre-restatement comparative.
        fams = {fy_res.get("family"), prior.get("family"),
                cur.get("family")} - {None, "either"}
        if len(fams) > 1:
            return absent(
                f"the trailing window for {label(input_id)} would splice tag "
                f"families ({' and '.join(sorted(fams))}) across its legs — "
                "the ASC 606 transition changed what the number measures")
        for ev in self._restatement_events(self.annual_points(input_id)):
            if ev["year_end"] == fy_res["end"] \
                    and ev["restating_filed"] > (q_fi.filed or ""):
                return absent(
                    f"{label(input_id)} for the fiscal year ending "
                    f"{fy_res['end']} was restated by filing "
                    f"{ev['restating_accession']} after the quarterly report "
                    f"({q_fi.accession}) was prepared — the trailing window "
                    "would mix the restated year with pre-restatement "
                    "year-to-date figures")
        value = fy_res["value"] - prior["value"] + cur["value"]
        cautions = sorted(set(fy_res["cautions"] + cur["cautions"]
                              + prior["cautions"]))
        return {"value": value, "input": input_id,
                "ttm_basis": f"FY {fy_res['end']} − YTD {prior['end']} "
                             f"+ YTD {cur['end']}",
                "legs": [fy_res, prior, cur], "cautions": cautions,
                "end": cur["end"], "accession": cur["accession"]}

    def _period_candidates(self, fi, input_id):
        """Candidate durations for an input in one filing: the input's own
        concepts' periods, plus — for completeness-zero inputs — the located
        cash-flow statement's periods, so a nil item's zero can materialise."""
        cands = set()
        for c in self._candidate_concepts(input_id):
            cands.update(fi.durations_of(c))
        if cm.input_spec(input_id).get("absent_means_zero"):
            cands.update(fi._cf_periods)
        return cands

    def _own_annual(self, fi, input_id):
        """The filing's own-period figure — annual for a 10-K, the stub for a
        10-KT (never forced into an annual duration band). Callers that need
        a full year (TTM) must check the duration themselves."""
        end = fi.period_of_report
        cands = {(s, e) for (s, e) in self._period_candidates(fi, input_id)
                 if e == end}
        best = None
        for (s, e) in sorted(cands, key=lambda p: _days(*p), reverse=True):
            d = _days(s, e)
            if fi.form.startswith("10-KT") or ANNUAL_DAYS[0] <= d <= ANNUAL_DAYS[1]:
                best = cm.resolve_duration(fi, input_id, s, e)
                if not cm.is_absent(best):
                    break
        # The last refusal is kept and handed back, so a caller reporting
        # "did not resolve in the newest annual report" can say WHY instead.
        # A period band that proposed no candidate at all has nothing to
        # report and says that.
        return best if best is not None else cm.absent(
            f"no period in {fi.form} {fi.accession} proposes an annual "
            f"duration for {label(input_id)}")

    def _ytd_resolution(self, fi, input_id, q_end):
        """The longest duration ending at the quarter end — the YTD column."""
        cands = {(s, e) for (s, e) in self._period_candidates(fi, input_id)
                 if e == q_end}
        last = None
        for (s, e) in sorted(cands, key=lambda p: _days(*p), reverse=True):
            last = r = cm.resolve_duration(fi, input_id, s, e)
            if not cm.is_absent(r):
                return r
        return last if last is not None else cm.absent(
            f"no year-to-date period for {label(input_id)} ends at {q_end} "
            f"in {fi.form} {fi.accession}")

    def _matching_prior_ytd(self, fi, input_id, cur):
        """The comparative column: same filing, same length (±10 days), ending
        about a year before the current YTD."""
        cur_days = _days(cur["start"], cur["end"])
        cands = set()
        for (s, e) in self._period_candidates(fi, input_id):
            if 340 <= _days(e, cur["end"]) <= 385 \
                    and abs(_days(s, e) - cur_days) <= 10:
                cands.add((s, e))
        last = None
        for (s, e) in sorted(cands):
            last = r = cm.resolve_duration(fi, input_id, s, e)
            if not cm.is_absent(r):
                return r
        return last if last is not None else cm.absent(
            f"no prior-year comparative column for {label(input_id)} is in "
            f"{fi.form} {fi.accession}")

    # -- instants -----------------------------------------------------------

    def latest_balance_fi(self):
        """The newest-period filing that actually carries a balance sheet
        face (period first, filed second — same rule as every other pick)."""
        return self._newest([fi for fi in self.indices if fi.balance_dates()])

    def instant_latest(self, input_id: str) -> dict:
        """An instant input at the newest balance-sheet date on record."""
        fi = self.latest_balance_fi()
        if fi is None:
            return absent("no stored filing carries a balance sheet")
        dates = fi.balance_dates()
        at = fi.period_of_report if fi.period_of_report in dates else dates[-1]
        r = cm.resolve_instant(fi, input_id, at)
        if cm.is_absent(r):
            return _why(r, f"{label(input_id)} did not resolve on the balance "
                           f"sheet dated {at} (filing {fi.accession})")
        return r

    def instant_pair_yoy(self, input_id: str) -> dict:
        """The latest instant and the one about a year earlier, both from the
        same filing (its comparative balance sheet), so both sit on one basis.
        Returns {"now": res, "ago": res} or absent."""
        fi = self.latest_balance_fi()
        if fi is None:
            return absent("no stored filing carries a balance sheet")
        dates = fi.balance_dates()
        at = fi.period_of_report if fi.period_of_report in dates else dates[-1]
        now = cm.resolve_instant(fi, input_id, at)
        if cm.is_absent(now):
            return _why(now, f"{label(input_id)} did not resolve on the "
                             f"balance sheet dated {at}")
        ago_dates = [d for d in dates if 340 <= _days(d, at) <= 385]
        if not ago_dates:
            return absent(
                f"the filing dated {at} carries no comparative balance sheet "
                "about a year earlier, so a year-over-year comparison of "
                f"{label(input_id)} cannot be made on one basis")
        ago = cm.resolve_instant(fi, input_id, ago_dates[-1])
        if cm.is_absent(ago):
            return _why(ago, f"{label(input_id)} did not resolve on the "
                             f"comparative balance sheet dated "
                             f"{ago_dates[-1]}")
        return {"now": now, "ago": ago}

    def instant_series_annual(self, input_id: str, n: int) -> dict:
        """Fiscal-year-end instants for n years, newest-filing-per-date, with
        the same restatement discipline as annual_window (balance sheets get
        restated too). Used for averages like ROE's mean equity."""
        by_date: dict[str, list] = {}
        for fi in self.indices:
            for d in fi.balance_dates():
                r = cm.resolve_instant(fi, input_id, d)
                if not cm.is_absent(r):
                    by_date.setdefault(d, []).append(r)
        if not by_date:
            return absent(f"{label(input_id)} did not resolve on any stored "
                          "balance sheet")
        # keep only fiscal-year-end dates (the dates annual reports close on)
        fy_ends = {fi.period_of_report for fi in self.annual_fis}
        dates = sorted(d for d in by_date if d in fy_ends)[-n:]
        if len(dates) < n:
            return absent(f"only {len(dates)} fiscal-year-end balance "
                          f"sheet(s) carry {label(input_id)}; {n} are needed")
        for a, b in zip(dates, dates[1:]):
            if not (340 <= _days(a, b) <= 385):
                return absent(
                    f"the year-end balance sheets carrying {label(input_id)} "
                    f"do not run annually: {a} is followed by {b} — a missing "
                    "year or a fiscal-year change sits between them, and an "
                    "average across that gap would be wrong")
        for d in by_date:
            by_date[d].sort(key=lambda r: (r["filed"], r["accession"]),
                            reverse=True)
        points = [by_date[d][0] for d in dates]
        events = []
        for d in dates:
            seq = sorted(by_date[d], key=lambda r: (r["filed"], r["accession"]))
            for prev, nxt in zip(seq, seq[1:]):
                if not _agree(prev["value"], nxt["value"]):
                    events.append({"date": d, "restating_filed": nxt["filed"],
                                   "older_value": prev["value"],
                                   "newer_value": nxt["value"],
                                   "restating_accession": nxt["accession"]})
        vintages = [p["filed"] for p in points]
        lo, hi = min(vintages), max(vintages)
        for ev in events:
            if lo < ev["restating_filed"] <= hi:
                return absent(
                    f"{label(input_id)} at {ev['date']} was restated by "
                    f"filing {ev['restating_accession']} "
                    f"({ev['older_value']:,.2f} → {ev['newer_value']:,.2f}) "
                    "and older balance sheets in this window were never "
                    "re-reported — the window would mix bases")
        cautions = sorted({c for p in points for c in p.get("cautions", [])})
        return {"values": [p["value"] for p in points], "points": points,
                "dates": dates, "cautions": cautions}

    # -- quarterly observations (for own-history medians) --------------------

    def quarterly_observation_fis(self, n: int) -> list:
        """The last n reporting periods (10-Qs and 10-Ks), one per period end,
        the original report for each — the filing the market had at the time."""
        by_end: dict[str, object] = {}
        for fi in self.indices:
            e = fi.period_of_report
            if e and e not in by_end:
                by_end[e] = fi          # earliest-filed wins: as first reported
        ends = sorted(by_end.keys())[-n:]
        return [by_end[e] for e in ends]

    def ttm_at(self, input_id: str, fi) -> dict:
        """TTM as of one historical filing's period end, on that filing's own
        basis: a 10-K's fiscal year, or FY − prior YTD + current YTD with the
        annual leg from the newest 10-K filed before this filing."""
        if fi.form in ANNUAL_FORMS:
            r = self._own_annual(fi, input_id)
            if cm.is_absent(r):
                return _why(r, f"{label(input_id)} did not resolve in "
                               f"{fi.accession}")
            d = _days(r["start"], r["end"])
            if not (ANNUAL_DAYS[0] <= d <= ANNUAL_DAYS[1]):
                return absent(
                    f"{fi.accession} covers a {d}-day transition stub, not a "
                    "year — no trailing-twelve-month figure exists at this "
                    "observation")
            return r
        prior_annuals = [a for a in self.annual_fis if a.filed <= fi.filed]
        if not prior_annuals:
            return absent("no annual report precedes this quarter")
        return self.ttm(input_id, annual_fi=prior_annuals[-1], quarter_fi=fi)


# Re-exported from engine/concept_map, which is where an input's declaration
# lives and where the refusals that name one are raised.
label = cm.label
