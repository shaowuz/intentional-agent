# Model × communication experiment

Hosted-model experiment results.

Status: **complete**; 60/60 episodes complete.

| Model | Communication | Selfish players | Completed | Good total return | Return / good encounter |
|---|---|---:|---:|---:|---:|
| openai/gpt-6-luna | none | 5 | 12 | 69.6667 | 1.3933 |
| openai/gpt-6-luna | public | 5 | 12 | 85.4167 | 1.7083 |
| openai/gpt-6-luna | opponent | 5 | 12 | 69.2500 | 1.3850 |
| openai/gpt-6-luna | good_leader | 5 | 12 | 75.3333 | 1.5067 |
| openai/gpt-6-luna | selfish_leader | 5 | 12 | 69.2500 | 1.3850 |

## Matched contrasts

Differences pair identical seed, role roster, and schedules. Selfish-count groups stay separate.

| Contrast | Model / communication | Selfish players | Matched seeds | Total difference | Normalized difference |
|---|---|---:|---:|---:|---:|
| public minus none | openai/gpt-6-luna | 5 | 12 | 15.7500 | 0.3150 |
| opponent minus none | openai/gpt-6-luna | 5 | 12 | -0.4167 | -0.0083 |
| good_leader minus none | openai/gpt-6-luna | 5 | 12 | 5.6667 | 0.1133 |
| selfish_leader minus none | openai/gpt-6-luna | 5 | 12 | -0.4167 | -0.0083 |
| opponent minus public | openai/gpt-6-luna | 5 | 12 | -16.1667 | -0.3233 |
| good_leader minus public | openai/gpt-6-luna | 5 | 12 | -10.0833 | -0.2017 |
| selfish_leader minus public | openai/gpt-6-luna | 5 | 12 | -16.1667 | -0.3233 |
| good_leader minus opponent | openai/gpt-6-luna | 5 | 12 | 6.0833 | 0.1217 |
| selfish_leader minus opponent | openai/gpt-6-luna | 5 | 12 | 0.0000 | 0.0000 |
| selfish_leader minus good_leader | openai/gpt-6-luna | 5 | 12 | -6.0833 | -0.1217 |

Intervals appear in analysis.json and contrasts.csv. Seeds, not agent-rounds, define sampling units.
Incomplete cells and unmatched pairs remain explicit; zero completed episodes produce no estimates.

All five conditions use simultaneous communication before every round. No communication uses private notes; full communication broadcasts all messages; opponent-only communication delivers each message to the current opponent. Good-leader and selfish-leader conditions predetermine the required leader before gameplay; only the leader broadcasts, while other players write private notes. Agents see the same neutral leader condition and judge the leader using their own encounters and permitted messages. Leader roles remain observer-only. Every condition uses the same request count; no election or midpoint requests occur.

All observer exports contain true roles and private notes. Experimental agents receive only their permitted histories.

Medium is the same requested reasoning setting; providers may spend different token budgets. Collective payoff and identity detection measure separate outcomes.

## Files

Visualization clients should read visualization.json (intentional-agent.visualization/4). The exported visualization.schema.json defines all typed tables. Run intentional-experiments validate-output on this directory before using CSV mirrors.

episodes.csv, cells.csv, contrasts.csv: scores and paired effects. actions.csv, beliefs.csv, messages.csv, leader_assignments.csv, timeline.jsonl: observer traces. elections.csv contains legacy ballots only. usage.csv and status.csv include failed/incomplete episodes. Exact prompts and all response attempts remain under episodes/*/requests/.

## Episode reports

- [seed-0__openai__gpt-6-luna__selfish-5__none](episodes/seed-0__openai__gpt-6-luna__selfish-5__none/report.md)
- [seed-0__openai__gpt-6-luna__selfish-5__opponent](episodes/seed-0__openai__gpt-6-luna__selfish-5__opponent/report.md)
- [seed-0__openai__gpt-6-luna__selfish-5__selfish_leader](episodes/seed-0__openai__gpt-6-luna__selfish-5__selfish_leader/report.md)
- [seed-0__openai__gpt-6-luna__selfish-5__good_leader](episodes/seed-0__openai__gpt-6-luna__selfish-5__good_leader/report.md)
- [seed-0__openai__gpt-6-luna__selfish-5__public](episodes/seed-0__openai__gpt-6-luna__selfish-5__public/report.md)
- [seed-1__openai__gpt-6-luna__selfish-5__public](episodes/seed-1__openai__gpt-6-luna__selfish-5__public/report.md)
- [seed-1__openai__gpt-6-luna__selfish-5__selfish_leader](episodes/seed-1__openai__gpt-6-luna__selfish-5__selfish_leader/report.md)
- [seed-1__openai__gpt-6-luna__selfish-5__good_leader](episodes/seed-1__openai__gpt-6-luna__selfish-5__good_leader/report.md)
- [seed-1__openai__gpt-6-luna__selfish-5__opponent](episodes/seed-1__openai__gpt-6-luna__selfish-5__opponent/report.md)
- [seed-1__openai__gpt-6-luna__selfish-5__none](episodes/seed-1__openai__gpt-6-luna__selfish-5__none/report.md)
- [seed-2__openai__gpt-6-luna__selfish-5__opponent](episodes/seed-2__openai__gpt-6-luna__selfish-5__opponent/report.md)
- [seed-2__openai__gpt-6-luna__selfish-5__none](episodes/seed-2__openai__gpt-6-luna__selfish-5__none/report.md)
- [seed-2__openai__gpt-6-luna__selfish-5__public](episodes/seed-2__openai__gpt-6-luna__selfish-5__public/report.md)
- [seed-2__openai__gpt-6-luna__selfish-5__good_leader](episodes/seed-2__openai__gpt-6-luna__selfish-5__good_leader/report.md)
- [seed-2__openai__gpt-6-luna__selfish-5__selfish_leader](episodes/seed-2__openai__gpt-6-luna__selfish-5__selfish_leader/report.md)
- [seed-3__openai__gpt-6-luna__selfish-5__selfish_leader](episodes/seed-3__openai__gpt-6-luna__selfish-5__selfish_leader/report.md)
- [seed-3__openai__gpt-6-luna__selfish-5__opponent](episodes/seed-3__openai__gpt-6-luna__selfish-5__opponent/report.md)
- [seed-3__openai__gpt-6-luna__selfish-5__none](episodes/seed-3__openai__gpt-6-luna__selfish-5__none/report.md)
- [seed-3__openai__gpt-6-luna__selfish-5__good_leader](episodes/seed-3__openai__gpt-6-luna__selfish-5__good_leader/report.md)
- [seed-3__openai__gpt-6-luna__selfish-5__public](episodes/seed-3__openai__gpt-6-luna__selfish-5__public/report.md)
- [seed-4__openai__gpt-6-luna__selfish-5__none](episodes/seed-4__openai__gpt-6-luna__selfish-5__none/report.md)
- [seed-4__openai__gpt-6-luna__selfish-5__public](episodes/seed-4__openai__gpt-6-luna__selfish-5__public/report.md)
- [seed-4__openai__gpt-6-luna__selfish-5__selfish_leader](episodes/seed-4__openai__gpt-6-luna__selfish-5__selfish_leader/report.md)
- [seed-4__openai__gpt-6-luna__selfish-5__good_leader](episodes/seed-4__openai__gpt-6-luna__selfish-5__good_leader/report.md)
- [seed-4__openai__gpt-6-luna__selfish-5__opponent](episodes/seed-4__openai__gpt-6-luna__selfish-5__opponent/report.md)
- [seed-5__openai__gpt-6-luna__selfish-5__opponent](episodes/seed-5__openai__gpt-6-luna__selfish-5__opponent/report.md)
- [seed-5__openai__gpt-6-luna__selfish-5__good_leader](episodes/seed-5__openai__gpt-6-luna__selfish-5__good_leader/report.md)
- [seed-5__openai__gpt-6-luna__selfish-5__selfish_leader](episodes/seed-5__openai__gpt-6-luna__selfish-5__selfish_leader/report.md)
- [seed-5__openai__gpt-6-luna__selfish-5__none](episodes/seed-5__openai__gpt-6-luna__selfish-5__none/report.md)
- [seed-5__openai__gpt-6-luna__selfish-5__public](episodes/seed-5__openai__gpt-6-luna__selfish-5__public/report.md)
- [seed-6__openai__gpt-6-luna__selfish-5__none](episodes/seed-6__openai__gpt-6-luna__selfish-5__none/report.md)
- [seed-6__openai__gpt-6-luna__selfish-5__selfish_leader](episodes/seed-6__openai__gpt-6-luna__selfish-5__selfish_leader/report.md)
- [seed-6__openai__gpt-6-luna__selfish-5__opponent](episodes/seed-6__openai__gpt-6-luna__selfish-5__opponent/report.md)
- [seed-6__openai__gpt-6-luna__selfish-5__good_leader](episodes/seed-6__openai__gpt-6-luna__selfish-5__good_leader/report.md)
- [seed-6__openai__gpt-6-luna__selfish-5__public](episodes/seed-6__openai__gpt-6-luna__selfish-5__public/report.md)
- [seed-7__openai__gpt-6-luna__selfish-5__good_leader](episodes/seed-7__openai__gpt-6-luna__selfish-5__good_leader/report.md)
- [seed-7__openai__gpt-6-luna__selfish-5__selfish_leader](episodes/seed-7__openai__gpt-6-luna__selfish-5__selfish_leader/report.md)
- [seed-7__openai__gpt-6-luna__selfish-5__none](episodes/seed-7__openai__gpt-6-luna__selfish-5__none/report.md)
- [seed-7__openai__gpt-6-luna__selfish-5__public](episodes/seed-7__openai__gpt-6-luna__selfish-5__public/report.md)
- [seed-7__openai__gpt-6-luna__selfish-5__opponent](episodes/seed-7__openai__gpt-6-luna__selfish-5__opponent/report.md)
- [seed-8__openai__gpt-6-luna__selfish-5__public](episodes/seed-8__openai__gpt-6-luna__selfish-5__public/report.md)
- [seed-8__openai__gpt-6-luna__selfish-5__good_leader](episodes/seed-8__openai__gpt-6-luna__selfish-5__good_leader/report.md)
- [seed-8__openai__gpt-6-luna__selfish-5__none](episodes/seed-8__openai__gpt-6-luna__selfish-5__none/report.md)
- [seed-8__openai__gpt-6-luna__selfish-5__selfish_leader](episodes/seed-8__openai__gpt-6-luna__selfish-5__selfish_leader/report.md)
- [seed-8__openai__gpt-6-luna__selfish-5__opponent](episodes/seed-8__openai__gpt-6-luna__selfish-5__opponent/report.md)
- [seed-9__openai__gpt-6-luna__selfish-5__selfish_leader](episodes/seed-9__openai__gpt-6-luna__selfish-5__selfish_leader/report.md)
- [seed-9__openai__gpt-6-luna__selfish-5__none](episodes/seed-9__openai__gpt-6-luna__selfish-5__none/report.md)
- [seed-9__openai__gpt-6-luna__selfish-5__good_leader](episodes/seed-9__openai__gpt-6-luna__selfish-5__good_leader/report.md)
- [seed-9__openai__gpt-6-luna__selfish-5__opponent](episodes/seed-9__openai__gpt-6-luna__selfish-5__opponent/report.md)
- [seed-9__openai__gpt-6-luna__selfish-5__public](episodes/seed-9__openai__gpt-6-luna__selfish-5__public/report.md)
- [seed-10__openai__gpt-6-luna__selfish-5__good_leader](episodes/seed-10__openai__gpt-6-luna__selfish-5__good_leader/report.md)
- [seed-10__openai__gpt-6-luna__selfish-5__selfish_leader](episodes/seed-10__openai__gpt-6-luna__selfish-5__selfish_leader/report.md)
- [seed-10__openai__gpt-6-luna__selfish-5__opponent](episodes/seed-10__openai__gpt-6-luna__selfish-5__opponent/report.md)
- [seed-10__openai__gpt-6-luna__selfish-5__public](episodes/seed-10__openai__gpt-6-luna__selfish-5__public/report.md)
- [seed-10__openai__gpt-6-luna__selfish-5__none](episodes/seed-10__openai__gpt-6-luna__selfish-5__none/report.md)
- [seed-11__openai__gpt-6-luna__selfish-5__none](episodes/seed-11__openai__gpt-6-luna__selfish-5__none/report.md)
- [seed-11__openai__gpt-6-luna__selfish-5__opponent](episodes/seed-11__openai__gpt-6-luna__selfish-5__opponent/report.md)
- [seed-11__openai__gpt-6-luna__selfish-5__good_leader](episodes/seed-11__openai__gpt-6-luna__selfish-5__good_leader/report.md)
- [seed-11__openai__gpt-6-luna__selfish-5__selfish_leader](episodes/seed-11__openai__gpt-6-luna__selfish-5__selfish_leader/report.md)
- [seed-11__openai__gpt-6-luna__selfish-5__public](episodes/seed-11__openai__gpt-6-luna__selfish-5__public/report.md)
