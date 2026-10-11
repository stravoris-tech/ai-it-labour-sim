import json, phase2_sim as S

def steady(enrol, normal):
    S.P["BaseEnrolment"] = enrol; S.P["NormalUnempRate"] = normal
    eq = S.equilibrium()
    rows, _, _ = S.run(eq, ai_on=False, stop=1.0, record_every=1.0)
    return eq, rows[0]

normal = 0.05
for enrol in (6100, 6200, 6300, 6400, 6500):
    for _ in range(6):                      # fixed point: Normal = steady unemployment
        eq, r = steady(enrol, normal)
        normal = r["UnempRate"]
    print(f"enrol={enrol} unemp={normal:.4f} TTF J/M/S={r['TTF_J']:.2f}/{r['TTF_M']:.2f}/{r['TTF_S']:.2f} "
          f"H={r['H_J']:,.0f}/{r['H_M']:,.0f}/{r['H_S']:,.0f} U={r['U_J']:,.0f}/{r['U_M']:,.0f}/{r['U_S']:,.0f} "
          f"V={r['V_J']:,.0f}/{r['V_M']:,.0f}/{r['V_S']:,.0f} backlog={r['Backlog']:,.0f}")
