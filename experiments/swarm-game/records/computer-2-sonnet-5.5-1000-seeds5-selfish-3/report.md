# Model × communication experiment

Hosted-model experiment results.

Status: **complete**; 25/25 episodes complete.

| Model | Communication | Selfish players | Completed | Good total return | Return / good encounter |
|---|---|---:|---:|---:|---:|
| anthropic/claude-sonnet-5.5 | none | 3 | 5 | 191.0000 | 2.7286 |
| anthropic/claude-sonnet-5.5 | public | 3 | 5 | 199.4000 | 2.8486 |
| anthropic/claude-sonnet-5.5 | opponent | 3 | 5 | 186.2000 | 2.6600 |
| anthropic/claude-sonnet-5.5 | good_leader | 3 | 5 | 184.4000 | 2.6343 |
| anthropic/claude-sonnet-5.5 | selfish_leader | 3 | 5 | 194.2000 | 2.7743 |

## Matched contrasts

Differences pair identical seed, role roster, and schedules. Selfish-count groups stay separate.

| Contrast | Model / communication | Selfish players | Matched seeds | Total difference | Normalized difference |
|---|---|---:|---:|---:|---:|
| public minus none | anthropic/claude-sonnet-5.5 | 3 | 5 | 8.4000 | 0.1200 |
| opponent minus none | anthropic/claude-sonnet-5.5 | 3 | 5 | -4.8000 | -0.0686 |
| good_leader minus none | anthropic/claude-sonnet-5.5 | 3 | 5 | -6.6000 | -0.0943 |
| selfish_leader minus none | anthropic/claude-sonnet-5.5 | 3 | 5 | 3.2000 | 0.0457 |
| opponent minus public | anthropic/claude-sonnet-5.5 | 3 | 5 | -13.2000 | -0.1886 |
| good_leader minus public | anthropic/claude-sonnet-5.5 | 3 | 5 | -15.0000 | -0.2143 |
| selfish_leader minus public | anthropic/claude-sonnet-5.5 | 3 | 5 | -5.2000 | -0.0743 |
| good_leader minus opponent | anthropic/claude-sonnet-5.5 | 3 | 5 | -1.8000 | -0.0257 |
| selfish_leader minus opponent | anthropic/claude-sonnet-5.5 | 3 | 5 | 8.0000 | 0.1143 |
| selfish_leader minus good_leader | anthropic/claude-sonnet-5.5 | 3 | 5 | 9.8000 | 0.1400 |

Intervals appear in analysis.json and contrasts.csv. Seeds, not agent-rounds, define sampling units.
Incomplete cells and unmatched pairs remain explicit; zero completed episodes produce no estimates.

All five conditions use simultaneous communication before every round. No communication uses private notes; full communication broadcasts all messages; opponent-only communication delivers each message to the current opponent. Good-leader and selfish-leader conditions predetermine the required leader before gameplay; only the leader broadcasts, while other players write private notes. Agents see the same neutral leader condition and judge the leader using their own encounters and permitted messages. Leader roles remain observer-only. Every condition uses the same request count; no election or midpoint requests occur.

All observer exports contain true roles and private notes. Experimental agents receive only their permitted histories.

Medium is the same requested reasoning setting; providers may spend different token budgets. Collective payoff and identity detection measure separate outcomes.

## Files

Visualization clients should read visualization.json (intentional-agent.visualization/4). The exported visualization.schema.json defines all typed tables. Run intentional-experiments validate-output on this directory before using CSV mirrors.

episodes.csv, cells.csv, contrasts.csv: scores and paired effects. actions.csv, beliefs.csv, messages.csv, leader_assignments.csv, timeline.jsonl: observer traces. elections.csv contains legacy ballots only. usage.csv and status.csv include failed/incomplete episodes. Exact prompts and all response attempts remain under episodes/*/requests/.

## Episode reports

- [seed-0__anthropic__claude-sonnet-5.5__selfish-3__none](episodes/seed-0__anthropic__claude-sonnet-5.5__selfish-3__none/report.md)
- [seed-0__anthropic__claude-sonnet-5.5__selfish-3__opponent](episodes/seed-0__anthropic__claude-sonnet-5.5__selfish-3__opponent/report.md)
- [seed-0__anthropic__claude-sonnet-5.5__selfish-3__selfish_leader](episodes/seed-0__anthropic__claude-sonnet-5.5__selfish-3__selfish_leader/report.md)
- [seed-0__anthropic__claude-sonnet-5.5__selfish-3__good_leader](episodes/seed-0__anthropic__claude-sonnet-5.5__selfish-3__good_leader/report.md)
- [seed-0__anthropic__claude-sonnet-5.5__selfish-3__public](episodes/seed-0__anthropic__claude-sonnet-5.5__selfish-3__public/report.md)
- [seed-1__anthropic__claude-sonnet-5.5__selfish-3__public](episodes/seed-1__anthropic__claude-sonnet-5.5__selfish-3__public/report.md)
- [seed-1__anthropic__claude-sonnet-5.5__selfish-3__selfish_leader](episodes/seed-1__anthropic__claude-sonnet-5.5__selfish-3__selfish_leader/report.md)
- [seed-1__anthropic__claude-sonnet-5.5__selfish-3__good_leader](episodes/seed-1__anthropic__claude-sonnet-5.5__selfish-3__good_leader/report.md)
- [seed-1__anthropic__claude-sonnet-5.5__selfish-3__opponent](episodes/seed-1__anthropic__claude-sonnet-5.5__selfish-3__opponent/report.md)
- [seed-1__anthropic__claude-sonnet-5.5__selfish-3__none](episodes/seed-1__anthropic__claude-sonnet-5.5__selfish-3__none/report.md)
- [seed-2__anthropic__claude-sonnet-5.5__selfish-3__opponent](episodes/seed-2__anthropic__claude-sonnet-5.5__selfish-3__opponent/report.md)
- [seed-2__anthropic__claude-sonnet-5.5__selfish-3__none](episodes/seed-2__anthropic__claude-sonnet-5.5__selfish-3__none/report.md)
- [seed-2__anthropic__claude-sonnet-5.5__selfish-3__public](episodes/seed-2__anthropic__claude-sonnet-5.5__selfish-3__public/report.md)
- [seed-2__anthropic__claude-sonnet-5.5__selfish-3__good_leader](episodes/seed-2__anthropic__claude-sonnet-5.5__selfish-3__good_leader/report.md)
- [seed-2__anthropic__claude-sonnet-5.5__selfish-3__selfish_leader](episodes/seed-2__anthropic__claude-sonnet-5.5__selfish-3__selfish_leader/report.md)
- [seed-3__anthropic__claude-sonnet-5.5__selfish-3__selfish_leader](episodes/seed-3__anthropic__claude-sonnet-5.5__selfish-3__selfish_leader/report.md)
- [seed-3__anthropic__claude-sonnet-5.5__selfish-3__opponent](episodes/seed-3__anthropic__claude-sonnet-5.5__selfish-3__opponent/report.md)
- [seed-3__anthropic__claude-sonnet-5.5__selfish-3__none](episodes/seed-3__anthropic__claude-sonnet-5.5__selfish-3__none/report.md)
- [seed-3__anthropic__claude-sonnet-5.5__selfish-3__good_leader](episodes/seed-3__anthropic__claude-sonnet-5.5__selfish-3__good_leader/report.md)
- [seed-3__anthropic__claude-sonnet-5.5__selfish-3__public](episodes/seed-3__anthropic__claude-sonnet-5.5__selfish-3__public/report.md)
- [seed-4__anthropic__claude-sonnet-5.5__selfish-3__none](episodes/seed-4__anthropic__claude-sonnet-5.5__selfish-3__none/report.md)
- [seed-4__anthropic__claude-sonnet-5.5__selfish-3__public](episodes/seed-4__anthropic__claude-sonnet-5.5__selfish-3__public/report.md)
- [seed-4__anthropic__claude-sonnet-5.5__selfish-3__selfish_leader](episodes/seed-4__anthropic__claude-sonnet-5.5__selfish-3__selfish_leader/report.md)
- [seed-4__anthropic__claude-sonnet-5.5__selfish-3__good_leader](episodes/seed-4__anthropic__claude-sonnet-5.5__selfish-3__good_leader/report.md)
- [seed-4__anthropic__claude-sonnet-5.5__selfish-3__opponent](episodes/seed-4__anthropic__claude-sonnet-5.5__selfish-3__opponent/report.md)
