"""Phase 5 price-cut scan: does the Phase 4 tipping point move once contracts and sourcing are endogenous?"""
import json, phase5_sim as S
r = json.load(open("phase5_results.json"))
S.P.update(r["params"])
init = r["init"]
print("cut | vendor head 2027 -> 2040 | min viability | years viability<0 | vendor work share 2040")
for sh in (0.0, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50):
    rows, fin, mins = S.run(init, ai_on=False, PriceShock=sh, record_every=0.25)
    v27 = min(rows, key=lambda q: abs(q["year"] - 2027))["VendorHead"]
    last = rows[-1]
    print(f"{sh:4.2f} | {v27:7,.0f} -> {last['VendorHead']:7,.0f} ({last['VendorHead'] / v27 - 1:+.1%}) | "
          f"{min(q['Viability'] for q in rows) * 100:6.1f}% | {sum(0.25 for q in rows if q['Viability'] < 0):4.1f} | {last['VendorShare']:.3f}")
