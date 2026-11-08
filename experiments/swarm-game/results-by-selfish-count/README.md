# Main-study results by selfish-agent count

Verified on November 7, 2026 (Pacific). Each planned cohort contains five communication modes × 12 seeds, with 10 agents and 10 rounds per episode.

| Folder | Selfish agents | Good agents | Planned episodes | Verified complete | Results |
|---|---:|---:|---:|---:|---|
| [selfish-1](selfish-1/) | 1 | 9 | 60 | Unknown | [Missing-results status](selfish-1/README.md) |
| [3 selfish agents results](3%20selfish%20agents%20results/) | 3 | 7 | 60 | 60 | [Report](3%20selfish%20agents%20results/report.md), [provenance and archive](3%20selfish%20agents%20results/README.md) |
| [5 selfish agents results](5%20selfish%20agents%20results/) | 5 | 5 | 60 | 60 | [Report](5%20selfish%20agents%20results/report.md), [provenance and archive](5%20selfish%20agents%20results/README.md) |

**120 completed episodes are verified; completion of all 180 is not established.**

For both available cohorts, all 60 episode rows, status rows and final checkpoints were checked: unique seed/mode coverage, correct selfish-role count, completed round 10, 50 paired encounters and 10 final reports per episode. Each mode contains 12 completed episodes. This organization check did not replay the archived model responses.

The `3 selfish agents results` and `5 selfish agents results` folders contain byte-identical copies of the published records, including complete compressed archives. Original records remain under [records](../records/README.md); these copies are not additional cohorts. Each folder's `organization-verification.json` records source paths, commit and SHA-256 hashes. Treat original records as authoritative; any future updates must keep these copies synchronized.

Source snapshot: `e794ea77a754ba786b2360b4b7724c6ce3754407` on `results/3-bad-agents`. Original README provenance and recovery disclosures are preserved.
