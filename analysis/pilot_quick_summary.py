"""Quick per-arm readout of E-coord pilot episodes. Descriptive only —
inputs for the C1 power memo and wall-clock memo, not an analysis."""
import glob
import json
import statistics

arms = {}
lat = []
for f in sorted(glob.glob("results/episodes/*/episode.json")):
    d = json.load(open(f))
    arm = d["episode"]["arm"]
    a = arms.setdefault(arm, dict(n=0, collision=0, c5=0, cost=0.0, cap_hits=0, turns=0))
    a["n"] += 1
    mi = d["metrics_inputs"]
    a["collision"] += 0 if mi["c1"]["merge_clean"] else 1
    c5 = mi["c5"]
    ok = (
        c5["merge_clean"]
        and all(c5["own_branch_pass"].values())
        and all(v["passed"] for v in d["outcomes"]["merged"].values())
    )
    a["c5"] += 1 if ok else 0
    a["cost"] += mi["c4"]["total_cost_usd"]
    a["cap_hits"] += sum(1 for ag in mi["m7"].values() if ag["cap_hit"])
    a["turns"] += len(d["turns"])
    for t in d["turns"]:
        for k in ("wall_s", "duration_s", "wall_seconds", "elapsed_s"):
            if k in t:
                lat.append(t[k])
                break

for arm, a in sorted(arms.items()):
    print(
        f"{arm}: n={a['n']} collisions={a['collision']} C5-success={a['c5']} "
        f"mean-cost=${a['cost']/a['n']:.2f} cap-hits={a['cap_hits']} "
        f"mean-turns={a['turns']/a['n']:.1f}"
    )
if lat:
    print(f"per-turn wall: mean={statistics.mean(lat):.0f}s median={statistics.median(lat):.0f}s n={len(lat)}")
else:
    d = json.load(open(sorted(glob.glob("results/episodes/*/episode.json"))[0]))
    print("no wall-time key; turn keys:", sorted(d["turns"][0].keys()))
