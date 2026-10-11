import json, math, phase2_sim as S

S.P["BaseEnrolment"] = 6100.0
# fixed point for NormalUnempRate at this enrolment, starting from the slack regime
S.P["NormalUnempRate"] = 0.0974
for _ in range(12):
    eq = S.equilibrium()
    r0 = S.run(eq, ai_on=False, stop=0.0, record_every=1.0)[0][0]
    S.P["NormalUnempRate"] = r0["UnempRate"]
    S.P["NormalTTF_M"] = r0["TTF_M"]; S.P["NormalTTF_S"] = r0["TTF_S"]
S.P["NormalTTF_M"] = round(S.P["NormalTTF_M"], 3); S.P["NormalTTF_S"] = round(S.P["NormalTTF_S"], 3)
eq = S.equilibrium()
NORMAL = round(S.P["NormalUnempRate"], 4)
S.P["NormalUnempRate"] = NORMAL
# rounded initial values as a builder would type them
init = {k: (round(v) if abs(v) >= 10 else round(v, 4)) for k, v in eq.items()}
init["PerceivedP"] = 1.0; init["A"] = S.P["A0"]
init["PercUnempShort"] = NORMAL; init["PercUnempLong"] = NORMAL

tests = {
    "T1_ai_off": dict(ai_on=False),
    "T2_step_ai_off": dict(ai_on=False, DemandStep=0.20),
    "T3_ai_base": dict(ai_on=True),
    "T4_rebound": dict(ai_on=True, DemandStep=0.35, StepYear=2034.0),
    "T5_dt32": dict(ai_on=True, dt=1/32),
    "T6_extreme": dict(ai_on=True, a_2024=0.5, a_max=0.95, g=0.5, s=50, v=0.0, p=0.5, q=1.0, JuniorCut=0.9),
}
out = {"normal": NORMAL, "normal_ttf_m": S.P["NormalTTF_M"], "normal_ttf_s": S.P["NormalTTF_S"], "init": init, "tests": {}}
for name, kw in tests.items():
    rows, st, mins = S.run(dict(init), **kw)
    out["tests"][name] = {"rows": rows, "mins": {k: v for k, v in mins.items()}}
    neg = {k: round(v, 2) for k, v in mins.items() if v < -1e-6}
    def at(y):
        return min(rows, key=lambda r: abs(r["year"] - y))
    print(f"\n{name}  negatives={neg}")
    for y in (2024, 2026, 2028, 2030, 2032, 2034, 2035, 2036, 2038, 2040):
        r = at(y)
        print(f" {y}: H J/M/S={r['H_J']:7,.0f}/{r['H_M']:7,.0f}/{r['H_S']:7,.0f} tot={r['HeadTotal']:8,.0f} "
              f"U%={r['UnempRate']*100:5.2f} enrol={r['Enrolment']:6,.0f} grad={r['Graduation']:6,.0f} "
              f"TTF J/M/S={r['TTF_J']:.2f}/{r['TTF_M']:.2f}/{r['TTF_S']:.2f} left={r['LeftField']:7,.0f} backlog={r['Backlog']:7,.0f}")
json.dump(out, open("phase2_results.json", "w"), default=lambda x: None)
print("\nNORMAL", NORMAL, "TTF_M", S.P["NormalTTF_M"], "TTF_S", S.P["NormalTTF_S"])
print("INIT", json.dumps(init, indent=0))
