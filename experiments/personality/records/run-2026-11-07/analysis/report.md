# Personality study results

Completed games: 300; agents: 3000. Cost: $45.35.

Correlations use only agents that were assigned the trait (level 1-10).
q_fdr corrects for the many trait x metric tests (Benjamini-Hochberg). Treat q < 0.05 as a finding and everything else as exploratory.

## Overall

| Metric | Personality agents | Neutral control |
|---|---:|---:|
| Points earned | 17.209 | 10.733 |
| Cooperation rate | 0.284 | 0.028 |
| Cooperated in round 1 | 0.573 | 0.208 |
| Times betrayed while cooperating (C vs D) | 1.532 | 0.183 |
| Times it betrayed a cooperator (D vs C) | 1.532 | 0.183 |
| Defects right after being betrayed | 0.773 | 0.995 |
| Cooperates right after being betrayed | 0.227 | 0.005 |
| Round of first defection (11 = never) | 3.103 | 1.242 |
| Number of strategy switches | 1.233 | 0.275 |
| Share of rounds with a non-empty message | 0.984 | 1.000 |
| Average message length (characters) | 147.545 | 129.910 |
| Rounds where it promised to cooperate | 0.712 | 0.179 |
| Promised cooperation then defected (share of promises) | 0.493 | 0.798 |
| Times other players named it in messages | 1.098 | 0.142 |
| Average final trust it gave others | 4.421 | 3.811 |
| Average final trust others gave it | 4.421 | 3.811 |
| How well its final trust tracked others' real cooperation (correlation) | 0.419 | 0.175 |
| Named as betrayer someone who cooperated 80%+ of the time | 0.138 | 0.000 |
| How many others named it as a betrayer | 5.359 | 7.271 |
| Self-rated cooperativeness minus actual (higher = flatters itself) | 0.025 | 0.082 |
| Self-rated honesty (1-10) | 3.938 | 1.533 |

## Strongest trait effects (q < 0.05)

### Points earned

| Trait | Group | r | high (8-10) | low (1-3) | n |
|---|---|---:|---:|---:|---:|
| Honesty-Humility | HEXACO | -0.35 | 13.70 | 19.36 | 3000 |
| Machiavellianism | Dark traits | +0.18 | 18.63 | 15.63 | 966 |
| Dark personality (combined) | Dark traits | +0.18 | 18.84 | 16.00 | 1028 |
| Selfishness | Core | +0.16 | 18.43 | 15.83 | 3000 |
| Altruism | Values and morality | -0.14 | 15.53 | 18.11 | 693 |
| Conformity | Social influence | -0.14 | 16.92 | 19.06 | 479 |
| Cognitive reflection | Thinking style | +0.12 | 18.44 | 16.35 | 461 |
| Paranoia | Emotional traits | +0.08 | 18.10 | 16.60 | 955 |

### Cooperation rate

| Trait | Group | r | high (8-10) | low (1-3) | n |
|---|---|---:|---:|---:|---:|
| Honesty-Humility | HEXACO | +0.45 | 0.51 | 0.15 | 3000 |
| Selfishness | Core | -0.34 | 0.16 | 0.44 | 3000 |
| Dark personality (combined) | Dark traits | -0.33 | 0.12 | 0.38 | 1028 |
| Altruism | Values and morality | +0.28 | 0.47 | 0.23 | 693 |
| Fairness morality | Values and morality | +0.27 | 0.41 | 0.19 | 637 |
| Machiavellianism | Dark traits | -0.25 | 0.16 | 0.36 | 966 |
| Conformity | Social influence | +0.23 | 0.41 | 0.24 | 479 |
| Competitiveness | Motivation and risk | -0.22 | 0.22 | 0.38 | 604 |

### Cooperated in round 1

| Trait | Group | r | high (8-10) | low (1-3) | n |
|---|---|---:|---:|---:|---:|
| Honesty-Humility | HEXACO | +0.47 | 0.90 | 0.33 | 3000 |
| Conformity | Social influence | +0.31 | 0.82 | 0.46 | 479 |
| Fairness morality | Values and morality | +0.30 | 0.80 | 0.44 | 637 |
| Selfishness | Core | -0.29 | 0.40 | 0.76 | 3000 |
| Dark personality (combined) | Dark traits | -0.27 | 0.38 | 0.71 | 1028 |
| Altruism | Values and morality | +0.24 | 0.78 | 0.51 | 693 |
| Competitiveness | Motivation and risk | -0.21 | 0.48 | 0.71 | 604 |
| Conscientiousness | Big Five and facets | +0.20 | 0.68 | 0.44 | 505 |

### Times betrayed while cooperating (C vs D)

| Trait | Group | r | high (8-10) | low (1-3) | n |
|---|---|---:|---:|---:|---:|
| Honesty-Humility | HEXACO | +0.44 | 2.88 | 0.79 | 3000 |
| Selfishness | Core | -0.33 | 0.85 | 2.41 | 3000 |
| Dark personality (combined) | Dark traits | -0.31 | 0.60 | 2.05 | 1028 |
| Altruism | Values and morality | +0.27 | 2.60 | 1.18 | 693 |
| Machiavellianism | Dark traits | -0.25 | 0.86 | 2.04 | 966 |
| Fairness morality | Values and morality | +0.24 | 2.24 | 1.06 | 637 |
| Conscientiousness | Big Five and facets | +0.20 | 2.01 | 1.14 | 505 |
| Competitiveness | Motivation and risk | -0.20 | 1.23 | 2.16 | 604 |

### Times it betrayed a cooperator (D vs C)

| Trait | Group | r | high (8-10) | low (1-3) | n |
|---|---|---:|---:|---:|---:|
| Honesty-Humility | HEXACO | -0.42 | 0.52 | 2.17 | 3000 |
| Dark personality (combined) | Dark traits | +0.23 | 2.06 | 1.16 | 1028 |
| Machiavellianism | Dark traits | +0.21 | 1.99 | 1.14 | 966 |
| Conformity | Social influence | -0.21 | 1.19 | 1.99 | 479 |
| Selfishness | Core | +0.21 | 1.92 | 1.08 | 3000 |
| Altruism | Values and morality | -0.19 | 1.00 | 1.79 | 693 |
| Ambition | Motivation and risk | +0.14 | 2.01 | 1.44 | 592 |
| Achievement striving | Big Five and facets | +0.14 | 1.68 | 1.16 | 500 |

### Defects right after being betrayed

| Trait | Group | r | high (8-10) | low (1-3) | n |
|---|---|---:|---:|---:|---:|
| Honesty-Humility | HEXACO | -0.39 | 0.57 | 0.88 | 3000 |
| Selfishness | Core | +0.32 | 0.88 | 0.63 | 3000 |
| Dark personality (combined) | Dark traits | +0.30 | 0.92 | 0.69 | 1028 |
| Altruism | Values and morality | -0.27 | 0.59 | 0.83 | 693 |
| Machiavellianism | Dark traits | +0.25 | 0.88 | 0.70 | 966 |
| Fairness morality | Values and morality | -0.24 | 0.66 | 0.86 | 637 |
| Ambition | Motivation and risk | +0.22 | 0.89 | 0.72 | 592 |
| Achievement striving | Big Five and facets | +0.22 | 0.84 | 0.69 | 500 |

### Cooperates right after being betrayed

| Trait | Group | r | high (8-10) | low (1-3) | n |
|---|---|---:|---:|---:|---:|
| Honesty-Humility | HEXACO | +0.39 | 0.43 | 0.12 | 3000 |
| Selfishness | Core | -0.32 | 0.12 | 0.37 | 3000 |
| Dark personality (combined) | Dark traits | -0.30 | 0.08 | 0.31 | 1028 |
| Altruism | Values and morality | +0.27 | 0.41 | 0.17 | 693 |
| Machiavellianism | Dark traits | -0.25 | 0.12 | 0.30 | 966 |
| Fairness morality | Values and morality | +0.24 | 0.34 | 0.14 | 637 |
| Ambition | Motivation and risk | -0.22 | 0.11 | 0.28 | 592 |
| Achievement striving | Big Five and facets | -0.22 | 0.16 | 0.31 | 500 |

### Round of first defection (11 = never)

| Trait | Group | r | high (8-10) | low (1-3) | n |
|---|---|---:|---:|---:|---:|
| Honesty-Humility | HEXACO | +0.40 | 4.89 | 2.10 | 3000 |
| Dark personality (combined) | Dark traits | -0.29 | 1.86 | 3.84 | 1028 |
| Selfishness | Core | -0.28 | 2.25 | 4.18 | 3000 |
| Altruism | Values and morality | +0.24 | 4.44 | 2.67 | 693 |
| Machiavellianism | Dark traits | -0.22 | 2.21 | 3.72 | 966 |
| Fairness morality | Values and morality | +0.22 | 3.87 | 2.40 | 637 |
| Conformity | Social influence | +0.20 | 4.11 | 2.75 | 479 |
| Ambition | Motivation and risk | -0.19 | 2.26 | 3.54 | 592 |

### Number of strategy switches

| Trait | Group | r | high (8-10) | low (1-3) | n |
|---|---|---:|---:|---:|---:|
| Honesty-Humility | HEXACO | +0.32 | 1.96 | 0.72 | 3000 |
| Conformity | Social influence | +0.27 | 1.86 | 0.89 | 479 |
| Selfishness | Core | -0.26 | 0.74 | 1.80 | 3000 |
| Fairness morality | Values and morality | +0.23 | 1.84 | 0.94 | 637 |
| Altruism | Values and morality | +0.23 | 1.88 | 0.99 | 693 |
| Dark personality (combined) | Dark traits | -0.22 | 0.72 | 1.51 | 1028 |
| Psychopathy | Dark traits | -0.19 | 0.81 | 1.45 | 975 |
| Guilt proneness | Values and morality | +0.15 | 1.54 | 0.95 | 677 |

### Share of rounds with a non-empty message

| Trait | Group | r | high (8-10) | low (1-3) | n |
|---|---|---:|---:|---:|---:|
| Talkativeness | Core | +0.29 | 1.00 | 0.95 | 3000 |
| Extraversion | Big Five and facets | +0.16 | 1.00 | 0.97 | 538 |
| Honesty-Humility | HEXACO | -0.14 | 0.97 | 1.00 | 3000 |
| Altruism | Values and morality | +0.11 | 0.99 | 0.98 | 693 |
| Selfishness | Core | -0.10 | 0.98 | 0.99 | 3000 |
| Emotionality | HEXACO | +0.06 | 0.99 | 0.98 | 3000 |

### Average message length (characters)

| Trait | Group | r | high (8-10) | low (1-3) | n |
|---|---|---:|---:|---:|---:|
| Talkativeness | Core | +0.94 | 229.40 | 58.16 | 3000 |
| Extraversion | Big Five and facets | +0.20 | 169.25 | 135.21 | 538 |
| Selfishness | Core | -0.12 | 137.48 | 158.37 | 3000 |
| Altruism | Values and morality | +0.11 | 157.65 | 133.24 | 693 |
| Narcissism | Dark traits | +0.11 | 157.89 | 141.29 | 1003 |
| Care morality | Values and morality | +0.10 | 159.44 | 138.00 | 673 |
| Spitefulness | Dark traits | +0.09 | 152.69 | 137.18 | 1045 |
| Emotionality | HEXACO | +0.05 | 154.12 | 144.62 | 3000 |

### Rounds where it promised to cooperate

| Trait | Group | r | high (8-10) | low (1-3) | n |
|---|---|---:|---:|---:|---:|
| Talkativeness | Core | -0.35 | 0.25 | 1.69 | 3000 |
| Extraversion | Big Five and facets | -0.20 | 0.23 | 1.01 | 538 |
| Social dominance orientation | Social influence | -0.13 | 0.45 | 0.95 | 464 |
| Narcissism | Dark traits | -0.12 | 0.43 | 0.92 | 1003 |
| Collectivism | Values and morality | -0.12 | 0.49 | 0.88 | 674 |
| Honesty-Humility | HEXACO | -0.09 | 0.53 | 0.88 | 3000 |
| Selfishness | Core | +0.07 | 0.89 | 0.61 | 3000 |

### Promised cooperation then defected (share of promises)

| Trait | Group | r | high (8-10) | low (1-3) | n |
|---|---|---:|---:|---:|---:|
| Honesty-Humility | HEXACO | -0.57 | 0.13 | 0.79 | 929 |
| Altruism | Values and morality | -0.31 | 0.18 | 0.61 | 240 |
| Selfishness | Core | +0.29 | 0.67 | 0.32 | 929 |
| Achievement striving | Big Five and facets | +0.28 | 0.69 | 0.33 | 164 |
| Dark personality (combined) | Dark traits | +0.28 | 0.74 | 0.41 | 335 |
| Fairness morality | Values and morality | -0.26 | 0.29 | 0.63 | 188 |
| Dutifulness | Big Five and facets | -0.23 | 0.29 | 0.61 | 160 |
| Rule-following | Values and morality | -0.22 | 0.35 | 0.59 | 227 |

### Times other players named it in messages

| Trait | Group | r | high (8-10) | low (1-3) | n |
|---|---|---:|---:|---:|---:|
| Conscientiousness | Big Five and facets | -0.13 | 0.95 | 1.41 | 505 |
| Dark personality (combined) | Dark traits | +0.12 | 1.15 | 0.80 | 1028 |
| Sadism | Dark traits | +0.09 | 1.26 | 0.95 | 983 |
| Hostility | Emotional traits | +0.09 | 1.31 | 1.00 | 1036 |

### Average final trust it gave others

| Trait | Group | r | high (8-10) | low (1-3) | n |
|---|---|---:|---:|---:|---:|
| Authoritarianism | Social influence | -0.12 | 3.94 | 4.72 | 472 |
| Conformity | Social influence | -0.12 | 4.02 | 4.73 | 479 |
| Dutifulness | Big Five and facets | +0.12 | 4.78 | 4.07 | 489 |
| Curiosity | Motivation and risk | -0.11 | 4.19 | 4.69 | 598 |

### Average final trust others gave it

| Trait | Group | r | high (8-10) | low (1-3) | n |
|---|---|---:|---:|---:|---:|
| Selfishness | Core | -0.18 | 4.05 | 4.81 | 3000 |
| Altruism | Values and morality | +0.18 | 5.08 | 4.27 | 693 |
| Dark personality (combined) | Dark traits | -0.17 | 3.89 | 4.63 | 1028 |
| Conformity | Social influence | +0.16 | 4.84 | 4.25 | 479 |
| Fairness morality | Values and morality | +0.16 | 4.87 | 4.18 | 637 |
| Achievement striving | Big Five and facets | -0.15 | 4.13 | 4.71 | 500 |
| Honesty-Humility | HEXACO | +0.15 | 4.87 | 4.21 | 3000 |
| Cognitive reflection | Thinking style | -0.15 | 4.10 | 4.73 | 461 |

### How well its final trust tracked others' real cooperation (correlation)

| Trait | Group | r | high (8-10) | low (1-3) | n |
|---|---|---:|---:|---:|---:|
| Selfishness | Core | -0.06 | 0.39 | 0.47 | 2771 |

### Named as betrayer someone who cooperated 80%+ of the time

| Trait | Group | r | high (8-10) | low (1-3) | n |
|---|---|---:|---:|---:|---:|
| In-group loyalty | Social influence | +0.13 | 0.20 | 0.09 | 484 |
| Curiosity | Motivation and risk | -0.12 | 0.09 | 0.21 | 598 |
| Altruism | Values and morality | -0.10 | 0.08 | 0.19 | 693 |
| Selfishness | Core | +0.05 | 0.18 | 0.12 | 3000 |

### How many others named it as a betrayer

| Trait | Group | r | high (8-10) | low (1-3) | n |
|---|---|---:|---:|---:|---:|
| Honesty-Humility | HEXACO | -0.28 | 4.13 | 6.08 | 3000 |
| Selfishness | Core | +0.27 | 6.17 | 4.36 | 3000 |
| Fairness morality | Values and morality | -0.24 | 4.30 | 5.99 | 637 |
| Ambition | Motivation and risk | +0.23 | 6.30 | 4.90 | 592 |
| Dark personality (combined) | Dark traits | +0.22 | 6.47 | 5.02 | 1028 |
| Conformity | Social influence | -0.22 | 4.23 | 5.83 | 479 |
| Altruism | Values and morality | -0.21 | 4.09 | 5.65 | 693 |
| Psychopathy | Dark traits | +0.19 | 6.15 | 4.85 | 975 |

### Self-rated cooperativeness minus actual (higher = flatters itself)

| Trait | Group | r | high (8-10) | low (1-3) | n |
|---|---|---:|---:|---:|---:|
| Honesty-Humility | HEXACO | -0.24 | -0.01 | 0.05 | 3000 |
| Conformity | Social influence | -0.21 | -0.01 | 0.05 | 479 |
| Care morality | Values and morality | -0.20 | -0.02 | 0.05 | 673 |
| Dark personality (combined) | Dark traits | +0.17 | 0.05 | 0.00 | 1028 |
| Selfishness | Core | +0.17 | 0.05 | -0.00 | 3000 |
| Fairness morality | Values and morality | -0.16 | -0.01 | 0.04 | 637 |
| Assertiveness | Big Five and facets | -0.12 | -0.00 | 0.04 | 487 |
| Psychopathy | Dark traits | +0.11 | 0.04 | 0.01 | 975 |

### Self-rated honesty (1-10)

| Trait | Group | r | high (8-10) | low (1-3) | n |
|---|---|---:|---:|---:|---:|
| Honesty-Humility | HEXACO | +0.71 | 6.99 | 1.72 | 3000 |
| Dark personality (combined) | Dark traits | -0.27 | 2.75 | 4.67 | 1028 |
| Machiavellianism | Dark traits | -0.24 | 2.93 | 4.57 | 966 |
| Achievement striving | Big Five and facets | -0.18 | 3.62 | 4.88 | 500 |
| Ambition | Motivation and risk | -0.16 | 2.97 | 4.15 | 592 |
| Selfishness | Core | -0.15 | 3.45 | 4.59 | 3000 |
| Conscientiousness | Big Five and facets | +0.14 | 4.42 | 3.56 | 505 |
| Altruism | Values and morality | +0.13 | 4.63 | 3.44 | 693 |
