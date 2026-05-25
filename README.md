# graph-activity

This repository stores controlled historical activity entries used to populate contribution history with a moderate and realistic pattern.

## Backfill Defaults

- Range: 2023-05-25 to 2026-05-24
- Max commits per day: 3
- Active days per week: 2 to 4
- Skip-weeks rate: 0.20
- Deterministic seed: 2608

## Notes

The commit generator writes incremental entries to `activity.json` and uses historical author/committer dates.
