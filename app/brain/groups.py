"""Brain group resolver and stimulus builder (tasks.md 6 & design §5.3, §5.4).

Resolves cell_type names from `config/brain_map.yaml` to neuron indices in
`data/neurons.parquet`, verifies that all required neural pathways exist,
and builds per-turn Poisson stimulation maps.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
import yaml

log = logging.getLogger("fly.brain.groups")

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "brain_map.yaml"
DEFAULT_NEURONS_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "neurons.parquet"


class BrainGroups:
    """Manages FlyWire neuron groups for sensory input and readout output."""

    def __init__(
        self,
        config_path: Path = DEFAULT_CONFIG_PATH,
        neurons_path: Path = DEFAULT_NEURONS_PATH,
    ) -> None:
        if not config_path.exists():
            raise FileNotFoundError(f"Brain map config not found at {config_path}")
        if not neurons_path.exists():
            raise FileNotFoundError(f"Neurons parquet not found at {neurons_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            self.config: dict[str, Any] = yaml.safe_load(f)

        df = pd.read_parquet(neurons_path)

        # Build mapping: cell_type -> list of neuron indices
        type_to_indices: dict[str, list[int]] = {}
        for ctype, sub_df in df.groupby("cell_type", observed=True):
            type_to_indices[str(ctype)] = sub_df["index"].tolist()

        # 1. Resolve stimulus groups
        self.stimulus_groups: dict[str, list[int]] = {}
        raw_stim = self.config.get("stimulus_groups", {})
        for cat, ctypes in raw_stim.items():
            indices: list[int] = []
            if ctypes:
                per_type_cap = max(15, 150 // len(ctypes))
                for ct in ctypes:
                    type_idxs = type_to_indices.get(ct, [])
                    indices.extend(type_idxs[:per_type_cap])
            # Sort and deduplicate
            indices = sorted(set(indices))
            self.stimulus_groups[cat] = indices

            # Check required non-empty categories
            if cat in ("eat", "smell", "listen", "talk", "look", "light", "touch", "attack", "move"):
                if len(indices) == 0:
                    raise ValueError(f"Stimulus group '{cat}' resolved to 0 neurons! Refusing to start.")

        # 2. Resolve readout groups
        # readout_groups: {category: {option: list[int]}}
        self.readout_groups: dict[str, dict[str, list[int]]] = {}
        raw_readout = self.config.get("readout_groups", {})
        for cat, options in raw_readout.items():
            self.readout_groups[cat] = {}
            for opt, ctypes in options.items():
                indices = []
                for ct in ctypes:
                    indices.extend(type_to_indices.get(ct, []))
                indices = sorted(set(indices))
                if len(indices) == 0:
                    raise ValueError(f"Readout group '{cat}.{opt}' resolved to 0 neurons! Refusing to start.")
                self.readout_groups[cat][opt] = indices

        # 3. Cache feeding and scene ambience rules
        self.feeding_rules: dict[str, dict[str, Any]] = self.config.get("feeding", {})
        self.scene_ambience: dict[str, dict[str, Any]] = self.config.get("scene_ambience", {})
        self.model_cfg: dict[str, Any] = self.config.get("model", {})
        self.default_rate_hz: float = float(self.model_cfg.get("r_poi_hz", 150.0))

        # Log group stats
        log.info("BrainGroups initialized successfully:")
        for cat, idxs in self.stimulus_groups.items():
            if idxs:
                log.info("  Stimulus '%s': %d neurons", cat, len(idxs))
        for cat, opts in self.readout_groups.items():
            for opt, idxs in opts.items():
                log.info("  Readout '%s.%s': %d neurons", cat, opt, len(idxs))

    def get_stimulus_neurons(self, category: str, max_neurons: int = 150) -> list[int]:
        """Return neuron indices for an action category, capped at max_neurons."""
        neurons = self.stimulus_groups.get(category, [])
        if len(neurons) > max_neurons:
            # Deterministic spread sample across the population
            step = len(neurons) / max_neurons
            return [neurons[int(i * step)] for i in range(max_neurons)]
        return list(neurons)

    def get_readout_neurons(self, category: str, option: str) -> list[int]:
        """Return neuron indices for a readout category option."""
        return self.readout_groups.get(category, {}).get(option, [])

    def build_stimulus(
        self,
        category: str,
        action_text: str = "",
        scene: str = "",
        danger: int = 0,
        stim_fatigue: Mapping[str, int] | None = None,
        max_stim_neurons: int = 150,
    ) -> dict[int, float]:
        """Build Poisson stimulus mapping {neuron_index: rate_hz} (design §5.3).

        Args:
            category: Action category from judge (e.g. 'look', 'eat').
            action_text: Player raw input text (checked for feeding keywords).
            scene: Current player scene id.
            danger: Action danger score (0 safe, 1 risky, 2 dangerous, 3 suicidal).
            stim_fatigue: Dictionary of {pathway: consecutive_usage_count}.
            max_stim_neurons: Cap on stimulated neurons to ensure simulation speed.

        Returns:
            Dictionary mapping neuron index to Poisson stimulation rate in Hz.
        """
        stim_fatigue = stim_fatigue or {}
        stimulus: dict[int, float] = {}

        # 1. Base rate scaled by danger score: danger=0 -> 1.0x, danger=3 -> 1.9x
        danger_scale = 1.0 + (max(0, min(3, danger)) * 0.3)
        base_rate = self.default_rate_hz * danger_scale

        # Base category neurons
        neurons = self.get_stimulus_neurons(category, max_neurons=max_stim_neurons)
        for idx in neurons:
            stimulus[idx] = base_rate

        # 2. Sensory feeding keywords
        lower_text = action_text.lower()
        for kw, rule in self.feeding_rules.items():
            if kw in lower_text:
                pathway = rule["pathway"]
                mult = float(rule["multiplier"])
                fatigue_count = stim_fatigue.get(pathway, 0)
                # 0.6 decay per consecutive use
                decayed_mult = mult * (0.6 ** fatigue_count)
                feed_rate = self.default_rate_hz * decayed_mult
                feed_neurons = self.get_stimulus_neurons(pathway, max_neurons=50)
                for idx in feed_neurons:
                    stimulus[idx] = max(stimulus.get(idx, 0.0), feed_rate)

        # 3. Scene ambience additions
        if scene in self.scene_ambience:
            amb = self.scene_ambience[scene]
            pathway = amb["pathway"]
            boost = float(amb["rate_boost_hz"])
            amb_neurons = self.get_stimulus_neurons(pathway, max_neurons=30)
            for idx in amb_neurons:
                stimulus[idx] = stimulus.get(idx, 0.0) + boost

        return stimulus
