# Recorded pipeline input — NOT ground truth

These are the gateway's extracted raw facts for the same filings the
hand-read ground truth covers, recorded once from live EDGAR under the pinned
edgartools version, gzipped. They exist so the resolution and period tests can
run offline against real filing shapes.

The evidence hierarchy matters: `../groundtruth/` is the truth (hand-read from
primary documents); these files are what the pipeline *saw*. When a test
comparing the two fails, the pipeline or these recordings are wrong — never
the ground truth. If the gateway's extraction shape changes (GATEWAY_VERSION
bump or an edgartools upgrade), re-record these from a fresh fetch and re-run
the comparison; do not hand-edit them.
