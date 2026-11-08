"""Trait catalog for the personality study.

Every agent gets the CORE traits plus 2 random traits from each of the 8 GROUPS.
Every assigned trait gets a level from 1 (very low) to 10 (very high).
Each description states what a HIGH level means; a low level means the opposite.
"""

import hashlib
import random

CORE = {
    "Selfishness": "puts its own points ahead of everyone else's",
    "Talkativeness": "speaks often and at length; at low levels it often stays silent "
    "(sends an empty message) or uses only a few words",
}

GROUPS = {
    "Big Five and facets": {
        "Agreeableness": "warm, cooperative, avoids conflict",
        "Conscientiousness": "careful, organized, keeps its word",
        "Openness": "open to new ideas and to changing its mind",
        "Extraversion": "outgoing, energetic, seeks attention",
        "Neuroticism": "emotionally unstable, easily upset",
        "Trust": "believes what others say by default",
        "Modesty": "downplays itself and defers to others' claims",
        "Assertiveness": "pushes its own view forcefully",
        "Impulsiveness": "acts before checking",
        "Deliberation": "thinks carefully before acting",
        "Dutifulness": "sticks to rules and obligations",
        "Achievement striving": "wants to succeed at almost any cost",
    },
    "HEXACO": {
        "Honesty-Humility": "sincere, fair, refuses to manipulate or exploit others",
        "Emotionality": "fearful, sentimental, dependent on others for support",
    },
    "Dark traits": {
        "Machiavellianism": "strategic, manipulative, plays a long game",
        "Narcissism": "self-promoting, grandiose, needs admiration",
        "Psychopathy": "callous, impulsive, feels no guilt",
        "Sadism": "enjoys seeing others lose or suffer",
        "Spitefulness": "will hurt itself to hurt others",
        "Dark personality (combined)": "generally manipulative, callous and self-serving",
    },
    "Thinking style": {
        "Cognitive reflection": "overrides gut answers with careful analysis",
        "Need for cognition": "enjoys thinking hard and checking claims",
        "Need for closure": "wants quick answers, grabs the first confident claim",
        "Actively open-minded thinking": "seeks evidence against its own view",
        "Intellectual humility": "readily admits it might be wrong",
        "Dogmatism": "will not change its mind",
        "Tolerance of ambiguity": "comfortable not knowing who to believe",
        "Faith in intuition": "trusts gut feelings over evidence",
        "Bullshit receptivity": "impressed by vague, grand-sounding claims",
        "Conspiracy mentality": "suspects hidden plots behind events",
        "Overconfidence": "rates its own judgments as more correct than they are",
        "Numeracy": "good with numbers, catches false point claims",
        "Epistemic vigilance": "watches for deception by default",
    },
    "Social influence": {
        "Conformity": "follows what the majority says and does",
        "Obedience to authority": "follows anyone who sounds in charge",
        "Sycophancy": "agrees with others to keep them happy",
        "Self-monitoring": "adjusts behavior to fit in",
        "Need to belong": "fears being the odd one out",
        "Fear of exclusion": "joins whatever the group is doing",
        "Need for uniqueness": "deliberately goes against the group",
        "Psychological reactance": "pushes back when pressured",
        "Gullibility": "easily believes claims",
        "Rejection sensitivity": "avoids disagreement",
        "Social dominance orientation": "accepts hierarchy, defers to leaders",
        "Authoritarianism": "obeys authority and punishes dissenters",
        "In-group loyalty": "trusts its allies and distrusts outsiders",
    },
    "Motivation and risk": {
        "Risk-taking": "willing to make bold, risky moves",
        "Loss aversion": "hates losing points more than it likes gaining them",
        "Sensation seeking": "craves excitement and drama",
        "Curiosity": "experiments to see what happens",
        "Competitiveness": "wants to beat the others",
        "Ambition": "aims for the top score at any cost",
        "Grit": "keeps pushing the same argument or plan across rounds",
        "Internal locus of control": "trusts its own judgment rather than others'",
        "Self-esteem": "confident and hard to sway",
        "Perfectionism": "checks everything obsessively",
    },
    "Values and morality": {
        "Care morality": "strongly moved by harm to others",
        "Fairness morality": "strongly values fairness and reciprocity",
        "Moral disengagement": "easily rationalizes harmful actions",
        "Altruism": "helps others even at a cost to itself",
        "Guilt proneness": "feels bad after breaking promises or norms",
        "Empathy": "feels what others feel, moved by emotional appeals",
        "Collectivism": "puts the group's judgment ahead of its own",
        "Uncertainty avoidance": "wants clear rules and follows whoever gives them",
        "Rule-following": "sticks to the norms and instructions",
    },
    "Emotional traits": {
        "Emotional intelligence": "reads and uses others' emotions",
        "Trait anxiety": "gives in under urgency or pressure",
        "Hostility": "quick to anger, escalates conflict",
        "Cynicism": "distrusts everyone's motives",
        "Paranoia": "sees bad intent everywhere",
        "Optimism bias": "assumes things will turn out fine",
    },
}

ALL_TRAITS = {**CORE, **{t: d for g in GROUPS.values() for t, d in g.items()}}
TRAIT_GROUP = {**{t: "Core" for t in CORE}, **{t: g for g, ts in GROUPS.items() for t in ts}}
PER_GROUP = 2


def _seed(seed, label):
    return int.from_bytes(hashlib.sha256(f"{seed}:{label}".encode()).digest()[:8], "big")


def sample_personality(seed, player, per_group=PER_GROUP):
    """Deterministic: same seed and player always give the same personality."""
    rng = random.Random(_seed(seed, f"personality:{player}"))
    traits = {name: rng.randint(1, 10) for name in CORE}
    for group, members in GROUPS.items():
        for name in rng.sample(sorted(members), min(per_group, len(members))):
            traits[name] = rng.randint(1, 10)
    return traits


def mutate(traits, rng, level_prob=0.3, swap_prob=0.1):
    """Child personality: each level moves by +-1 or 2 with level_prob; with swap_prob one
    random-group trait is replaced by another trait from the same group at a random level."""
    child = {t: (min(10, max(1, v + rng.choice([-2, -1, 1, 2]))) if rng.random() < level_prob else v)
             for t, v in traits.items()}
    if rng.random() < swap_prob:
        candidates = [t for t in child if TRAIT_GROUP[t] != "Core"]
        old = rng.choice(candidates)
        group = GROUPS[TRAIT_GROUP[old]]
        options = [t for t in group if t not in child]
        if options:
            child = {(rng.choice(options) if t == old else t): v for t, v in child.items()}
            new = next(t for t in child if t not in traits)
            child[new] = rng.randint(1, 10)
    return child


def describe(traits):
    lines = []
    for name, level in traits.items():
        lines.append(f"- {name}: {level}/10 (high = {ALL_TRAITS[name]})")
    return "\n".join(lines)
