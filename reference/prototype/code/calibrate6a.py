"""Phase 6a calibration: start from the Phase 5 calibrated model; size the sector arrays (LOB, apps, seats)
and solve CostPerBFY0, LabourCostPB0 and Budget0 so that AI-off 2024 is a steady state."""
import json, phase6a_sim as S

p5 = json.load(open("phase5_results.json"))
for k, v in p5["params"].items():
    if k in S.P:
        S.P[k] = v
init5 = p5["init"]


def calibrate():
    st = S.blank_state()
    for k, v in init5.items():
        if k in st:
            st[k] = json.loads(json.dumps(v))
    st["BL"] = {x: {w: init5["Backlog"] * S.SEC6["SectorShare"][x] * S.WT6["Mix"][w] for w in S.WTYPES} for x in S.SECTORS}
    it_total = sum(init5["H"][u][l] for u in S.UNITS for l in S.LEVELS)
    cons_it = sum(init5["H"][u][l] for u in ("IH", "GCC") for l in S.LEVELS)
    for x in S.SECTORS:
        itp = it_total * S.SEC6["SectorShare"][x]
        S.P["LOB0_" + x] = round(itp / S.SEC6["ITIntensity"][x] - itp, -2)
        S.P["Port0_" + x] = round(0.3 * itp)
        S.P["Seats0_" + x] = round(S.P["LOB0_" + x] + cons_it * S.SEC6["SectorShare"][x])
        S.P["Budget0_" + x] = 1.0
        st["LOB"][x] = S.P["LOB0_" + x]; st["Port"][x] = S.P["Port0_" + x]; st["SeatsB"][x] = S.P["Seats0_" + x]
        st["AC"][x] = S.P["AC0"]; st["SpendRatio"][x] = S.P["NormalUtil"]
    st["Att"] = S.P["Att0"]; st["CostPerc"] = 1.0
    r0 = S.run(st, ai_on=False, stop=0.0, record_every=1.0)[0][0]
    S.P["CostPerBFY0"] = round(r0["ServicesSpend"] / r0["Completion"], -1)
    S.P["LabourCostPB0"] = round(r0["LabourCostPB"], -1)
    for x in S.SECTORS:
        S.P["Budget0_" + x] = round(r0["Committed_" + x] / S.P["NormalUtil"], -5)
    return st, r0


if __name__ == "__main__":
    st, r0 = calibrate()
    print({k: S.P[k] for k in S.P if k.startswith(("LOB0", "Port0", "Seats0", "Budget0")) or k in ("CostPerBFY0", "LabourCostPB0")})
    rows, fin, mins = S.run(st, ai_on=False, stop=16.0, record_every=4.0)
    for x in rows:
        print(int(x["year"]), "head", round(x["HeadTotal"]), "dem", round(x["Demand"]), "comp", round(x["Completion"]), "margin", round(x["Margin"], 4),
              "seats", round(x["Seats"]), "lob", round(x["LOB"]), "port", round(x["Port"]), "util", round(x["Committed"] / x["Budget"], 4),
              "spend svc", round(x["ServicesSpend"] / 1e9, 3), "seat", round(x["SeatSpend"] / 1e9, 3), "cloud", round(x["CloudSpend"] / 1e9, 3), "costidx", round(x["CostIdx"], 4))
