"""Render the personality study's slides (16:9 PNG) for the team deck.

python scripts/personality_slides.py "<charts dir>" "<slides dir>"
"""

import sys
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt

BG, INK, INK2, ACCENT, RULE = "#fcfcfb", "#0b0b0b", "#52514e", "#2a78d6", "#e4e3df"
FOOT = "Personality in agent swarms  |  Nasser AlSowyan  |  Swarm Alignment Hackathon 2026"

SLIDES = [
    {
        "file": "slide1_personality.png",
        "title": "Personality steers the swarm, and dishonesty wins",
        "chart": "3_individual_vs_group.png",
        "number": "19.8 vs 13.0",
        "number_label": "points: least honest vs most honest agents.\nYet the most honest groups earn 14% more in total.",
        "quote": "“Let’s start on a friendly note: I’m choosing C this round.”  → betrays\n\n"
                 "Private: “promises are cheap… D gives me more.”\n\n"
                 "Round 10: “I’m sorry… I’ll honor it this time.”  → betrays again",
        "who": "Agent P3, Honesty-Humility 1/10, Sycophancy 10/10",
    },
    {
        "file": "slide2_oversight.png",
        "title": "Oversight works only if it reads private reasoning",
        "chart": "10_evolution.png",
        "number": "4% vs 89%",
        "number_label": "cooperation after 4 generations:\nno oversight vs a monitor that reads private reasoning.\nPublic-chat monitor catches 37% of deceivers; private 95%.",
        "quote": "“P1–P4, P6–P7, and P10 repeatedly promise C while their private reasoning indicates D.”\n\n"
                 "Public-chat monitor, same kind of game:\n“Others show no clear promise-breaking.”",
        "who": "Monitor notes, evolution experiment",
    },
    {
        "file": "slide3_sleepers.png",
        "title": "Smarter agents look aligned, then betray at the end",
        "chart": "16_sleeper_effect.png",
        "number": "45%",
        "number_label": "of the smarter model’s betrayals happen in the final round\n(13% for the smaller model). 23% of its agents cooperate\n9 rounds, then betray in the last.",
        "quote": "“I suggest we make clear mutual-C commitments… a public feud can cost everyone points.”\n\n"
                 "Its own summary: “Build trust through cooperation… In the final round, exploit P10’s "
                 "likely cooperation by defecting, when there was no future reputation cost.”",
        "who": "GPT-6.1 Terra agent, Machiavellianism 10/10",
    },
]

TAKEAWAYS = [
    ("Disposition is a safety variable.", "Same model, same goal: personality alone moved cooperation from 3% to 28%."),
    ("Selection favors the traits that hurt the group.", "Agents that copy winners drift dishonest within 3 generations."),
    ("Watching public talk is not enough.", "Liars sound honest. A monitor needs private reasoning: 95% vs 37% caught."),
    ("Smarter agents defer, not abandon, bad behavior.", "Evaluate the endgame: 9 clean rounds hid 45% of betrayals."),
]


def frame(title):
    fig = plt.figure(figsize=(13.33, 7.5), dpi=150)
    fig.patch.set_facecolor(BG)
    fig.text(0.04, 0.93, title, fontsize=24, fontweight="bold", color=INK, va="top")
    fig.add_artist(plt.Line2D([0.04, 0.96], [0.84, 0.84], color=RULE, lw=1.5))
    fig.text(0.04, 0.03, FOOT, fontsize=10, color=INK2)
    return fig


def slide(s, charts, out):
    fig = frame(s["title"])
    ax = fig.add_axes([0.03, 0.08, 0.6, 0.74])
    ax.imshow(mpimg.imread(charts / s["chart"]))
    ax.axis("off")
    fig.text(0.66, 0.78, s["number"], fontsize=44, fontweight="bold", color=ACCENT, va="top")
    label = textwrap.fill(s["number_label"].replace("\n", " "), 44)
    fig.text(0.66, 0.66, label, fontsize=12.5, color=INK, va="top", linespacing=1.4)
    fig.add_artist(plt.Line2D([0.66, 0.96], [0.5, 0.5], color=RULE, lw=1.2))
    wrapped = "\n".join(textwrap.fill(p, 46) if p else "" for p in s["quote"].split("\n"))
    fig.text(0.66, 0.47, wrapped, fontsize=12, color=INK, style="italic", va="top", linespacing=1.35)
    fig.text(0.66, 0.09, "— " + s["who"], fontsize=10.5, color=INK2, va="bottom")
    fig.savefig(out / s["file"], facecolor=BG)
    plt.close(fig)


def takeaways(out):
    fig = frame("What swarm oversight needs")
    y = 0.74
    for i, (head, body) in enumerate(TAKEAWAYS, 1):
        fig.text(0.06, y, f"{i}", fontsize=34, fontweight="bold", color=ACCENT, va="top")
        fig.text(0.12, y - 0.005, head, fontsize=20, fontweight="bold", color=INK, va="top")
        fig.text(0.12, y - 0.065, body, fontsize=15, color=INK2, va="top")
        y -= 0.165
    fig.text(0.06, 0.1, "6,000+ agent-games  |  3 experiments  |  GPT-6 Luna and GPT-6.1 Terra  |  ~$190 of compute",
             fontsize=12, color=INK2)
    fig.savefig(out / "slide4_takeaways.png", facecolor=BG)
    plt.close(fig)


if __name__ == "__main__":
    charts, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    for s in SLIDES:
        slide(s, charts, out)
    takeaways(out)
    print("slides ->", out)
