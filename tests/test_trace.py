"""The trace hook sees every section of every step, in order, and does not change the results."""

from __future__ import annotations

from aisim import run
from aisim.scalar.engine import SECTION_IDS
from tests.helpers import parity, port_dict


def test_trace_sees_every_section_in_order() -> None:
    calls: list[tuple[int, float, str, object]] = []
    stop, dt = 1.0, 1 / 16

    def trace(step: int, year: float, section_id: str, intermediates: object) -> None:
        calls.append((step, year, section_id, intermediates))

    run(stop=stop, dt=dt, trace=trace)
    n_steps = round(stop / dt) + 1
    assert len(calls) == n_steps * len(SECTION_IDS)
    for step in range(n_steps):
        block = calls[step * len(SECTION_IDS) : (step + 1) * len(SECTION_IDS)]
        assert [c[2] for c in block] == list(SECTION_IDS)
        assert {c[0] for c in block} == {step}
        assert len({c[1] for c in block}) == 1
    assert SECTION_IDS[0] == "S2"
    assert SECTION_IDS[-1].startswith("S13")
    assert len(set(SECTION_IDS)) == len(SECTION_IDS)


def test_noop_trace_is_bit_identical() -> None:
    def noop(step: int, year: float, section_id: str, intermediates: object) -> None:
        return None

    plain = run(record_every=1 / 16)
    traced = run(record_every=1 / 16, trace=noop)
    assert port_dict(traced) == port_dict(plain)
    diff, where = parity(traced, (plain.rows, dict(plain.final_state), plain.mins))
    assert diff == 0.0, where
