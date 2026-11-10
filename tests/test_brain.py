"""Unit tests for Leaky Integrate-and-Fire connectome simulator (app/brain/lif.py)."""

from __future__ import annotations

import numpy as np
import pytest

from app.brain.groups import DEFAULT_NEURONS_PATH, BrainGroups
from app.brain.lif import DEFAULT_CONNECTOME_PATH, LIFSimulator, derive_seed


def test_derive_seed():
    s1 = derive_seed(42, 1)
    s2 = derive_seed(42, 1)
    s3 = derive_seed(42, 2)
    s4 = derive_seed(999, 1)

    assert s1 == s2
    assert s1 != s3
    assert s1 != s4
    assert isinstance(s1, int)
    assert s1 > 0


@pytest.fixture(scope="session")
def simulator():
    if not DEFAULT_CONNECTOME_PATH.exists():
        pytest.skip(f"Connectome matrix not found at {DEFAULT_CONNECTOME_PATH}")
    return LIFSimulator(DEFAULT_CONNECTOME_PATH)


def test_lif_determinism(simulator):
    stimulus = {100: 150.0, 101: 150.0, 102: 150.0}
    seed = derive_seed(12345, 5)

    res1 = simulator.simulate(stimulus, seed=seed, duration_s=0.1)
    res2 = simulator.simulate(stimulus, seed=seed, duration_s=0.1)

    assert np.array_equal(res1.spike_counts, res2.spike_counts)
    assert np.array_equal(res1.first_spike_time_ms, res2.first_spike_time_ms)
    assert res1.total_spikes == res2.total_spikes
    assert res1.active_neurons == res2.active_neurons


def test_lif_different_seeds_diverge(simulator):
    stimulus = {100: 150.0, 101: 150.0, 102: 150.0}
    seed1 = derive_seed(12345, 1)
    seed2 = derive_seed(12345, 2)

    res1 = simulator.simulate(stimulus, seed=seed1, duration_s=0.1)
    res2 = simulator.simulate(stimulus, seed=seed2, duration_s=0.1)

    # Different seeds should yield slightly different Poisson realizations
    assert not np.array_equal(res1.spike_counts, res2.spike_counts)


def test_lif_silence_produces_no_spikes(simulator):
    res = simulator.simulate({}, seed=1, duration_s=0.05)
    assert res.total_spikes == 0
    assert res.active_neurons == 0
    assert np.all(res.spike_counts == 0)
    assert np.all(res.first_spike_time_ms < 0)


def test_lif_spikes_in_group(simulator):
    stimulus = {500: 200.0, 501: 200.0}
    seed = derive_seed(777, 1)
    res = simulator.simulate(stimulus, seed=seed, duration_s=0.1)

    assert res.spikes_in_group([]) == 0
    assert res.spikes_in_group([500, 501]) == int(res.spike_counts[500] + res.spike_counts[501])
    assert res.spikes_in_group([500]) >= 1


@pytest.fixture(scope="session")
def brain_groups():
    if not DEFAULT_NEURONS_PATH.exists():
        pytest.skip(f"Neurons parquet not found at {DEFAULT_NEURONS_PATH}")
    return BrainGroups()


def test_brain_groups_resolution(brain_groups):
    # Check stimulus groups
    for cat in ("eat", "smell", "listen", "look", "light", "touch", "attack", "move"):
        neurons = brain_groups.get_stimulus_neurons(cat)
        assert len(neurons) > 0, f"Expected neurons for stimulus category {cat}"

    # Check readout groups
    assert len(brain_groups.get_readout_neurons("monster", "attack")) > 0
    assert len(brain_groups.get_readout_neurons("monster", "retreat")) > 0
    assert len(brain_groups.get_readout_neurons("monster", "approach")) > 0
    assert len(brain_groups.get_readout_neurons("monster", "feed")) > 0

    assert len(brain_groups.get_readout_neurons("anomaly", "visual")) > 0
    assert len(brain_groups.get_readout_neurons("anomaly", "sound")) > 0
    assert len(brain_groups.get_readout_neurons("anomaly", "smell")) > 0
    assert len(brain_groups.get_readout_neurons("anomaly", "memory")) > 0

    assert len(brain_groups.get_readout_neurons("clue", "clue")) > 0
    assert len(brain_groups.get_readout_neurons("drift", "drift")) > 0


def test_brain_groups_build_stimulus(brain_groups):
    # 1. Normal category stimulus
    stim_safe = brain_groups.build_stimulus("look", danger=0)
    stim_danger = brain_groups.build_stimulus("look", danger=3)

    assert len(stim_safe) > 0
    assert len(stim_danger) == len(stim_safe)
    # Danger increases stimulation rate
    k = next(iter(stim_safe))
    assert stim_danger[k] > stim_safe[k]

    # 2. Sensory feeding keyword
    stim_sugar = brain_groups.build_stimulus("touch", action_text="give some sugar")
    eat_neurons = brain_groups.get_stimulus_neurons("eat", max_neurons=50)
    assert any(idx in stim_sugar for idx in eat_neurons)

    # 3. Fatigue reduces feeding boost
    stim_sugar_fatigued = brain_groups.build_stimulus(
        "touch", action_text="give some sugar", stim_fatigue={"eat": 2}
    )
    for idx in eat_neurons:
        if idx in stim_sugar and idx in stim_sugar_fatigued:
            assert stim_sugar[idx] > stim_sugar_fatigued[idx]

    # 4. Scene ambience boost
    stim_cold = brain_groups.build_stimulus("look", scene="cold_storage")
    touch_neurons = brain_groups.get_stimulus_neurons("touch", max_neurons=30)
    assert any(idx in stim_cold for idx in touch_neurons)
