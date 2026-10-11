import json, sys, phase3_sim as S

def steady(enIN, enON, iters=10, years=150.0):
    S.P["BaseEnrolment_IN"] = enIN; S.P["BaseEnrolment_ON"] = enON
    for r in S.REGIONS:
        S.P["NormalUnempRate_" + r] = 0.10
    st = None
    for _ in range(iters):
        st = S.equilibrium(years, None if st is None else st)
        r0 = S.run(st, ai_on=False, stop=0.0, record_every=1.0)[0][0]
        for r in S.REGIONS:
            S.P["NormalUnempRate_" + r] = r0["Unemp_" + r]
            for l in ("M", "S"):
                S.P[f"NormalTTF_{r}_{l}"] = max(r0[f"TTF_{r}_{l}"], 0.02)
    return st, r0

if __name__ == "__main__":
    for enIN, enON in [tuple(map(float, a.split(","))) for a in sys.argv[1:]]:
        st, r = steady(enIN, enON)
        print(f"IN={enIN:.0f} ON={enON:.0f} | unemp IN {r['Unemp_IN']*100:.2f}% ON {r['Unemp_ON']*100:.2f}% | "
              f"TTF IN J/M/S {r['TTF_IN_J']:.2f}/{r['TTF_IN_M']:.2f}/{r['TTF_IN_S']:.2f} "
              f"ON {r['TTF_ON_J']:.2f}/{r['TTF_ON_M']:.2f}/{r['TTF_ON_S']:.2f} | "
              f"H " + " ".join(f"{u}={r['H_'+u]:,.0f}" for u in S.UNITS) + f" | backlog {r['Backlog']:,.0f} visaHires {r['VisaHires']:,.0f} cap {r['VisaCap']:,.0f}")
