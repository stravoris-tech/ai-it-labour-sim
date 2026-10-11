"""All stock updates of one Euler step, in the prototype's order, and the tracking of stock minimums.

Prototype: ``phase7_sim.py`` INT, lines 548-634 (``t += dt`` stays in the engine). Spec: every module's stocks.

**The update order is deliberate and must not change.** Every update reads intermediates computed earlier in the step
(``Step``) or the stock it updates, except two read-after-update sites, which read a stock already updated in this
step, as the prototype does:

- ``ClientPRef`` reads the updated ``ClientP`` (prototype line 602).
- ``NewD`` reads the updated ``NewV`` (prototype line 614).

Recon E3 measured that switching both to start-of-step values moves the Q1 lines by up to 1e-2 by 2040 and other keys
by up to 4e-2: a different model. The other statements are also kept in prototype order, so that stocks updated by
several statements (``U``, ``R``, ``LeftField``, ``Retired``) accumulate their terms in the same order, bit for bit.
"""

from __future__ import annotations

from collections.abc import Mapping

from aisim.dims import EMPLOYERS, LEVELS, POOL, REGIONS, SECTORS, TYPES, UNITS, VENDORS, WTYPES
from aisim.scalar.step import Step
from aisim.state import State


def integrate(pr: Mapping[str, float], st: State, s: Step, d: float) -> None:
    """Advance every stock in ``st`` by one step of length ``d``, in place."""
    Demand, cons = s.consumer.Demand, s.consumer.cons
    Comp, Aband = s.work.Comp, s.work.Aband
    Src, SignS = s.flows.Src, s.flows.SignS
    SrcTarget = s.targets.SrcTarget
    for x in SECTORS:
        c = cons[x]
        for w in WTYPES:
            st["BL"][x][w] += d * (Demand[x][w] - Comp[x][w] - Aband[x][w])
        st["AC"][x] += d * c.AdoptC
        st["LOB"][x] += d * (c.LOBTarget - st["LOB"][x]) / pr["LOBAdjTime"]
        st["Port"][x] += d * (c.NewApps - c.Retire)
        st["SeatsB"][x] += d * (c.Seats - st["SeatsB"][x]) / pr["SeatAdjTime"]
        st["SpendRatio"][x] += d * (c.Committed / c.Budget - st["SpendRatio"][x]) / pr["BudgetCycle"]
        if pr["FreezeSourcing"] < 0.5:
            s_ = Src[x]
            st["IHW"][x] += d * (s_.Contested * st["SrcPerc"][x]["IH"] - pr["Contest"] * s_.IHTurn)
            st["GCCW"][x] += d * (s_.Contested * st["SrcPerc"][x]["GCC"] - pr["Contest"] * s_.GCCTurn)
            for v in VENDORS:
                st["VW"][x][v] += d * (SignS[x][v] - s_.VExp[v])
            for e in EMPLOYERS:
                st["SrcPerc"][x][e] += d * (SrcTarget[x][e] - st["SrcPerc"][x][e]) / pr["SrcPerceptionTime"]
    st["Att"] += d * s.drivers.AttAdopt
    st["CostPerc"] += d * (s.drivers.CostIdx6 - st["CostPerc"]) / pr["CostPerceptionTime"]

    fl, promo, cancel = s.exits.fl, s.vac.promo, s.vac.cancel
    sw, hires = s.switching.sw, s.hiring.hires
    expiry, conv = s.visa.expiry, s.visa.conv
    for u in UNITS:
        r = POOL[u]
        for l in LEVELS:
            x_ = fl[u][l]
            promo_in = promo[u][l]
            conv_in = conv[l] if u == "OL" else 0.0
            visa_out = (expiry[l] + conv[l]) if u == "OV" else 0.0
            st["V"][u][l] += d * (x_["openings"] - cancel[u][l] - promo_in - sw[u][l]["in"] - hires[u][l])
            st["O"][u][l] += d * (hires[u][l] - x_["onboard"])
            st["H"][u][l] += d * (
                x_["onboard"]
                + promo_in
                + sw[u][l]["in"]
                + conv_in
                - x_["promo_out"]
                - x_["quits"]
                - x_["leave"]
                - x_["retire"]
                - x_["layoffs"]
                - sw[u][l]["out"]
                - visa_out
            )
            st["R"][r][l] += d * x_["layoffs"]
            st["U"][r][l] += d * (x_["quits"] - hires[u][l])
            st["LeftField"][r] += d * x_["leave"]
            st["Retired"][r] += d * x_["retire"]
        if u == "OV":
            for l in LEVELS:
                st["U"]["IN"][l] += d * expiry[l]

    pool, Grad, Enrol, ext = s.pools.pool, s.pools.Grad, s.pools.Enrol, s.ttf.ext
    UnempRate = s.unemp.UnempRate
    for r in REGIONS:
        for l in LEVELS:
            pz = pool[r][l]
            grad_in = Grad[r] if l == "J" else 0.0
            st["R"][r][l] += d * (-pz["rec_to_seek"] - pz["rec_to_left"] - pz["rec_retire"])
            st["U"][r][l] += d * (grad_in + pz["rec_to_seek"] + ext[r][l] - pz["seek_exit"] - pz["seek_retire"])
            st["LeftField"][r] += d * (pz["rec_to_left"] + pz["seek_exit"])
            st["Retired"][r] += d * (pz["rec_retire"] + pz["seek_retire"])
        st["Pipeline"][r] += d * (Enrol[r] - Grad[r])
        st["PUS"][r] += d * (UnempRate[r] - st["PUS"][r]) / pr["UnempPerceptionTime"]
        st["PUL"][r] += d * (UnempRate[r] - st["PUL"][r]) / pr["StudentPerceptionTime"]

    Pe, AdoptE = s.work.Pe, s.adoption.AdoptE
    for e in EMPLOYERS:
        st["A"][e] += d * AdoptE[e]
        st["PerceivedP"][e] += d * (Pe[e] - st["PerceivedP"][e]) / pr["PerceptionTime"]
        st["ClientP"][e] += d * (Pe[e] - st["ClientP"][e]) / pr["ClientPerceptionTime"]
        # Read-after-update (prototype line 602): ClientP was updated on the line above.
        st["ClientPRef"][e] += d * (st["ClientP"][e] - st["ClientPRef"][e]) / pr["TrendTime"]
    st["TightPerc"] += d * (s.staffing.VisaTight - st["TightPerc"]) / pr["TightPerceptionTime"]

    VF, VB = s.contracts.VF, s.books.VB
    for v in VENDORS:
        f, b = VF[v], VB[v]
        st["Overhead"][v] += d * (pr["OverheadRate_" + v] * f.Revenue - st["Overhead"][v]) / pr["OverheadAdjTime"]
        st["Viab"][v] += d * (b.Margin - st["Viab"][v]) / pr["ViabilityTime"]
        st["CostProg"][v] += d * (b.CostProgTarget - st["CostProg"][v]) / pr["CostProgramTime"]
        st["Disc"][v] += d * (b.DiscTarget - st["Disc"][v]) / pr["DiscAdjTime"]
        st["ShareRef"][v] += d * (b.VShare - st["ShareRef"][v]) / pr["ShareRefTime"]
        for k in TYPES:
            st["Leg"][v][k] += d * (-f.ExpLeg[k])
            st["NewV"][v][k] += d * (b.Sign[k] - f.ExpNew[k])
            # Read-after-update (prototype line 614): NewV was updated on the line above.
            st["NewD"][v][k] += d * (b.Sign[k] * f.Dnew[k] - st["NewV"][v][k])
            st["NewP"][v][k] += d * (b.Sign[k] * f.PNew[k] - f.ExpNew[k] * f.AvgP[k] - st["NewP"][v][k] * f.Glide[k])
    WITarget = s.wages.WITarget
    for u in UNITS:
        st["WI"][u] += d * (WITarget[u] - st["WI"][u]) / pr["WageAdjTime"]


def track_mins(st: State, mins: dict[str, float]) -> None:
    """Lower each tracked stock's running minimum in ``mins`` to its current value (after the step's updates).

    Tracked: ``H``, ``O``, ``V`` by unit and level, ``R``, ``U`` by region and level, ``IHW``, ``GCCW``, ``VW`` by
    sector, and ``Leg``, ``NewV``, ``NewP``, ``NewD`` by vendor and type. As in the prototype, the initial state is not
    included.
    """
    for grp, by_unit in (("H", st["H"]), ("O", st["O"]), ("V", st["V"])):
        for u in UNITS:
            for l in LEVELS:
                key = f"{grp}_{u}_{l}"
                mins[key] = min(mins.get(key, 1e18), by_unit[u][l])
    for grp, by_region in (("R", st["R"]), ("U", st["U"])):
        for r in REGIONS:
            for l in LEVELS:
                key = f"{grp}_{r}_{l}"
                mins[key] = min(mins.get(key, 1e18), by_region[r][l])
    for x in SECTORS:
        for key, val in (("IHW", st["IHW"][x]), ("GCCW", st["GCCW"][x])):
            mins[f"{key}_{x}"] = min(mins.get(f"{key}_{x}", 1e18), val)
        for v in VENDORS:
            mins[f"VW_{x}_{v}"] = min(mins.get(f"VW_{x}_{v}", 1e18), st["VW"][x][v])
    for v in VENDORS:
        for k in TYPES:
            for g_, book in (("Leg", st["Leg"]), ("NewV", st["NewV"]), ("NewP", st["NewP"]), ("NewD", st["NewD"])):
                mins[f"{g_}_{v}_{k}"] = min(mins.get(f"{g_}_{v}_{k}", 1e18), book[v][k])
