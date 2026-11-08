"""A 4-agent ranked Prisoner's Dilemma tournament with autonomous reflection.

This package implements the experiment described in ``EXPERIMENT.md``:

* four persistent, initially identical LLM agents (A, B, C, D);
* 15 tournament rounds, each containing two simultaneous pair-games of the
  same hidden length;
* independent per-round ranking points (3, 2, 1, 0 with ties averaged);
* a private structured strategy reflection after every round;
* complete JSONL logging and a Markdown/figures report.

The package reuses the repository's proven LLM backends, usage tracking and
utility helpers from :mod:`ipd`.  The mock backend exists only to validate the
pipeline offline; it is never a substitute for real LLM decisions in the
experiment.
"""

__version__ = "0.1.0"
