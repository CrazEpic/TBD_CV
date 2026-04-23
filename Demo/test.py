import pandas as pd
import numpy as np
from itertools import combinations

# ---------- Utilities ----------

def vec(df, name):
    return df[[f"{name}_X", f"{name}_Y", f"{name}_Z"]].values

def normalize(v):
    norm = np.linalg.norm(v, axis=1, keepdims=True)
    norm[norm < 1e-8] = 1.0
    return v / norm

def magnitude(v):
    return np.linalg.norm(v, axis=1)

def direction_variance(vectors):
    v_norm = normalize(vectors)
    mean_dir = normalize(np.mean(v_norm, axis=0, keepdims=True))[0]
    dots = np.clip(np.sum(v_norm * mean_dir, axis=1), -1.0, 1.0)
    angles = np.arccos(dots)
    return np.var(angles)

def magnitude_variance(vectors):
    return np.var(magnitude(vectors))

def total_variance(vectors, w_dir=1.0, w_mag=0.3):
    return w_dir * direction_variance(vectors) + w_mag * magnitude_variance(vectors)


# ---------- Load ----------

df = pd.read_csv("motion.csv")


# ---------- Marker Groups ----------

BODY_POINTS = [
    "C7", "CLAV", "STRN", "T10",
    "RSHO", "LSHO",
    "RELB", "LELB"
]

VIOLIN_POINTS = ["VTOP", "VBOM"]
BOW_POINTS = ["BTOP", "BBOM"]


# ---------- Build Data ----------

points = {}

# Raw points
for p in BODY_POINTS + VIOLIN_POINTS + BOW_POINTS:
    points[p] = vec(df, p)

# Midpoints
points["SHO_MID"] = 0.5 * (points["RSHO"] + points["LSHO"])
points["V_MID"]   = 0.5 * (points["VTOP"] + points["VBOM"])
points["B_MID"]   = 0.5 * (points["BTOP"] + points["BBOM"])

# Axes
axes = {}
axes["V_AXIS"] = points["VTOP"] - points["VBOM"]
axes["B_AXIS"] = points["BTOP"] - points["BBOM"]


# ---------- Helpers ----------

VIOLIN_RELATED = {"VTOP", "VBOM", "V_MID", "V_AXIS"}
BOW_RELATED    = {"BTOP", "BBOM", "B_MID", "B_AXIS"}

def is_violin_related(name):
    return any(k in name for k in VIOLIN_RELATED | BOW_RELATED)


# ---------- Candidate Testing ----------

results = []

def test(name, vecs):
    if not is_violin_related(name):
        return
    try:
        var = total_variance(vecs)
        if not np.isnan(var):
            results.append((name, var))
    except:
        pass


# ---------- 1. Point-to-Point (filtered) ----------

for a, b in combinations(points.keys(), 2):
    name = f"{a} - {b}"
    if is_violin_related(a) or is_violin_related(b):
        test(name, points[a] - points[b])


# ---------- 2. Point to Axis ----------

for p in points:
    for ax in axes:
        name = f"{p} vs {ax}"
        if is_violin_related(p) or is_violin_related(ax):
            test(name, points[p] - axes[ax])


# ---------- 3. Axis vs Axis ----------

for a, b in combinations(axes.keys(), 2):
    name = f"{a} vs {b} (dot)"
    if is_violin_related(a) or is_violin_related(b):
        a_n = normalize(axes[a])
        b_n = normalize(axes[b])
        dots = np.sum(a_n * b_n, axis=1)
        results.append((name, np.var(dots)))


# ---------- Sort & Display ----------

results.sort(key=lambda x: x[1])

print("\nTop 25 violin/bow-related stable relationships:\n")
for name, val in results[:25]:
    print(f"{name:35s} {val:.6f}")