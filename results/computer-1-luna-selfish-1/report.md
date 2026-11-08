# Model × communication experiment

Hosted-model experiment results.

Status: **complete**; 60/60 episodes complete.

| Model | Communication | Selfish players | Completed | Good total return | Return / good encounter |
|---|---|---:|---:|---:|---:|
| openai/gpt-6-luna | none | 1 | 12 | 232.8333 | 2.5870 |
| openai/gpt-6-luna | public | 1 | 12 | 240.1667 | 2.6685 |
| openai/gpt-6-luna | opponent | 1 | 12 | 231.8333 | 2.5759 |
| openai/gpt-6-luna | good_leader | 1 | 12 | 236.0833 | 2.6231 |
| openai/gpt-6-luna | selfish_leader | 1 | 12 | 233.0000 | 2.5889 |

## Matched contrasts

Differences pair identical seed, role roster, and schedules. Selfish-count groups stay separate.

| Contrast | Model / communication | Selfish players | Matched seeds | Total difference | Normalized difference |
|---|---|---:|---:|---:|---:|
| public minus none | openai/gpt-6-luna | 1 | 12 | 7.3333 | 0.0815 |
| opponent minus none | openai/gpt-6-luna | 1 | 12 | -1.0000 | -0.0111 |
| good_leader minus none | openai/gpt-6-luna | 1 | 12 | 3.2500 | 0.0361 |
| selfish_leader minus none | openai/gpt-6-luna | 1 | 12 | 0.1667 | 0.0019 |
| opponent minus public | openai/gpt-6-luna | 1 | 12 | -8.3333 | -0.0926 |
| good_leader minus public | openai/gpt-6-luna | 1 | 12 | -4.0833 | -0.0454 |
| selfish_leader minus public | openai/gpt-6-luna | 1 | 12 | -7.1667 | -0.0796 |
| good_leader minus opponent | openai/gpt-6-luna | 1 | 12 | 4.2500 | 0.0472 |
| selfish_leader minus opponent | openai/gpt-6-luna | 1 | 12 | 1.1667 | 0.0130 |
| selfish_leader minus good_leader | openai/gpt-6-luna | 1 | 12 | -3.0833 | -0.0343 |

Intervals appear in analysis.json and contrasts.csv. Seeds, not agent-rounds, define sampling units.
Incomplete cells and unmatched pairs remain explicit; zero completed episodes produce no estimates.

All five conditions use simultaneous communication before every round. No communication uses private notes; full communication broadcasts all messages; opponent-only communication delivers each message to the current opponent. Good-leader and selfish-leader conditions predetermine the required leader before gameplay; only the leader broadcasts, while other players write private notes. Agents see the same neutral leader condition and judge the leader using their own encounters and permitted messages. Leader roles remain observer-only. Every condition uses the same request count; no election or midpoint requests occur.

All observer exports contain true roles and private notes. Experimental agents receive only their permitted histories.

Medium is the same requested reasoning setting; providers may spend different token budgets. Collective payoff and identity detection measure separate outcomes.

## Files

Visualization clients should read visualization.json (intentional-agent.visualization/4). The exported visualization.schema.json defines all typed tables. Run intentional-experiments validate-output on this directory before using CSV mirrors.

episodes.csv, cells.csv, contrasts.csv: scores and paired effects. actions.csv, beliefs.csv, messages.csv, leader_assignments.csv, timeline.jsonl: observer traces. elections.csv contains legacy ballots only. usage.csv and status.csv include failed/incomplete episodes. Exact prompts and all response attempts remain under episodes/*/requests/.

## Episode reports

- [seed-0__openai__gpt-6-luna__selfish-1__none](episodes/seed-0__openai__gpt-6-luna__selfish-1__none/report.md)
- [seed-0__openai__gpt-6-luna__selfish-1__opponent](episodes/seed-0__openai__gpt-6-luna__selfish-1__opponent/report.md)
- [seed-0__openai__gpt-6-luna__selfish-1__selfish_leader](episodes/seed-0__openai__gpt-6-luna__selfish-1__selfish_leader/report.md)
- [seed-0__openai__gpt-6-luna__selfish-1__good_leader](episodes/seed-0__openai__gpt-6-luna__selfish-1__good_leader/report.md)
- [seed-0__openai__gpt-6-luna__selfish-1__public](episodes/seed-0__openai__gpt-6-luna__selfish-1__public/report.md)
- [seed-1__openai__gpt-6-luna__selfish-1__public](episodes/seed-1__openai__gpt-6-luna__selfish-1__public/report.md)
- [seed-1__openai__gpt-6-luna__selfish-1__selfish_leader](episodes/seed-1__openai__gpt-6-luna__selfish-1__selfish_leader/report.md)
- [seed-1__openai__gpt-6-luna__selfish-1__good_leader](episodes/seed-1__openai__gpt-6-luna__selfish-1__good_leader/report.md)
- [seed-1__openai__gpt-6-luna__selfish-1__opponent](episodes/seed-1__openai__gpt-6-luna__selfish-1__opponent/report.md)
- [seed-1__openai__gpt-6-luna__selfish-1__none](episodes/seed-1__openai__gpt-6-luna__selfish-1__none/report.md)
- [seed-2__openai__gpt-6-luna__selfish-1__opponent](episodes/seed-2__openai__gpt-6-luna__selfish-1__opponent/report.md)
- [seed-2__openai__gpt-6-luna__selfish-1__none](episodes/seed-2__openai__gpt-6-luna__selfish-1__none/report.md)
- [seed-2__openai__gpt-6-luna__selfish-1__public](episodes/seed-2__openai__gpt-6-luna__selfish-1__public/report.md)
- [seed-2__openai__gpt-6-luna__selfish-1__good_leader](episodes/seed-2__openai__gpt-6-luna__selfish-1__good_leader/report.md)
- [seed-2__openai__gpt-6-luna__selfish-1__selfish_leader](episodes/seed-2__openai__gpt-6-luna__selfish-1__selfish_leader/report.md)
- [seed-3__openai__gpt-6-luna__selfish-1__selfish_leader](episodes/seed-3__openai__gpt-6-luna__selfish-1__selfish_leader/report.md)
- [seed-3__openai__gpt-6-luna__selfish-1__opponent](episodes/seed-3__openai__gpt-6-luna__selfish-1__opponent/report.md)
- [seed-3__openai__gpt-6-luna__selfish-1__none](episodes/seed-3__openai__gpt-6-luna__selfish-1__none/report.md)
- [seed-3__openai__gpt-6-luna__selfish-1__good_leader](episodes/seed-3__openai__gpt-6-luna__selfish-1__good_leader/report.md)
- [seed-3__openai__gpt-6-luna__selfish-1__public](episodes/seed-3__openai__gpt-6-luna__selfish-1__public/report.md)
- [seed-4__openai__gpt-6-luna__selfish-1__none](episodes/seed-4__openai__gpt-6-luna__selfish-1__none/report.md)
- [seed-4__openai__gpt-6-luna__selfish-1__public](episodes/seed-4__openai__gpt-6-luna__selfish-1__public/report.md)
- [seed-4__openai__gpt-6-luna__selfish-1__selfish_leader](episodes/seed-4__openai__gpt-6-luna__selfish-1__selfish_leader/report.md)
- [seed-4__openai__gpt-6-luna__selfish-1__good_leader](episodes/seed-4__openai__gpt-6-luna__selfish-1__good_leader/report.md)
- [seed-4__openai__gpt-6-luna__selfish-1__opponent](episodes/seed-4__openai__gpt-6-luna__selfish-1__opponent/report.md)
- [seed-5__openai__gpt-6-luna__selfish-1__opponent](episodes/seed-5__openai__gpt-6-luna__selfish-1__opponent/report.md)
- [seed-5__openai__gpt-6-luna__selfish-1__good_leader](episodes/seed-5__openai__gpt-6-luna__selfish-1__good_leader/report.md)
- [seed-5__openai__gpt-6-luna__selfish-1__selfish_leader](episodes/seed-5__openai__gpt-6-luna__selfish-1__selfish_leader/report.md)
- [seed-5__openai__gpt-6-luna__selfish-1__none](episodes/seed-5__openai__gpt-6-luna__selfish-1__none/report.md)
- [seed-5__openai__gpt-6-luna__selfish-1__public](episodes/seed-5__openai__gpt-6-luna__selfish-1__public/report.md)
- [seed-6__openai__gpt-6-luna__selfish-1__none](episodes/seed-6__openai__gpt-6-luna__selfish-1__none/report.md)
- [seed-6__openai__gpt-6-luna__selfish-1__selfish_leader](episodes/seed-6__openai__gpt-6-luna__selfish-1__selfish_leader/report.md)
- [seed-6__openai__gpt-6-luna__selfish-1__opponent](episodes/seed-6__openai__gpt-6-luna__selfish-1__opponent/report.md)
- [seed-6__openai__gpt-6-luna__selfish-1__good_leader](episodes/seed-6__openai__gpt-6-luna__selfish-1__good_leader/report.md)
- [seed-6__openai__gpt-6-luna__selfish-1__public](episodes/seed-6__openai__gpt-6-luna__selfish-1__public/report.md)
- [seed-7__openai__gpt-6-luna__selfish-1__good_leader](episodes/seed-7__openai__gpt-6-luna__selfish-1__good_leader/report.md)
- [seed-7__openai__gpt-6-luna__selfish-1__selfish_leader](episodes/seed-7__openai__gpt-6-luna__selfish-1__selfish_leader/report.md)
- [seed-7__openai__gpt-6-luna__selfish-1__none](episodes/seed-7__openai__gpt-6-luna__selfish-1__none/report.md)
- [seed-7__openai__gpt-6-luna__selfish-1__public](episodes/seed-7__openai__gpt-6-luna__selfish-1__public/report.md)
- [seed-7__openai__gpt-6-luna__selfish-1__opponent](episodes/seed-7__openai__gpt-6-luna__selfish-1__opponent/report.md)
- [seed-8__openai__gpt-6-luna__selfish-1__public](episodes/seed-8__openai__gpt-6-luna__selfish-1__public/report.md)
- [seed-8__openai__gpt-6-luna__selfish-1__good_leader](episodes/seed-8__openai__gpt-6-luna__selfish-1__good_leader/report.md)
- [seed-8__openai__gpt-6-luna__selfish-1__none](episodes/seed-8__openai__gpt-6-luna__selfish-1__none/report.md)
- [seed-8__openai__gpt-6-luna__selfish-1__selfish_leader](episodes/seed-8__openai__gpt-6-luna__selfish-1__selfish_leader/report.md)
- [seed-8__openai__gpt-6-luna__selfish-1__opponent](episodes/seed-8__openai__gpt-6-luna__selfish-1__opponent/report.md)
- [seed-9__openai__gpt-6-luna__selfish-1__selfish_leader](episodes/seed-9__openai__gpt-6-luna__selfish-1__selfish_leader/report.md)
- [seed-9__openai__gpt-6-luna__selfish-1__none](episodes/seed-9__openai__gpt-6-luna__selfish-1__none/report.md)
- [seed-9__openai__gpt-6-luna__selfish-1__good_leader](episodes/seed-9__openai__gpt-6-luna__selfish-1__good_leader/report.md)
- [seed-9__openai__gpt-6-luna__selfish-1__opponent](episodes/seed-9__openai__gpt-6-luna__selfish-1__opponent/report.md)
- [seed-9__openai__gpt-6-luna__selfish-1__public](episodes/seed-9__openai__gpt-6-luna__selfish-1__public/report.md)
- [seed-10__openai__gpt-6-luna__selfish-1__good_leader](episodes/seed-10__openai__gpt-6-luna__selfish-1__good_leader/report.md)
- [seed-10__openai__gpt-6-luna__selfish-1__selfish_leader](episodes/seed-10__openai__gpt-6-luna__selfish-1__selfish_leader/report.md)
- [seed-10__openai__gpt-6-luna__selfish-1__opponent](episodes/seed-10__openai__gpt-6-luna__selfish-1__opponent/report.md)
- [seed-10__openai__gpt-6-luna__selfish-1__public](episodes/seed-10__openai__gpt-6-luna__selfish-1__public/report.md)
- [seed-10__openai__gpt-6-luna__selfish-1__none](episodes/seed-10__openai__gpt-6-luna__selfish-1__none/report.md)
- [seed-11__openai__gpt-6-luna__selfish-1__none](episodes/seed-11__openai__gpt-6-luna__selfish-1__none/report.md)
- [seed-11__openai__gpt-6-luna__selfish-1__opponent](episodes/seed-11__openai__gpt-6-luna__selfish-1__opponent/report.md)
- [seed-11__openai__gpt-6-luna__selfish-1__good_leader](episodes/seed-11__openai__gpt-6-luna__selfish-1__good_leader/report.md)
- [seed-11__openai__gpt-6-luna__selfish-1__selfish_leader](episodes/seed-11__openai__gpt-6-luna__selfish-1__selfish_leader/report.md)
- [seed-11__openai__gpt-6-luna__selfish-1__public](episodes/seed-11__openai__gpt-6-luna__selfish-1__public/report.md)
