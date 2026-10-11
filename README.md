# ai-it-labour-sim

A System Dynamics model of AI's impact on IT employment, contract mix and vendor viability, for India and onshore
(North America and Europe), 2024-2040. It is a Python port of a prototype model, built as a tool for running many
simulations under chosen scenario levers and uncertainty.

## Status

Model ported (scalar engine) and batched engine in progress; experiment API, noise and charts not yet built. The
frozen Python prototype is in [`reference/`](reference/README.md).

## Reproducibility

- Results are bit-for-bit reproducible on the same platform and numpy build.
- On x86-64 CPUs with AVX-512, numpy's faster maths kernels round `np.power` and `np.log` differently from the C
  library in about 5% and 0.03% of calls, by 1 ulp each. Over a run this changes the head counts and the Q1 lines at
  2040 by at most 7e-16 relative (about 3 ulp). Values that should be exactly 0, such as AI costs with AI off, can come
  out as roundoff of up to 2e-7.
- To reproduce the reference numbers exactly on such a CPU, set
  `NPY_DISABLE_CPU_FEATURES="X86_V4 AVX512_ICL AVX512_SPR"`. CI does. The list is for x86-64 builds of numpy only (it
  names numpy 2.5's x86 targets); do not set it on ARM64 or macOS. `uv run python tools/numerics_probe.py` reports
  whether this machine's kernels match.

## Licence

- Code is under the MIT licence ([`LICENSE`](LICENSE)): all code under `src/` except `src/aisim/data/`, `tests/`,
  `tools/`, `scripts/`, `.claude/` and `reference/prototype/code/`.
- Documentation and data are under CC BY 4.0 ([`LICENSE-DOCS`](LICENSE-DOCS)): `docs/`, `reference/prototype/spec/`,
  `reference/prototype/data/`, `reference/goldens/`, `src/aisim/data/` and the text of this README.

## How to cite

See [`CITATION.cff`](CITATION.cff).
