"""Configuration loading and validation tests."""

import os
import tempfile
import unittest

from ipd.config import (
    ExperimentConfig,
    PopulationConfig,
    load_config,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestConfig(unittest.TestCase):
    def test_load_smoke_config(self):
        config = load_config(os.path.join(REPO_ROOT, "config", "smoke.yaml"))
        self.assertEqual(config.name, "smoke")
        self.assertEqual(config.population.n_agents(), 6)
        self.assertEqual(config.population.n_agents() % 2, 0)
        self.assertAlmostEqual(config.continue_prob, 0.95)

    def test_fingerprint_is_stable_and_seed_sensitive(self):
        c1 = load_config(os.path.join(REPO_ROOT, "config", "smoke.yaml"))
        c2 = load_config(os.path.join(REPO_ROOT, "config", "smoke.yaml"))
        self.assertEqual(c1.fingerprint(), c2.fingerprint())
        c3 = load_config(
            os.path.join(REPO_ROOT, "config", "smoke.yaml"), {"seed": 999}
        )
        self.assertNotEqual(c1.fingerprint(), c3.fingerprint())

    def test_odd_population_rejected(self):
        config = ExperimentConfig(
            population=PopulationConfig(priors=[0.1, 0.3, 0.5], agents_per_prior=1)
        )
        with self.assertRaises(ValueError):
            config.validate()

    def test_invalid_prior_rejected(self):
        config = ExperimentConfig(
            population=PopulationConfig(priors=[0.1, 1.5], agents_per_prior=1)
        )
        with self.assertRaises(ValueError):
            config.validate()

    def test_unknown_key_rejected(self):
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as fh:
            fh.write("name: x\nnot_a_key: 1\n")
            path = fh.name
        try:
            with self.assertRaises(ValueError):
                load_config(path)
        finally:
            os.remove(path)

    def test_overrides_applied(self):
        config = load_config(
            os.path.join(REPO_ROOT, "config", "smoke.yaml"), {"seed": 42}
        )
        self.assertEqual(config.seed, 42)


if __name__ == "__main__":
    unittest.main()
