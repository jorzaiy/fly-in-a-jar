"""Fruit-fly brain: LIF simulation on the FlyWire v783 connectome (design §5).

Not implemented yet (tasks.md 4, 6, 7). The engine only depends on this shape:
a simulation takes a stimulus and returns spike counts per readout group,
e.g. {"GF": 3, "P9": 41, "MDN": 0, "MN9": 2, "LC": 18, "MBON": 7, "PAM": 9, "EPG": 22},
which the turn stores in GameState.last_spikes.
"""

from typing import Protocol

READOUT_GROUPS = ("GF", "P9", "MDN", "MN9", "LC", "MBON", "PAM", "EPG")


class Simulator(Protocol):
    def run(self, stimulus: dict, seed: int) -> dict[str, int]:
        """Return spike counts per readout group."""
        ...
