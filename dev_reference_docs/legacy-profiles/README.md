# Retired profile YAML — source material, not code

These four files are the rulesets from the profile system the program used
before strategies became plugins. **Nothing reads them.** They are not
loaded, not copied into a user's data directory, and not referenced from
anywhere in `engine/`, `app.py` or `ui/`.

They are kept for one reason: they are the input to authoring the real
strategies (ticket P4). The thresholds carry over. The structure does not —
tier rollup, sell watch and the position clock were three separate paths that
each reached a conclusion, and under the contract they become one decision
matrix returning one state.

Read them as a record of *what levels a strategy demanded*, and of the
written reasoning beside each one (`why:` blocks), which is the part worth
preserving. Do not read them as a description of how a strategy is now
structured; for that, see `engine/contract.py`.

Two known problems to fix while porting rather than carry over, both logged
against ticket P11:

- `eps_cagr_5y` and `revenue_cagr_3y` declare their confirmation in
  quarterly filings but are annual-window measures, so as written they
  demand years of evidence to confirm what the window already smooths.
- `eps_cagr_5y`'s "very small base" caution is unquantified. A near-zero
  base flatters a CAGR, which is the dangerous direction.

The thresholds in these files were authored from an expert report and have
never been validated against what those investors would actually say. They
are a starting point, not an authority.
