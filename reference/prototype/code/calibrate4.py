import json, phase4_sim as S
CAL = dict(BaseEnrolment_IN=3900.0, BaseEnrolment_ON=2000.0, NormalUnempRate_IN=0.0589, NormalUnempRate_ON=0.0618,
           NormalTTF_IN_M=0.573, NormalTTF_IN_S=0.254, NormalTTF_ON_M=0.583, NormalTTF_ON_S=0.064)
S.P.update(CAL)

def base_state():
    p3 = json.load(open("phase3_results.json"))["init"]
    st = S.blank_state()
    for k in ("Backlog", "A", "PerceivedP", "TightPerc", "H", "O", "V", "R", "U", "Pipeline", "PUS", "PUL"):
        st[k] = p3[k]
    return st

def calibrate(target=0.18):
    st = base_state()
    r0 = S.run(st, ai_on=False, stop=0.0, record_every=1.0)[0][0]
    cost_wo_oh = r0["LabourRaw"] + r0["VisaCost"] + r0["AICost"]
    rev_needed = cost_wo_oh / (1 - S.P["OverheadRate"] - target)
    S.P["Price_VI"] = round((rev_needed - r0["RevOnsite"]) / r0["Del_VI"], -1)
    S.P["NormalMargin"] = target
    # settle finance stocks with feedback switched off, then compute the exact steady margin
    st["Overhead"] = S.P["OverheadRate"] * (r0["Del_VI"] * S.P["Price_VI"] + r0["RevOnsite"])
    r1 = S.run(st, ai_on=False, stop=0.0, record_every=1.0)[0][0]
    S.P["NormalMargin"] = round(r1["Margin"], 4)
    st["Viability"] = S.P["NormalMargin"]
    st["Overhead"] = round(st["Overhead"], -3)
    return st, r1

if __name__ == "__main__":
    st, r1 = calibrate()
    print("Price_VI", S.P["Price_VI"], "NormalMargin", S.P["NormalMargin"], "Revenue", round(r1["Revenue"]/1e9, 3), "bn",
          "labour", round(r1["VendorLabour"]/1e9, 3), "visa", round(r1["VisaCost"]/1e6, 1), "m AI", round(r1["AICost"]/1e6, 1), "m overhead", round(st["Overhead"]/1e6, 1))
    rows, fin, mins = S.run(st, ai_on=False, stop=16.0, record_every=4.0)
    for x in rows:
        print(x["year"], "head", round(x["HeadTotal"]), "vendor", round(x["VendorHead"]), "margin", round(x["Margin"], 4), "VSE", round(x["VSE"], 4), "rev", round(x["Revenue"]/1e9, 3))
