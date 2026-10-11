import json, phase4_sim as S
r = json.load(open("phase4_results.json"))
S.P.update({k: v for k, v in r["params"].items() if k.startswith("Normal") or k.startswith("BaseEnrolment") or k == "Price_VI"})
init = r["init"]
print("shock | vendor head 2027 -> 2040 | min viability | 2040 margin | VSE 2040 | years viability<0")
for sh in (0.0, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50):
    rows, fin, mins = S.run(init, ai_on=False, PriceShock=sh, record_every=0.25)
    v27 = min(rows, key=lambda q: abs(q["year"] - 2027))["VendorHead"]
    last = rows[-1]
    neg_years = sum(0.25 for q in rows if q["Viability"] < 0)
    print(f"{sh:4.2f} | {v27:7,.0f} -> {last['VendorHead']:7,.0f} ({last['VendorHead']/v27-1:+.1%}) | {min(q['Viability'] for q in rows)*100:6.1f}% | {last['Margin']*100:6.1f}% | {last['VSE']:.3f} | {neg_years:.1f}")
rows, _, _ = S.run(init, ai_on=True, record_every=1.0)
print("\nAI base:", [(int(q['year']), round(q['Margin']*100,1), round(q['VendorHead']), round(q['WI_VI'],3), round(q['PriceIndex'],3)) for q in rows[::2]])
