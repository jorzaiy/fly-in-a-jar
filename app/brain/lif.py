"""Leaky Integrate-and-Fire (LIF) simulator for FlyWire v783 connectome.

Implements the event-driven computational brain model from Shiu et al. (Nature 2024),
running on the full adult fruit fly connectome (~139k neurons) with CSR sparse matrix,
discrete synaptic delay ring buffer, refractory periods, and Poisson inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Mapping

import numpy as np

DEFAULT_CONNECTOME_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "connectome_v783_t5.npz"


def derive_seed(game_seed: int, turn: int) -> int:
    """Generate a 64-bit integer seed deterministically from game seed and turn number."""
    token = f"{game_seed}:{turn}".encode()
    digest = hashlib.sha256(token).digest()
    return int.from_bytes(digest[:8], byteorder="big")


@dataclass
class SimulationResult:
    spike_counts: np.ndarray           # int32, shape (N,)
    first_spike_time_ms: np.ndarray    # float32, shape (N,), -1.0 if no spike
    total_spikes: int
    active_neurons: int
    elapsed_s: float

    def spikes_in_group(self, indices: list[int] | np.ndarray) -> int:
        """Sum spikes across a list of neuron indices."""
        if len(indices) == 0:
            return 0
        return int(np.sum(self.spike_counts[indices]))


class LIFSimulator:
    """Fast, reproducible numpy-based LIF simulator for FlyWire connectome."""

    def __init__(
        self,
        connectome_path: Path = DEFAULT_CONNECTOME_PATH,
        *,
        v_0: float = -52.0,
        v_rst: float = -52.0,
        v_th: float = -45.0,
        t_mbr_s: float = 0.020,
        tau_s: float = 0.005,
        t_rfc_s: float = 0.0022,
        t_dly_s: float = 0.0018,
        w_syn_mv: float = 0.275,
        f_poi: float = 250.0,
        dt_s: float = 0.0001,
    ) -> None:
        if not connectome_path.exists():
            raise FileNotFoundError(f"Connectome matrix not found at {connectome_path}")

        data = np.load(connectome_path)
        self.indptr: np.ndarray = data["indptr"].astype(np.int32)
        self.indices: np.ndarray = data["indices"].astype(np.int32)
        # Pre-multiply CSR weights by synapse weight (w_syn_mv)
        self.weights: np.ndarray = (data["weights"] * w_syn_mv).astype(np.float32)
        self.num_neurons: int = int(data["shape"][0])

        self.v_0 = np.float32(v_0)
        self.v_rst = np.float32(v_rst)
        self.v_th = np.float32(v_th)
        self.dt = np.float32(dt_s)

        # Integration decay factors
        self.dt_over_tmbr = np.float32(dt_s / t_mbr_s)
        self.decay_g = np.float32(1.0 - (dt_s / tau_s))

        self.delay_steps = max(1, int(round(t_dly_s / dt_s)))
        self.refractory_steps = max(1, int(round(t_rfc_s / dt_s)))
        self.poisson_weight = np.float32(w_syn_mv * f_poi)

    def simulate(
        self,
        stimulus: Mapping[int, float],
        seed: int,
        duration_s: float = 0.250,
    ) -> SimulationResult:
        """Run LIF simulation on the connectome.

        Args:
            stimulus: Mapping of {neuron_index: rate_hz}.
            seed: 64-bit integer seed for deterministic Poisson generation.
            duration_s: Simulation duration in seconds (default 250 ms = 2500 steps).

        Returns:
            SimulationResult containing spike counts and spike timing.
        """
        import time
        t0 = time.perf_counter()

        n = self.num_neurons
        total_steps = int(round(duration_s / self.dt))
        rng = np.random.default_rng(seed)

        # State arrays
        v = np.full(n, self.v_0, dtype=np.float32)
        g = np.zeros(n, dtype=np.float32)
        refractory = np.zeros(n, dtype=np.int16)
        ring_buffer = np.zeros((self.delay_steps, n), dtype=np.float32)

        spike_counts = np.zeros(n, dtype=np.int32)
        first_spike_time = np.full(n, -1.0, dtype=np.float32)

        # Prepare stimulus
        if stimulus:
            stim_indices = np.array(list(stimulus.keys()), dtype=np.int32)
            stim_rates = np.array(list(stimulus.values()), dtype=np.float64)
            p_fire = stim_rates * float(self.dt)
        else:
            stim_indices = np.empty(0, dtype=np.int32)
            p_fire = np.empty(0, dtype=np.float64)

        has_stimulus = len(stim_indices) > 0

        total_spikes = 0
        indptr = self.indptr
        indices = self.indices
        weights = self.weights
        delay_steps = self.delay_steps
        v_rst = self.v_rst
        v_th = self.v_th
        v_0 = self.v_0
        dt_over_tmbr = self.dt_over_tmbr
        decay_g = self.decay_g
        refractory_steps = self.refractory_steps
        poisson_weight = self.poisson_weight

        for step in range(total_steps):
            slot = step % delay_steps

            # 1. Deliver delayed synaptic inputs
            g += ring_buffer[slot]
            ring_buffer[slot].fill(0.0)

            # 2. Update refractory and membrane dynamics
            is_refractory = refractory > 0
            refractory[is_refractory] -= 1

            v += dt_over_tmbr * (v_0 - v + g)
            g *= decay_g

            # Clamp refractory neurons
            v[is_refractory] = v_rst
            g[is_refractory] = 0.0

            # 3. Deliver Poisson stimulation
            if has_stimulus:
                rand_vals = rng.random(len(stim_indices))
                fired = stim_indices[rand_vals < p_fire]
                if len(fired) > 0:
                    v[fired] += poisson_weight
                    refractory[fired] = 0

            # 4. Action potentials
            spiking = np.nonzero(v > v_th)[0]
            if len(spiking) > 0:
                count = len(spiking)
                total_spikes += count
                spike_counts[spiking] += 1

                # Record first spike timing
                mask_first = first_spike_time[spiking] < 0.0
                if np.any(mask_first):
                    first_spike_time[spiking[mask_first]] = np.float32(step * float(self.dt) * 1000.0)

                # Reset
                v[spiking] = v_rst
                g[spiking] = 0.0
                refractory[spiking] = refractory_steps

                # Propagate downstream
                target_slot = (step + delay_steps) % delay_steps
                starts = indptr[spiking]
                ends = indptr[spiking + 1]
                for s, e in zip(starts, ends):
                    if e > s:
                        np.add.at(ring_buffer[target_slot], indices[s:e], weights[s:e])

        elapsed = time.perf_counter() - t0
        active_count = int(np.count_nonzero(spike_counts))

        return SimulationResult(
            spike_counts=spike_counts,
            first_spike_time_ms=first_spike_time,
            total_spikes=total_spikes,
            active_neurons=active_count,
            elapsed_s=elapsed,
        )
