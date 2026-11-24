"""Generate the README visuals in assets/ from the saved pipeline outputs.

Outputs: assets/permit_map.png, assets/pipeline_funnel.png,
assets/results_dashboard.png, assets/slides/slide_01-06.png and
assets/slides_preview.gif. No API requests are made. Run from anywhere:

    python -m pip install matplotlib pillow
    python assets/make_readme_figures.py

Uses the Inter font when installed and falls back to the default otherwise.
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch
import numpy as np
import pandas as pd
from PIL import Image

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"
SLIDES = OUT / "slides"
SLIDES.mkdir(parents=True, exist_ok=True)

for f in fm.findSystemFonts():
    if "Inter" in f:
        fm.fontManager.addfont(f)
plt.rcParams.update({
    "font.family": "Inter", "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": "#BBBBBB", "axes.labelcolor": "#444444",
    "xtick.color": "#555555", "ytick.color": "#555555",
})

NAVY = "#14395F"
DARK = "#1F2937"
MUTED = "#6B7280"
STATUS_COLORS = {"VERIFIED": "#0F7B6C", "PROVISIONAL": "#D97706", "UNRESOLVED": "#B91C1C"}
UTIL_COLORS = {"DC Water": "#1D70B8", "PEPCO": "#E3A008", "Washington Gas": "#0F7B6C"}
# FHWA functional class: 1 = highest hierarchy, 7 = local roads.
CLASS_NAMES = {3: "3 · Other Principal Arterial", 4: "4 · Minor Arterial",
               5: "5 · Major Collector", 6: "6 · Minor Collector", 7: "7 · Local"}
CLASS_COLORS = {3: "#B91C1C", 4: "#F97316", 5: "#FACC15", 6: "#22D3EE", 7: "#60A5FA"}

# ---------------------------------------------------------------- data
raw = json.loads((ROOT / "data/2_raw/permits_2026_applied_or_issued_staging_crane_all_companies.json")
                 .read_text(encoding="utf-8"))
N_RAW = len(raw["features"])
proc = json.loads((ROOT / "data/3_processed/permits_2026_applied_or_issued_staging_crane_three_utilities.json")
                  .read_text(encoding="utf-8"))
pts = pd.DataFrame([f["attributes"] for f in proc["features"]])[["LocationID", "Longitude", "Latitude"]]

res_dir = ROOT / "outputs/4_permit_highest_functional_class/01_primary_results/full"
loc = pd.read_csv(res_dir / "permit_locations_with_highest_fhwa_functional_class.csv")
app = pd.read_csv(res_dir / "permit_tracking_highest_fhwa_functional_class_summary.csv")
loc = loc.merge(pts, on="LocationID", how="left", validate="one_to_one")

N_LOC, N_APP = len(loc), len(app)
status = loc.LocationClassStatus.value_counts()
N_VER = int(status["VERIFIED"])
N_CONF = int(app.HighestClassDeterminationStatus.eq("CONFIRMED_ALL_LOCATIONS_VERIFIED").sum())
N_REVIEW_LOC = N_LOC - N_VER
N_REVIEW_APP = N_APP - N_CONF
verified = loc[loc.LocationClassStatus.eq("VERIFIED")]
ver_class = verified.LocationFHWAFunctionalClass.astype(int).value_counts().sort_index()
app_class = app.HighestFHWAFunctionalClassPerPermit.dropna().astype(int).value_counts().sort_index()
reasons = loc.loc[loc.LocationClassStatus.ne("VERIFIED"), "LocationMatchStatus"].value_counts()
assert N_LOC == 5048 and N_APP == 3171, "Unexpected saved output; check inputs."


# ---------------------------------------------------------------- helpers
def draw_map(ax, s=4, legend_fs=9, dark=True):
    bg = "#0B1220" if dark else "white"
    ax.set_facecolor(bg)
    lat0 = np.radians(38.9)
    x = loc.Longitude * np.cos(lat0)
    y = loc.Latitude
    unv = ~loc.LocationClassStatus.eq("VERIFIED")
    for c in sorted(CLASS_COLORS, reverse=True):  # local roads underneath, arterials on top
        m = loc.LocationClassStatus.eq("VERIFIED") & loc.LocationFHWAFunctionalClass.eq(c)
        ax.scatter(x[m], y[m], s=s, c=CLASS_COLORS[c], alpha=0.85, linewidths=0, label=CLASS_NAMES[c])
    ax.scatter(x[unv], y[unv], s=s * 5, facecolors="none", edgecolors="white", linewidths=0.7,
               label=f"Needs review ({unv.sum()})")
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)
    leg = ax.legend(loc="lower left", fontsize=legend_fs, frameon=True, markerscale=3.2,
                    title="Verified FHWA class", title_fontsize=legend_fs + 0.5,
                    facecolor="#111827", edgecolor="#374151", labelcolor="white")
    leg.get_title().set_color("white")


def save_slide(fig, n):
    fig.savefig(SLIDES / f"slide_{n:02d}.png", facecolor=fig.get_facecolor())
    plt.close(fig)


def slide_base(num, title, subtitle=None):
    fig = plt.figure(figsize=(13.333, 7.5), dpi=150, facecolor="white")
    fig.patches.append(plt.Rectangle((0, 0.93), 1, 0.07, transform=fig.transFigure, fc=NAVY))
    fig.patches.append(plt.Rectangle((0, 0.925), 1, 0.006, transform=fig.transFigure, fc="#0F7B6C"))
    fig.text(0.035, 0.957, "DDOT  |  Utility Permits × FHWA Roadway Functional Class", color="white",
             fontsize=12, va="center", fontweight="semibold")
    fig.text(0.965, 0.957, f"{num} / 6", color="#CBD5E1", fontsize=11, va="center", ha="right")
    fig.text(0.035, 0.85, title, fontsize=26, fontweight="bold", color=DARK)
    if subtitle:
        fig.text(0.035, 0.805, subtitle, fontsize=13, color=MUTED)
    fig.text(0.035, 0.025, "Source: DDOT TOPS (MapServer/24), DDOT LRS, DCGIS Roadway SubBlock (layer 162); "
             "saved October 2026 snapshot", fontsize=9, color="#9CA3AF")
    return fig


def card(fig, x0, y0, w, h, big, small, fc="#ECFDF5", ec="#6EE7B7", tc="#0F7B6C", big_fs=40, small_fs=13):
    fig.patches.append(FancyBboxPatch((x0, y0), w, h, boxstyle="round,pad=0,rounding_size=0.012",
                                      transform=fig.transFigure, fc=fc, ec=ec, lw=1.5))
    fig.text(x0 + w / 2, y0 + h * 0.56, big, ha="center", fontsize=big_fs, fontweight="bold", color=tc)
    fig.text(x0 + w / 2, y0 + h * 0.2, small, ha="center", fontsize=small_fs, color="#374151", linespacing=1.35)


def funnel(ax, fs=12):
    stages = [(N_RAW, "TOPS locations: staging-area or crane work,\napplied for or issued in 2026"),
              (N_LOC, "locations for DC Water, PEPCO\nand Washington Gas"),
              (N_VER, "locations with a VERIFIED\nFHWA class"),
              (N_APP, "applications\n(TrackingNumbers)"),
              (N_CONF, "applications with a confirmed\nhighest class")]
    colors = ["#94A3B8", "#1D70B8", "#0F7B6C", "#5B4B8A", "#14395F"]
    ymax = len(stages)
    for i, ((n, lbl), c) in enumerate(zip(stages, colors)):
        w = n / N_RAW
        y = ymax - i
        ax.barh(y, w, left=(1 - w) / 2, height=0.78, color=c)
        ax.text(0.5, y + 0.05, f"{n:,}", ha="center", va="center", fontsize=fs + 8, fontweight="bold", color="white")
        ax.text(1.04, y, lbl, va="center", fontsize=fs, color=DARK, linespacing=1.3)
    ax.set_xlim(-0.04, 1.75); ax.set_ylim(0.4, ymax + 0.6)
    ax.axis("off")


def status_by_company(ax, fs=10):
    ct = pd.crosstab(loc.UtilityCompany, loc.LocationClassStatus)[["VERIFIED", "PROVISIONAL", "UNRESOLVED"]]
    share = ct.div(ct.sum(axis=1), axis=0) * 100
    left = np.zeros(len(share))
    for col in share.columns:
        ax.barh(share.index, share[col], left=left, color=STATUS_COLORS[col], height=0.6, label=col.title())
        left += share[col].values
    for i, (u, row) in enumerate(ct.iterrows()):
        ax.text(101, i, f"n={row.sum():,} · {row.VERIFIED / row.sum():.1%}",
                va="center", fontsize=fs - 1, color=DARK)
    ax.set_xlim(0, 135); ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xlabel("% of locations", fontsize=fs - 1)
    ax.invert_yaxis()
    ax.tick_params(labelsize=fs, length=0)
    ax.legend(loc="lower left", bbox_to_anchor=(0.0, 0.99), fontsize=fs - 2, frameon=False, ncol=3,
              handlelength=1.0, columnspacing=0.8)
    ax.set_title("Location status by utility", loc="left", fontsize=fs + 3, fontweight="semibold", color=DARK, pad=24)


def class_bars(ax, series, title, color_fn, fs=10, ylabel="Count"):
    classes = list(range(1, 8))
    vals = [int(series.get(c, 0)) for c in classes]
    ax.bar(classes, vals, color=[color_fn(c) for c in classes], width=0.66)
    for c, v in zip(classes, vals):
        ax.text(c, v + max(vals) * 0.02, f"{v:,}", ha="center", fontsize=fs - 1, color=DARK)
    ax.set_xticks(classes)
    ax.set_xticklabels(["1\nInterstate", "2\nFreeway/\nExpwy", "3\nPrincipal\nArterial", "4\nMinor\nArterial",
                        "5\nMajor\nCollector", "6\nMinor\nCollector", "7\nLocal"], fontsize=fs - 2.5)
    ax.set_ylim(0, max(vals) * 1.15)
    ax.set_ylabel(ylabel, fontsize=fs - 1)
    ax.tick_params(labelsize=fs - 1, length=0)
    ax.grid(axis="y", color="#EEEEEE"); ax.set_axisbelow(True)
    ax.set_title(title, loc="left", fontsize=fs + 3, fontweight="semibold", color=DARK)


def highest_by_company(ax, fs=10):
    ct = pd.crosstab(app.UtilityCompany, app.HighestFHWAFunctionalClassPerPermit.astype("Int64"))
    share = ct.div(ct.sum(axis=1), axis=0) * 100
    left = np.zeros(len(share))
    for c in share.columns:
        ax.barh(share.index, share[c], left=left, color=CLASS_COLORS[int(c)], height=0.6, label=f"Class {int(c)}")
        for i, v in enumerate(share[c].values):
            if v >= 6:
                ax.text(left[i] + v / 2, i, f"{v:.0f}%", ha="center", va="center", fontsize=fs - 2,
                        color="white" if int(c) in (3, 4) else DARK)
        left += share[c].values
    ax.set_xlim(0, 100); ax.invert_yaxis()
    ax.set_xlabel("% of applications with a confirmed highest class", fontsize=fs - 1)
    ax.tick_params(labelsize=fs, length=0)
    ax.legend(loc="upper center", bbox_to_anchor=(0.4, -0.28), ncol=5, fontsize=fs - 3, frameon=False,
              handlelength=1.2, columnspacing=1.0)
    ax.set_title("Highest class per application, by utility", loc="left", fontsize=fs + 3,
                 fontweight="semibold", color=DARK)


def reasons_bar(ax, fs=10):
    r = reasons.sort_values()
    labels = [s.replace("_", " ").title().replace("Lrs", "LRS").replace("Api", "API") for s in r.index]
    ax.barh(labels, r.values, color="#D97706", height=0.65)
    for i, v in enumerate(r.values):
        ax.text(v + 1.5, i, str(v), va="center", fontsize=fs - 1, color=DARK)
    ax.set_xlim(0, r.max() * 1.18)
    ax.tick_params(labelsize=fs - 1.5, length=0)
    ax.set_xlabel("Locations", fontsize=fs - 1)
    ax.set_title(f"Why {N_REVIEW_LOC} locations still need review", loc="left", fontsize=fs + 3,
                 fontweight="semibold", color=DARK)


# ---------------------------------------------------------------- standalone figures
def fig_map():
    fig = plt.figure(figsize=(10, 10.6), dpi=200, facecolor="#0B1220")
    ax = fig.add_axes([0.02, 0.02, 0.96, 0.88])
    draw_map(ax, s=5, legend_fs=10)
    fig.text(0.5, 0.955, "2026 utility work locations in Washington, DC", ha="center", fontsize=20,
             fontweight="bold", color="white")
    fig.text(0.5, 0.922, f"{N_LOC:,} TOPS construction-staging locations (DC Water, PEPCO, Washington Gas), "
             "colored by the verified FHWA class of the matched roadway", ha="center", fontsize=10.5, color="#CBD5E1")
    fig.savefig(OUT / "permit_map.png", facecolor=fig.get_facecolor())
    plt.close(fig)


def fig_funnel():
    fig = plt.figure(figsize=(12, 5.2), dpi=200, facecolor="white")
    fig.text(0.03, 0.92, "From the raw TOPS extract to a confirmed highest class per application",
             fontsize=16, fontweight="bold", color=DARK)
    ax = fig.add_axes([0.0, 0.02, 1.0, 0.84])
    funnel(ax)
    fig.savefig(OUT / "pipeline_funnel.png", facecolor="white")
    plt.close(fig)


def fig_dashboard():
    fig = plt.figure(figsize=(13, 9.2), dpi=200, facecolor="white")
    fig.text(0.5, 0.965, "Roadway Functional Class Enrichment: Results", ha="center",
             fontsize=20, fontweight="bold", color=DARK)
    kpis = [(f"{N_LOC:,}", "permit locations"), (f"{N_APP:,}", "applications"),
            (f"{N_VER / N_LOC:.1%}", "locations verified"), (f"{N_CONF:,}", "applications confirmed"),
            (f"{N_REVIEW_LOC}", "locations kept for review")]
    for i, (big, small) in enumerate(kpis):
        x0 = 0.03 + i * 0.19
        card(fig, x0, 0.83, 0.175, 0.105, big, small, big_fs=22, small_fs=10.5)
    gs = fig.add_gridspec(2, 2, left=0.13, right=0.97, top=0.76, bottom=0.08, hspace=0.62, wspace=0.62)
    class_bars(fig.add_subplot(gs[0, 0]), ver_class, "Verified class of each location",
               lambda c: CLASS_COLORS.get(c, "#CBD5E1"), ylabel="Locations")
    class_bars(fig.add_subplot(gs[0, 1]), app_class, "Highest class of each confirmed application",
               lambda c: CLASS_COLORS.get(c, "#CBD5E1"), ylabel="Applications")
    status_by_company(fig.add_subplot(gs[1, 0]))
    reasons_bar(fig.add_subplot(gs[1, 1]))
    fig.text(0.03, 0.015, "FHWA class 1 = highest roadway hierarchy (Interstate), 7 = local road. "
             "No location matched Class 1 or 2. 'Verified' means every automated rule passed; "
             "it is not a measured spatial accuracy.", fontsize=9, color=MUTED)
    fig.savefig(OUT / "results_dashboard.png", facecolor="white")
    plt.close(fig)


# ---------------------------------------------------------------- slides
def slides():
    # 1 - title with map
    fig = plt.figure(figsize=(13.333, 7.5), dpi=150, facecolor="#0B1220")
    ax = fig.add_axes([0.53, 0.04, 0.45, 0.92])
    draw_map(ax, s=2.2, legend_fs=7.5)
    fig.patches.append(plt.Rectangle((0.05, 0.585), 0.1, 0.008, transform=fig.transFigure, fc="#10B981"))
    fig.text(0.05, 0.73, "Roadway Functional Class", fontsize=34, fontweight="bold", color="white")
    fig.text(0.05, 0.63, "for Utility Permit Locations", fontsize=34, fontweight="bold", color="#34D399")
    fig.text(0.05, 0.54, "Which FHWA roadway class does each 2026\nDC Water, PEPCO and Washington Gas work\n"
             "location sit on, and what is the highest\nclass per application?", fontsize=16,
             color="#E5E7EB", linespacing=1.5, va="top")
    fig.text(0.05, 0.2, "Python  •  ArcGIS REST  •  DDOT LRS  •  pandas  •  pyproj", fontsize=13, color="#9CA3AF")
    fig.text(0.05, 0.1, "Amir Moayyedi", fontsize=15, color="white", fontweight="semibold")
    fig.text(0.05, 0.05, "1 / 6", fontsize=11, color="#6B7280")
    save_slide(fig, 1)

    # 2 - headline numbers
    fig = slide_base(2, "Headline results", "Saved October 2026 snapshot (year to date, not a full-year census)")
    cards = [(f"{N_LOC:,}", "utility work locations\nin 3 companies"),
             (f"{N_APP:,}", "permit applications\n(TrackingNumbers)"),
             (f"{N_VER / N_LOC:.1%}", f"{N_VER:,} locations with a\nVERIFIED FHWA class"),
             (f"{N_CONF:,}", "applications with a\nconfirmed highest class")]
    for i, (big, small) in enumerate(cards):
        card(fig, 0.035 + i * 0.237, 0.36, 0.215, 0.36, big, small, big_fs=40, small_fs=14)
    fig.text(0.035, 0.18, f"Nothing is dropped or guessed: {N_REVIEW_LOC} uncertain locations "
             f"({120} provisional, {54} unresolved) stay in the\nfinal CSV with a reason and a suggested next "
             f"check, and {N_REVIEW_APP} applications keep a blank highest class until reviewed.",
             fontsize=13.5, color="#374151", linespacing=1.6)
    save_slide(fig, 2)

    # 3 - pipeline funnel
    fig = slide_base(3, "Seven scripts, one auditable pipeline", "Explore → download → filter → spatial QA → "
                     "match roadways → aggregate per application")
    ax = fig.add_axes([0.03, 0.08, 0.94, 0.68])
    funnel(ax, fs=12.5)
    save_slide(fig, 3)

    # 4 - matching logic
    fig = slide_base(4, "How a location gets a VERIFIED class", "Distance alone never decides the road")
    steps = [("1", "Query DDOT LRS", "Find candidate roadway\nSubBlocks within 75 m,\nwidening to 200 m. Query\nboth Original and OnSeg\npoints when they differ\n(535 locations)."),
             ("2", "Fetch official attributes", "Look up each SubBlockKey\nin Roadway SubBlock\nlayer 162: route name,\nroad type and\nFHWAFUNCTIONALCLASS."),
             ("3", "Check the address", "Street and quadrant must\nmatch. Accepted blocks\nmust cover the FULL permit\naddress range. Alleys\nare excluded."),
             ("4", "Check the nearest road", "The closest road at every\npoint must agree on street,\nblock and class. Ties and\nboundary conflicts go\nto review.")]
    for i, (n, head, body) in enumerate(steps):
        x0 = 0.035 + i * 0.237
        fig.patches.append(FancyBboxPatch((x0, 0.25), 0.215, 0.47, boxstyle="round,pad=0,rounding_size=0.012",
                                          transform=fig.transFigure, fc="#F8FAFC", ec="#CBD5E1", lw=1.2))
        fig.text(x0 + 0.02, 0.645, n, fontsize=30, fontweight="bold", color="#0F7B6C")
        fig.text(x0 + 0.02, 0.585, head, fontsize=15, fontweight="bold", color=DARK)
        fig.text(x0 + 0.02, 0.535, body, fontsize=11.5, color="#374151", linespacing=1.5, va="top")
    for i, (k, v) in enumerate([("VERIFIED", "all checks pass"), ("PROVISIONAL", "class proposed, road uncertain"),
                                ("UNRESOLVED", "no reliable or conflicting class")]):
        x0 = 0.035 + i * 0.316
        fig.patches.append(FancyBboxPatch((x0, 0.1), 0.295, 0.09, boxstyle="round,pad=0,rounding_size=0.01",
                                          transform=fig.transFigure, fc=STATUS_COLORS[k], ec="none"))
        fig.text(x0 + 0.147, 0.135, f"{k}: {v}", ha="center", fontsize=12.5, color="white", fontweight="semibold")
    save_slide(fig, 4)

    # 5 - class results
    fig = slide_base(5, "Which roads are the permits on?", "Most work is on local streets; about 1 in 3 "
                     "confirmed applications touches an arterial")
    class_bars(fig.add_axes([0.07, 0.14, 0.4, 0.56]), ver_class, "Verified class of each location",
               lambda c: CLASS_COLORS.get(c, "#CBD5E1"), fs=12, ylabel="Locations")
    highest_by_company(fig.add_axes([0.6, 0.3, 0.34, 0.38]), fs=12)
    save_slide(fig, 5)

    # 6 - review & takeaways
    fig = slide_base(6, "What still needs a human look", f"{N_REVIEW_LOC} locations ({N_REVIEW_LOC / N_LOC:.1%}) "
                     f"across {N_REVIEW_APP} applications, all retained in the deliverable")
    reasons_bar(fig.add_axes([0.25, 0.12, 0.3, 0.6]), fs=12)
    fig.text(0.62, 0.68, "Key takeaways", fontsize=17, fontweight="bold", color=DARK)
    fig.text(0.62, 0.62,
             f"1. {N_VER / N_LOC:.1%} of locations passed every\n    automated rule.\n\n"
             f"2. {ver_class.get(7, 0) / N_VER:.0%} of verified locations are on\n    local (Class 7) streets.\n\n"
             f"3. PEPCO's applications reach arterials\n    most often (Class 3-4).\n\n"
             f"4. The largest review group ({reasons.iloc[0]}) is where\n    the nearest road differs from the\n"
             "    written address.\n\n"
             "5. Suggested fixes are documented,\n    never applied automatically.",
             fontsize=13, color="#374151", linespacing=1.32, va="top")
    save_slide(fig, 6)

    frames = [Image.open(SLIDES / f"slide_{i:02d}.png").convert("RGB").resize((1000, 562), Image.LANCZOS)
              for i in range(1, 7)]
    frames = [f.quantize(colors=200, method=Image.Quantize.MEDIANCUT) for f in frames]
    frames[0].save(OUT / "slides_preview.gif", save_all=True, append_images=frames[1:], duration=3200,
                   loop=0, optimize=True)


fig_map()
fig_funnel()
fig_dashboard()
slides()
print("done", N_RAW, N_LOC, N_APP, N_VER, N_CONF, N_REVIEW_LOC, N_REVIEW_APP)
