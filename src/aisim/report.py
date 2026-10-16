"""One-page reports: a single self-contained HTML file (inline SVG charts, inline CSS), or markdown plus PNG files.

``Report(title)`` collects text, charts, tables and a settings block in order, then writes ``to_html(path)`` or
``to_markdown(dir)``. No templating library: string formatting, ``html.escape`` and ``DataFrame.to_html``.

- **Self-contained.** Charts are inline SVG with text kept as text (about 30 KB each); the page loads nothing from
  outside (no ``src`` or ``href`` but in-page ``#`` references) and prints cleanly.
- **Unique ids.** Each chart gets its own ``svg.hashsalt`` (``chart-<i>``), and every ``id`` in its SVG, with the
  references to it, is prefixed ``c<i>-``: matplotlib's counter ids (``figure_1``, ``axes_1``) and the chart gids
  repeat between charts, and duplicate ids are invalid in one HTML document. A gid repeated within one chart (one
  per panel) gets ``-2``, ``-3`` on its later copies.
- **Settings.** ``add_settings`` records the seed, runs, invalid runs, scenario(s), the model, package versions, git
  commit and dirty flag, platform and ``NPY_DISABLE_CPU_FEATURES`` from a result's meta.

``to_markdown_table(df)`` writes a markdown table (``DataFrame.to_markdown`` needs ``tabulate``, which is not a
dependency). Importing this module does not import matplotlib.
"""

from __future__ import annotations

import html
import math
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

import numpy as np
import pandas as pd

from aisim.charts.output import save, svg_text
from aisim.experiment.results import ExperimentResult
from aisim.experiment.scenarios import ScenarioResult, scenario_label

if TYPE_CHECKING:
    from matplotlib.figure import Figure

FloatFormat = str | Callable[[float], str]
"""A ``str.format`` pattern such as ``"{:.3f}"``, or a function of a float."""

CSS: Final = """
:root { color-scheme: light; }
body { margin: 0; background: #ffffff; color: #1f1f1c; }
body { font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif; }
main { max-width: 1000px; margin: 0 auto; padding: 24px 16px 48px; }
h1 { font-size: 1.6rem; margin: 0 0 16px; }
h2 { font-size: 1.15rem; margin: 32px 0 8px; }
p, ul { max-width: 72ch; }
figure { margin: 24px 0; break-inside: avoid; }
figure svg { display: block; max-width: 100%; height: auto; }
figcaption, caption { color: #55554f; font-size: 0.9rem; text-align: left; padding: 4px 0; }
.table { overflow-x: auto; margin: 16px 0 24px; break-inside: avoid; }
table { border-collapse: collapse; font-size: 0.85rem; font-variant-numeric: tabular-nums; }
th, td { padding: 4px 10px; border-bottom: 1px solid #dddcd6; text-align: right; vertical-align: top; }
th:first-child, td:first-child { text-align: left; }
thead th { border-bottom: 1.5px solid #8a8a85; }
table.settings td { text-align: left; font-family: ui-monospace, Consolas, monospace; word-break: break-all; }
footer { margin-top: 40px; color: #8a8a85; font-size: 0.8rem; }
@media print {
  body { font-size: 11pt; }
  main { max-width: none; padding: 0; }
  .table { overflow: visible; }
}
"""

_ID = re.compile(r'\bid="([^"]*)"')
_URL = re.compile(r"url\(#([^)]*)\)")
_HREF = re.compile(r'href="#([^"]*)"')
_BAD_ID_CHAR = re.compile(r"[^A-Za-z0-9_.:-]")


def _formatter(float_format: FloatFormat) -> Callable[[float], str]:
    return float_format.format if isinstance(float_format, str) else float_format


def _cell(v: Any, fmt: Callable[[float], str]) -> str:
    if v is None or v is pd.NA:
        return "n/a"
    if isinstance(v, float | np.floating):
        return fmt(float(v)) if math.isfinite(v) else "n/a"
    return str(v)


def to_markdown_table(df: pd.DataFrame, float_format: FloatFormat = "{:.3f}") -> str:
    """``df`` as a markdown table: one row per row (the index is not written), floats formatted with
    ``float_format``, NaN and None as ``n/a``, and ``|`` escaped."""
    fmt = _formatter(float_format)

    def esc(s: str) -> str:
        return s.replace("|", "\\|").replace("\n", " ")

    cols = [esc(str(c)) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for row in df.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(esc(_cell(v, fmt)) for v in row) + " |")
    return "\n".join(lines)


def inline_svg(svg: str, prefix: str) -> str:
    """matplotlib SVG text made fit to inline in HTML: no XML declaration, DOCTYPE or metadata, and every ``id`` (and
    reference to one) prefixed with ``prefix`` and restricted to ``[A-Za-z0-9_.:-]``."""
    svg = re.sub(r"<\?xml[^>]*\?>\s*", "", svg)
    svg = re.sub(r"<!DOCTYPE[^>]*>\s*", "", svg)
    svg = re.sub(r"\s*<metadata>.*?</metadata>", "", svg, flags=re.DOTALL)

    def name(raw: str) -> str:
        return prefix + _BAD_ID_CHAR.sub("_", html.unescape(raw))

    # A gid repeats within one chart when panels share it (``shade:calibration``, small multiples' ``median:<key>``):
    # the first keeps its name, so references still resolve, and later ones get "-2", "-3", ...
    seen: dict[str, int] = {}

    def unique(raw: str) -> str:
        base = name(raw)
        seen[base] = seen.get(base, 0) + 1
        return base if seen[base] == 1 else f"{base}-{seen[base]}"

    svg = _ID.sub(lambda m: f'id="{unique(m.group(1))}"', svg)
    svg = _URL.sub(lambda m: f"url(#{name(m.group(1))})", svg)
    svg = _HREF.sub(lambda m: f'href="#{name(m.group(1))}"', svg)
    return svg.strip()


def _paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]


def _text_html(text: str) -> str:
    out = []
    for para in _paragraphs(text):
        lines = para.splitlines()
        if all(line.lstrip().startswith("- ") for line in lines):
            items = "".join(f"<li>{html.escape(line.lstrip()[2:].strip())}</li>" for line in lines)
            out.append(f"<ul>{items}</ul>")
        else:
            out.append(f"<p>{html.escape(' '.join(line.strip() for line in lines))}</p>")
    return "\n".join(out)


def _versions(meta: Mapping[str, Any]) -> dict[str, str]:
    out = {str(k): str(v) for k, v in dict(meta.get("versions") or {}).items()}
    try:
        out["matplotlib"] = version("matplotlib")
    except PackageNotFoundError:
        out["matplotlib"] = "not installed"
    return out


def settings_rows(source: ExperimentResult | ScenarioResult | Mapping[str, Any]) -> list[tuple[str, str]]:
    """The settings block as ``(name, value)`` rows, from a result's meta (or a meta mapping)."""
    meta: Mapping[str, Any] = source if isinstance(source, Mapping) else source.meta
    exp: Mapping[str, Any] = meta.get("experiment") or {}

    def show(v: Any) -> str:
        return "n/a (unavailable)" if v is None else str(v)

    rows: list[tuple[str, str]] = [("seed", show(meta.get("seed")))]
    if "scenarios" in meta:
        names = [scenario_label(s) for s in meta["scenarios"]]
        rows.append(("runs", f"{meta.get('n_per_scenario')} per scenario x {len(names)} = {meta.get('n')}"))
        rows.append(("scenarios", ", ".join(names)))
        pinned = [f"{scenario_label(p['scenario'])}: {', '.join(p['levers'])}" for p in meta.get("pinned", [])]
        pinned = [p for p in pinned if not p.endswith(": ")]
        rows.append(("pinned levers", "; ".join(pinned) or "none"))
    else:
        rows.append(("runs", show(meta.get("n"))))
        rows.append(("scenario", scenario_label(exp.get("scenario"))))
        if meta.get("pinned"):
            rows.append(("pinned levers", ", ".join(meta["pinned"])))
    rows.append(("model", show(exp.get("model"))))
    rows.append(("invalid runs (n_invalid)", show(meta.get("n_invalid"))))
    sample = exp.get("sample") or {}
    if sample:
        rows.append(("sampled levers", f"{', '.join(sample)} ({exp.get('method')}, n = {exp.get('n')})"))
    elif exp.get("samples"):
        rows.append(("explicit samples", f"{exp['samples']['shape']} sha256 {exp['samples']['sha256']}"))
    if exp.get("overrides"):
        rows.append(("overrides", ", ".join(f"{k} = {v}" for k, v in exp["overrides"].items())))
    y0 = meta.get("perturb_from", exp.get("perturb_from"))
    rows.append(
        ("perturb_from", "none (levers act from 2024)" if y0 is None else f"{y0:g} (calibrated baseline until then)")
    )
    noise: Mapping[str, Any] = meta.get("noise", exp.get("noise")) or {}
    on = {name: spec for name, spec in noise.items() if spec["sigma"] > 0}
    if on:
        specs = "; ".join(f"{name}: sigma {spec['sigma']:g}, tau {spec['tau']:g}" for name, spec in on.items())
        rows.append(("noise", f"{specs} (noise_seed {show(meta.get('noise_seed', exp.get('noise_seed')))})"))
    else:
        rows.append(("noise", "off"))
    rows.append(("package versions", ", ".join(f"{k} {v}" for k, v in _versions(meta).items())))
    rows.append(("git_commit", show(meta.get("git_commit"))))
    rows.append(("git_dirty", show(meta.get("git_dirty"))))
    plat = meta.get("platform") or {}
    python = str(plat.get("python", "")).split()[0] if plat.get("python") else None
    rows.append(("platform", f"{plat.get('os')}; {plat.get('machine')}; Python {python}" if plat else show(None)))
    rows.append(("NPY_DISABLE_CPU_FEATURES", show(meta.get("NPY_DISABLE_CPU_FEATURES"))))
    return rows


@dataclass
class _Chart:
    fig: Figure
    caption: str


@dataclass
class _Table:
    df: pd.DataFrame
    caption: str
    float_format: FloatFormat


@dataclass
class _Text:
    text: str


@dataclass
class _Settings:
    rows: list[tuple[str, str]]


class Report:
    """A one-page report, built in order with ``add_*`` and written with ``to_html`` or ``to_markdown``."""

    def __init__(self, title: str) -> None:
        self.title = title
        self._items: list[_Chart | _Table | _Text | _Settings] = []

    def add_text(self, text: str) -> Report:
        """Paragraphs separated by blank lines (a paragraph of ``- `` lines becomes a list); HTML-escaped."""
        self._items.append(_Text(text))
        return self

    def add_chart(self, fig: Figure, caption: str = "") -> Report:
        """A chart, inlined as SVG in HTML (its own hash salt and id prefix) or saved as PNG for markdown."""
        self._items.append(_Chart(fig, caption))
        return self

    def add_table(self, df: pd.DataFrame, caption: str = "", float_format: FloatFormat = "{:.3f}") -> Report:
        """A table (the index is not written: reset it first to keep it), floats formatted with ``float_format``."""
        self._items.append(_Table(df.copy(), caption, float_format))
        return self

    def add_settings(self, source: ExperimentResult | ScenarioResult | Mapping[str, Any]) -> Report:
        """The run settings from a result or its meta: seed, runs, ``n_invalid``, scenario(s), the model,
        ``perturb_from``, the noise spec, package versions, git commit and dirty flag, platform and
        ``NPY_DISABLE_CPU_FEATURES``."""
        self._items.append(_Settings(settings_rows(source)))
        return self

    def to_html(self, path: str | Path) -> Path:
        """Write one self-contained HTML file; return its path."""
        path = Path(path)
        parts = [f"<h1>{html.escape(self.title)}</h1>"]
        n_chart = n_table = 0
        for item in self._items:
            if isinstance(item, _Text):
                parts.append(_text_html(item.text))
            elif isinstance(item, _Chart):
                n_chart += 1
                svg = inline_svg(svg_text(item.fig, f"chart-{n_chart}"), f"c{n_chart}-")
                cap = f"Figure {n_chart}." + (f" {html.escape(item.caption)}" if item.caption else "")
                parts.append(f'<figure id="chart-{n_chart}">\n{svg}\n<figcaption>{cap}</figcaption>\n</figure>')
            elif isinstance(item, _Table):
                n_table += 1
                body = item.df.to_html(
                    index=False, border=0, na_rep="n/a", float_format=_formatter(item.float_format), escape=True
                )
                cap = f"Table {n_table}." + (f" {html.escape(item.caption)}" if item.caption else "")
                body = body.replace(' class="dataframe"', "", 1)
                body = body.replace("<table>", f"<table>\n  <caption>{cap}</caption>", 1)
                parts.append(f'<div class="table" id="table-{n_table}">\n{body}\n</div>')
            else:
                rows = "".join(f"<tr><th>{html.escape(k)}</th><td>{html.escape(v)}</td></tr>" for k, v in item.rows)
                parts.append(f'<h2>Settings</h2>\n<div class="table"><table class="settings">{rows}</table></div>')
        footer = f"<footer>Made with aisim {html.escape(version('ai-it-labour-sim'))}.</footer>"
        page = (
            '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f"<title>{html.escape(self.title)}</title>\n<style>{CSS}</style>\n</head>\n<body>\n<main>\n"
            + "\n".join(parts)
            + f"\n{footer}\n</main>\n</body>\n</html>\n"
        )
        path.write_text(page, encoding="utf-8", newline="\n")
        return path

    def to_markdown(self, directory: str | Path) -> Path:
        """Write ``report.md`` and one PNG per chart (``chart-01.png``, ...) into ``directory``; return the
        markdown path."""
        out = Path(directory)
        out.mkdir(parents=True, exist_ok=True)
        md = [f"# {self.title}"]
        n_chart = n_table = 0
        for item in self._items:
            if isinstance(item, _Text):
                md.append(item.text.strip())
            elif isinstance(item, _Chart):
                n_chart += 1
                name = f"chart-{n_chart:02d}.png"
                save(item.fig, out / name)
                cap = f"Figure {n_chart}." + (f" {item.caption}" if item.caption else "")
                md.append(f"![{item.caption or name}]({name})\n\n*{cap}*")
            elif isinstance(item, _Table):
                n_table += 1
                cap = f"Table {n_table}." + (f" {item.caption}" if item.caption else "")
                md.append(f"*{cap}*\n\n{to_markdown_table(item.df, item.float_format)}")
            else:
                settings = pd.DataFrame(item.rows, columns=pd.Index(["setting", "value"]))
                md.append("## Settings\n\n" + to_markdown_table(settings))
        path = out / "report.md"
        path.write_text("\n\n".join(md) + "\n", encoding="utf-8", newline="\n")
        return path
