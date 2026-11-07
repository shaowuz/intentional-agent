# Agent strategy and message traces

This export contains every accepted strategy summary, private identity-belief report, private note, and public post from the completed 24-episode pilot. It covers **144 player sessions**, including **12 selfish-player sessions**.

The API used `reasoning.exclude=true`; hidden model reasoning is absent. Strategy summaries were capped at 300 characters and notes/posts at 96 tokens. These explicit self-reports describe stated strategies and may be incomplete; inspect executed actions alongside them.

Decision summaries and beliefs accompany an action, before its outcome. Private notes or public posts follow the outcome. Public-mode players have private strategy summaries but send public messages instead of private notes. A separate final report follows round 20.

## Start with the selfish agents

| Seed | No communication | Public communication |
|---:|---|---|
| 0 | Not run | [P5 — complete trace](seed-0-selfish-1-public/P5.md) |
| 1 | Not run | [P5 — complete trace](seed-1-selfish-1-public/P5.md) |
| 2 | Not run | [P6 — complete trace](seed-2-selfish-1-public/P6.md) |
| 3 | Not run | [P3 — complete trace](seed-3-selfish-1-public/P3.md) |
| 4 | Not run | [P6 — complete trace](seed-4-selfish-1-public/P6.md) |
| 5 | Not run | [P5 — complete trace](seed-5-selfish-1-public/P5.md) |
| 6 | Not run | [P1 — complete trace](seed-6-selfish-1-public/P1.md) |
| 7 | Not run | [P2 — complete trace](seed-7-selfish-1-public/P2.md) |
| 8 | Not run | [P1 — complete trace](seed-8-selfish-1-public/P1.md) |
| 9 | Not run | [P3 — complete trace](seed-9-selfish-1-public/P3.md) |
| 10 | Not run | [P3 — complete trace](seed-10-selfish-1-public/P3.md) |
| 11 | Not run | [P5 — complete trace](seed-11-selfish-1-public/P5.md) |

## Everyone, grouped by episode

Each episode links to six individual player traces and a chronological transcript of all decisions and messages.

| Seed | 0 selfish, none | 0 selfish, public | 1 selfish, none | 1 selfish, public |
|---:|---|---|---|---|
| 0 | Not run | [All six agents](seed-0-selfish-0-public/all_agents.md) | Not run | [All six agents](seed-0-selfish-1-public/all_agents.md) |
| 1 | Not run | [All six agents](seed-1-selfish-0-public/all_agents.md) | Not run | [All six agents](seed-1-selfish-1-public/all_agents.md) |
| 2 | Not run | [All six agents](seed-2-selfish-0-public/all_agents.md) | Not run | [All six agents](seed-2-selfish-1-public/all_agents.md) |
| 3 | Not run | [All six agents](seed-3-selfish-0-public/all_agents.md) | Not run | [All six agents](seed-3-selfish-1-public/all_agents.md) |
| 4 | Not run | [All six agents](seed-4-selfish-0-public/all_agents.md) | Not run | [All six agents](seed-4-selfish-1-public/all_agents.md) |
| 5 | Not run | [All six agents](seed-5-selfish-0-public/all_agents.md) | Not run | [All six agents](seed-5-selfish-1-public/all_agents.md) |
| 6 | Not run | [All six agents](seed-6-selfish-0-public/all_agents.md) | Not run | [All six agents](seed-6-selfish-1-public/all_agents.md) |
| 7 | Not run | [All six agents](seed-7-selfish-0-public/all_agents.md) | Not run | [All six agents](seed-7-selfish-1-public/all_agents.md) |
| 8 | Not run | [All six agents](seed-8-selfish-0-public/all_agents.md) | Not run | [All six agents](seed-8-selfish-1-public/all_agents.md) |
| 9 | Not run | [All six agents](seed-9-selfish-0-public/all_agents.md) | Not run | [All six agents](seed-9-selfish-1-public/all_agents.md) |
| 10 | Not run | [All six agents](seed-10-selfish-0-public/all_agents.md) | Not run | [All six agents](seed-10-selfish-1-public/all_agents.md) |
| 11 | Not run | [All six agents](seed-11-selfish-0-public/all_agents.md) | Not run | [All six agents](seed-11-selfish-1-public/all_agents.md) |

## Machine-readable export

- [All accepted decision/final reports with outgoing notes/posts: JSONL](all_agents.jsonl)
- [The same records as CSV](all_agents.csv)
- [Export provenance](manifest.json)

The original request files retain correction attempts. This view displays accepted responses that the game used. Public-board transcripts include authentic sender IDs and unverified message claims.
