# Data License and Citations

The connectome data and cell type annotations used in **Fly in a Jar** are derived from FlyWire (FAFB v783) and associated whole-brain computational modeling resources.

## Licenses

- **FlyWire Connectome & Annotations**: Released under [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/).
- **Drosophila Computational Brain Model**: Released under the [MIT License](https://github.com/philshiu/Drosophila_brain_model/blob/main/LICENSE) (Copyright (c) 2023 Philip Shiu and Nico Spiller).

## Attribution & Citations

If you use or build upon this data, please cite the following original publications:

1. **Whole-Brain Connectome**:
   Dorkenwald, S., Matsliah, A., Sterling, A.R., et al. (2024).
   *Neuronal wiring diagram of an adult brain*.
   **Nature**, 634, 124–138.
   https://doi.org/10.1038/s41586-024-07558-y

2. **Whole-Brain Cell Typing & Annotation**:
   Schlegel, P., Yin, Y., Bates, A.S., et al. (2024).
   *Whole-brain annotation and multi-connectome cell typing of Drosophila*.
   **Nature**, 634, 139–152.
   https://doi.org/10.1038/s41586-024-07686-5

3. **Computational Brain Model (LIF Simulation)**:
   Shiu, P.K., Sterne, G.R., Spiller, N., et al. (2024).
   *A Drosophila computational brain model reveals sensorimotor processing*.
   **Nature**, 634, 210–219.
   https://doi.org/10.1038/s41586-024-07763-9

## Preprocessing Summary

- Raw dataset: FlyWire FAFB v783 (`Connectivity_783.parquet`, 15,091,983 connections across 138,639 neurons).
- Filter applied: Synaptic connection count threshold $\ge 5$ (default), resulting in 2,700,513 directed connections.
- Formats:
  - `data/connectome_v783_t5.npz`: Compressed Sparse Row (CSR) matrix partitioned by presynaptic neuron indices with signed weights ($+1$ for excitatory, $-1$ for inhibitory).
  - `data/neurons.parquet`: Indexed mapping of 138,639 neurons containing `index`, `root_id`, `cell_type`, `super_class`, and `side`.
