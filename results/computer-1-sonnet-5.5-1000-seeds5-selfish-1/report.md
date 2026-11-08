# Model × communication experiment

Hosted-model experiment results.

Status: **complete**; 25/25 episodes complete.

| Model | Communication | Selfish players | Completed | Good total return | Return / good encounter |
|---|---|---:|---:|---:|---:|
| anthropic/claude-sonnet-5.5 | none | 1 | 5 | 259.4000 | 2.8822 |
| anthropic/claude-sonnet-5.5 | public | 1 | 5 | 262.4000 | 2.9156 |
| anthropic/claude-sonnet-5.5 | opponent | 1 | 5 | 248.4000 | 2.7600 |
| anthropic/claude-sonnet-5.5 | good_leader | 1 | 5 | 259.4000 | 2.8822 |
| anthropic/claude-sonnet-5.5 | selfish_leader | 1 | 5 | 265.4000 | 2.9489 |

## Matched contrasts

Differences pair identical seed, role roster, and schedules. Selfish-count groups stay separate.

| Contrast | Model / communication | Selfish players | Matched seeds | Total difference | Normalized difference |
|---|---|---:|---:|---:|---:|
| public minus none | anthropic/claude-sonnet-5.5 | 1 | 5 | 3.0000 | 0.0333 |
| opponent minus none | anthropic/claude-sonnet-5.5 | 1 | 5 | -11.0000 | -0.1222 |
| good_leader minus none | anthropic/claude-sonnet-5.5 | 1 | 5 | 0.0000 | -0.0000 |
| selfish_leader minus none | anthropic/claude-sonnet-5.5 | 1 | 5 | 6.0000 | 0.0667 |
| opponent minus public | anthropic/claude-sonnet-5.5 | 1 | 5 | -14.0000 | -0.1556 |
| good_leader minus public | anthropic/claude-sonnet-5.5 | 1 | 5 | -3.0000 | -0.0333 |
| selfish_leader minus public | anthropic/claude-sonnet-5.5 | 1 | 5 | 3.0000 | 0.0333 |
| good_leader minus opponent | anthropic/claude-sonnet-5.5 | 1 | 5 | 11.0000 | 0.1222 |
| selfish_leader minus opponent | anthropic/claude-sonnet-5.5 | 1 | 5 | 17.0000 | 0.1889 |
| selfish_leader minus good_leader | anthropic/claude-sonnet-5.5 | 1 | 5 | 6.0000 | 0.0667 |

Intervals appear in analysis.json and contrasts.csv. Seeds, not agent-rounds, define sampling units.
Incomplete cells and unmatched pairs remain explicit; zero completed episodes produce no estimates.

All five conditions use simultaneous communication before every round. No communication uses private notes; full communication broadcasts all messages; opponent-only communication delivers each message to the current opponent. Good-leader and selfish-leader conditions predetermine the required leader before gameplay; only the leader broadcasts, while other players write private notes. Agents see the same neutral leader condition and judge the leader using their own encounters and permitted messages. Leader roles remain observer-only. Every condition uses the same request count; no election or midpoint requests occur.

All observer exports contain true roles and private notes. Experimental agents receive only their permitted histories.

Medium is the same requested reasoning setting; providers may spend different token budgets. Collective payoff and identity detection measure separate outcomes.

## Files

Visualization clients should read visualization.json (intentional-agent.visualization/4). The exported visualization.schema.json defines all typed tables. Run intentional-experiments validate-output on this directory before using CSV mirrors.

episodes.csv, cells.csv, contrasts.csv: scores and paired effects. actions.csv, beliefs.csv, messages.csv, leader_assignments.csv, timeline.jsonl: observer traces. elections.csv contains legacy ballots only. usage.csv and status.csv include failed/incomplete episodes. Exact prompts and all response attempts remain under episodes/*/requests/.

## Episode reports

- [seed-0__anthropic__claude-sonnet-5.5__selfish-1__none](episodes/seed-0__anthropic__claude-sonnet-5.5__selfish-1__none/report.md)
- [seed-0__anthropic__claude-sonnet-5.5__selfish-1__opponent](episodes/seed-0__anthropic__claude-sonnet-5.5__selfish-1__opponent/report.md)
- [seed-0__anthropic__claude-sonnet-5.5__selfish-1__selfish_leader](episodes/seed-0__anthropic__claude-sonnet-5.5__selfish-1__selfish_leader/report.md)
- [seed-0__anthropic__claude-sonnet-5.5__selfish-1__good_leader](episodes/seed-0__anthropic__claude-sonnet-5.5__selfish-1__good_leader/report.md)
- [seed-0__anthropic__claude-sonnet-5.5__selfish-1__public](episodes/seed-0__anthropic__claude-sonnet-5.5__selfish-1__public/report.md)
- [seed-1__anthropic__claude-sonnet-5.5__selfish-1__public](episodes/seed-1__anthropic__claude-sonnet-5.5__selfish-1__public/report.md)
- [seed-1__anthropic__claude-sonnet-5.5__selfish-1__selfish_leader](episodes/seed-1__anthropic__claude-sonnet-5.5__selfish-1__selfish_leader/report.md)
- [seed-1__anthropic__claude-sonnet-5.5__selfish-1__good_leader](episodes/seed-1__anthropic__claude-sonnet-5.5__selfish-1__good_leader/report.md)
- [seed-1__anthropic__claude-sonnet-5.5__selfish-1__opponent](episodes/seed-1__anthropic__claude-sonnet-5.5__selfish-1__opponent/report.md)
- [seed-1__anthropic__claude-sonnet-5.5__selfish-1__none](episodes/seed-1__anthropic__claude-sonnet-5.5__selfish-1__none/report.md)
- [seed-2__anthropic__claude-sonnet-5.5__selfish-1__opponent](episodes/seed-2__anthropic__claude-sonnet-5.5__selfish-1__opponent/report.md)
- [seed-2__anthropic__claude-sonnet-5.5__selfish-1__none](episodes/seed-2__anthropic__claude-sonnet-5.5__selfish-1__none/report.md)
- [seed-2__anthropic__claude-sonnet-5.5__selfish-1__public](episodes/seed-2__anthropic__claude-sonnet-5.5__selfish-1__public/report.md)
- [seed-2__anthropic__claude-sonnet-5.5__selfish-1__good_leader](episodes/seed-2__anthropic__claude-sonnet-5.5__selfish-1__good_leader/report.md)
- [seed-2__anthropic__claude-sonnet-5.5__selfish-1__selfish_leader](episodes/seed-2__anthropic__claude-sonnet-5.5__selfish-1__selfish_leader/report.md)
- [seed-3__anthropic__claude-sonnet-5.5__selfish-1__selfish_leader](episodes/seed-3__anthropic__claude-sonnet-5.5__selfish-1__selfish_leader/report.md)
- [seed-3__anthropic__claude-sonnet-5.5__selfish-1__opponent](episodes/seed-3__anthropic__claude-sonnet-5.5__selfish-1__opponent/report.md)
- [seed-3__anthropic__claude-sonnet-5.5__selfish-1__none](episodes/seed-3__anthropic__claude-sonnet-5.5__selfish-1__none/report.md)
- [seed-3__anthropic__claude-sonnet-5.5__selfish-1__good_leader](episodes/seed-3__anthropic__claude-sonnet-5.5__selfish-1__good_leader/report.md)
- [seed-3__anthropic__claude-sonnet-5.5__selfish-1__public](episodes/seed-3__anthropic__claude-sonnet-5.5__selfish-1__public/report.md)
- [seed-4__anthropic__claude-sonnet-5.5__selfish-1__none](episodes/seed-4__anthropic__claude-sonnet-5.5__selfish-1__none/report.md)
- [seed-4__anthropic__claude-sonnet-5.5__selfish-1__public](episodes/seed-4__anthropic__claude-sonnet-5.5__selfish-1__public/report.md)
- [seed-4__anthropic__claude-sonnet-5.5__selfish-1__selfish_leader](episodes/seed-4__anthropic__claude-sonnet-5.5__selfish-1__selfish_leader/report.md)
- [seed-4__anthropic__claude-sonnet-5.5__selfish-1__good_leader](episodes/seed-4__anthropic__claude-sonnet-5.5__selfish-1__good_leader/report.md)
- [seed-4__anthropic__claude-sonnet-5.5__selfish-1__opponent](episodes/seed-4__anthropic__claude-sonnet-5.5__selfish-1__opponent/report.md)
