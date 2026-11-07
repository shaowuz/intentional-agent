"""Intentional-agent: a reproducible multi-agent Iterated Prisoner's Dilemma experiment.

The package is intentionally dependency-light.  It uses only the Python standard
library plus PyYAML for configuration.  Analysis scripts use numpy/pandas/
matplotlib which are imported lazily so that the simulation itself does not
require them.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
