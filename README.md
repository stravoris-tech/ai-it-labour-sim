# ai-it-labour-sim

A System Dynamics model of AI's impact on IT employment, contract mix and vendor viability, for India and onshore
(North America and Europe), 2024-2040. It is a Python port of a prototype model, built as a tool for running many
simulations under chosen scenario levers and uncertainty.

## Status

Model ported (scalar engine) and batched engine in progress; experiment API, noise and charts not yet built. The
frozen Python prototype is in [`reference/`](reference/README.md).

## Licence

- Code is under the MIT licence ([`LICENSE`](LICENSE)): all code under `src/` except `src/aisim/data/`, `tests/`,
  `tools/`, `scripts/`, `.claude/` and `reference/prototype/code/`.
- Documentation and data are under CC BY 4.0 ([`LICENSE-DOCS`](LICENSE-DOCS)): `docs/`, `reference/prototype/spec/`,
  `reference/prototype/data/`, `reference/goldens/`, `src/aisim/data/` and the text of this README.

## How to cite

See [`CITATION.cff`](CITATION.cff).
