"""Build vector figures for the full project report from recorded aggregates.

All numeric plots use evidence.json, raw-sources/VALIDATION.md, or
raw-sources/L3_REPORT.md. The figure captions in the report name the snapshot.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle
import numpy as np


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
FIG = HERE / "figures"
EVIDENCE = json.loads((HERE / "evidence.json").read_text(encoding="utf-8"))["results"]

NAVY = "#16324f"
BLUE = "#2b6f9c"
GOLD = "#bc821e"
TEAL = "#2e7b73"
GREY = "#607080"
LIGHT = "#d8e5ec"
PALE = "#f2f6f8"


def setup() -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.titlesize": 11,
        "axes.titleweight": "bold",
        "axes.labelcolor": NAVY,
        "text.color": NAVY,
        "xtick.color": NAVY,
        "ytick.color": NAVY,
        "axes.edgecolor": GREY,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
        "pdf.fonttype": 42,
    })


def save(name: str, fig) -> None:
    fig.savefig(
        FIG / f"{name}.pdf",
        bbox_inches="tight",
        pad_inches=0.1,
        metadata={"CreationDate": datetime(2026, 10, 3, tzinfo=timezone.utc)},
    )
    plt.close(fig)


def year_line(name: str, values: list[float], title: str, ylabel: str,
              color: str = BLUE, note: str | None = None) -> None:
    years = np.array([row["year"] for row in EVIDENCE["years"]])
    fig, ax = plt.subplots(figsize=(7.0, 3.15))
    ax.plot(years, values, color=color, lw=2, marker="o", ms=2.4)
    ax.grid(axis="y", color="#d8e0e6", lw=.6)
    ax.set_xlim(1990, 2025)
    ax.set_xticks([1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025])
    ax.set_ylabel(ylabel)
    ax.set_title(title, loc="left", pad=13)
    ax.scatter([years[0], years[-1]], [values[0], values[-1]], s=29, color=color, zorder=4)
    ax.annotate(f"{values[0]:,.0f}", (years[0], values[0]), xytext=(5, 7), textcoords="offset points", fontsize=8)
    ax.annotate(f"{values[-1]:,.0f}", (years[-1], values[-1]), xytext=(-5, 7), textcoords="offset points", ha="right", fontsize=8)
    if note:
        fig.text(.125, .01, note, fontsize=7.5, color=GREY)
    save(name, fig)


def source_timeline() -> None:
    source = {row["year"]: row["source"] for row in EVIDENCE["year_sources"]}
    colors = {"text": BLUE, "html": GOLD, "json": TEAL}
    labels = {"text": "Project Gutenberg text", "html": "CIA HTML ZIP", "json": "JSON snapshot"}
    fig, ax = plt.subplots(figsize=(7.0, 2.3))
    for year in range(1990, 2026):
        ax.add_patch(Rectangle((year-.46, .4), .92, .55, facecolor=colors[source[year]], edgecolor="white", lw=.6))
    ax.set_xlim(1989.4, 2025.6)
    ax.set_ylim(0, 1.24)
    ax.set_yticks([])
    ax.set_xticks([1990,1995,2000,2005,2010,2015,2020,2025])
    ax.spines[["left", "bottom"]].set_visible(False)
    ax.set_title("The archived editions span three source formats", loc="left", pad=11)
    handles = [Rectangle((0,0),1,1,color=colors[k]) for k in ("text","html","json")]
    ax.legend(handles, [labels[k] for k in ("text","html","json")], frameon=False,
              loc="lower center", bbox_to_anchor=(.5,-.44), ncol=3, fontsize=8)
    save("01-source-timeline", fig)


def fields_per_entry() -> None:
    buckets = defaultdict(list)
    for row in EVIDENCE["field_quantiles_input"]:
        buckets[row["year"]].append(row["fields"])
    years = sorted(buckets)
    q25 = [np.percentile(buckets[y], 25) for y in years]
    med = [np.median(buckets[y]) for y in years]
    q75 = [np.percentile(buckets[y], 75) for y in years]
    fig, ax = plt.subplots(figsize=(7.0,3.25))
    ax.fill_between(years,q25,q75,color=LIGHT,label="Middle 50% of entries")
    ax.plot(years,med,color=BLUE,lw=2,label="Median entry")
    ax.set_xlim(1990,2025)
    ax.set_xticks([1990,1995,2000,2005,2010,2015,2020,2025])
    ax.set_ylabel("Field rows per country-year")
    ax.set_title("Field counts per entry vary by edition",loc="left",pad=12)
    ax.grid(axis="y",color="#d8e0e6",lw=.6)
    ax.legend(frameon=False,loc="upper left",fontsize=8)
    save("04-entry-distribution",fig)


def category_2025() -> None:
    rows=list(reversed(EVIDENCE["categories_2025"]))
    fig,ax=plt.subplots(figsize=(7.0,4.3))
    y=np.arange(len(rows))
    ax.barh(y,[r["fields"] for r in rows],color=BLUE,height=.73)
    ax.set_yticks(y,[r["category"] for r in rows],fontsize=8)
    ax.set_xlabel("Stored field rows")
    ax.set_title("The final edition spans 13 source categories",loc="left",pad=12)
    ax.grid(axis="x",color="#d8e0e6",lw=.6)
    ax.set_axisbelow(True)
    ax.set_xlim(0,max(r["fields"] for r in rows)*1.16)
    for i,r in enumerate(rows): ax.text(r["fields"]+75,i,f'{r["fields"]:,}',va="center",fontsize=7.5)
    save("06-categories-2025",fig)


def entity_editions() -> None:
    counts=Counter(r["editions"] for r in EVIDENCE["entity_years"])
    bins=[(0,5),(6,10),(11,20),(21,30),(31,35),(36,36)]
    labels=["0-5","6-10","11-20","21-30","31-35","36"]
    values=[sum(n for k,n in counts.items() if lo<=k<=hi) for lo,hi in bins]
    fig,ax=plt.subplots(figsize=(7.0,3.0))
    ax.bar(labels,values,color=[LIGHT,BLUE,BLUE,BLUE,BLUE,GOLD],edgecolor=NAVY,lw=.4)
    for i,v in enumerate(values):ax.text(i,v+1,str(v),ha="center",fontsize=8)
    ax.set_ylim(0,max(values)*1.15)
    ax.set_ylabel("Canonical entities")
    ax.set_xlabel("Number of editions represented")
    ax.set_title("Entity histories have different lengths",loc="left",pad=11)
    ax.grid(axis="y",color="#d8e0e6",lw=.6)
    ax.set_axisbelow(True)
    save("07-entity-editions",fig)


def mapping_types() -> None:
    rows=list(reversed(EVIDENCE["mapping_types"]))
    fig,ax=plt.subplots(figsize=(7.0,3.0))
    y=np.arange(len(rows))
    ax.barh(y,[r["names"] for r in rows],color=TEAL,height=.68)
    ax.set_yticks(y,[r["mapping_type"].replace("_"," ") for r in rows],fontsize=8)
    ax.set_xlabel("Distinct original field names")
    ax.set_title("Mapping decisions are recorded by type",loc="left",pad=12)
    ax.grid(axis="x",color="#d8e0e6",lw=.6)
    ax.set_axisbelow(True)
    ax.set_xlim(0,max(r["names"] for r in rows)*1.18)
    for i,r in enumerate(rows):ax.text(r["names"]+6,i,str(r["names"]),va="center",fontsize=8)
    save("08-mapping-types",fig)


def values_by_year() -> None:
    years=[r["year"] for r in EVIDENCE["field_values_year"]]
    vals=[r["value_count"] for r in EVIDENCE["field_values_year"]]
    fields=[r["fields"] for r in EVIDENCE["years"]]
    fig,ax=plt.subplots(figsize=(7.0,3.25))
    ax.plot(years,vals,color=TEAL,lw=2,label="Derived sub-value rows")
    ax.plot(years,fields,color=BLUE,lw=2,ls="--",label="Stored field rows")
    ax.set_xlim(1990,2025)
    ax.set_xticks([1990,1995,2000,2005,2010,2015,2020,2025])
    ax.set_ylabel("Rows in local SQLite snapshot")
    ax.set_title("Sub-value counts reflect the parser as well as source structure",loc="left",pad=11)
    ax.grid(axis="y",color="#d8e0e6",lw=.6)
    ax.legend(frameon=False,loc="upper left",fontsize=8)
    save("09-field-values",fig)


def numeric_share() -> None:
    rows=EVIDENCE["field_values_year"]
    years=[r["year"] for r in rows]
    share=[100*r["numeric_values"]/r["value_count"] for r in rows]
    fig,ax=plt.subplots(figsize=(7.0,3.0))
    ax.plot(years,share,color=TEAL,lw=2,marker="o",ms=2.3)
    ax.set_xlim(1990,2025)
    ax.set_xticks([1990,1995,2000,2005,2010,2015,2020,2025])
    ax.set_ylim(0,100)
    ax.set_ylabel("Share with NumericVal (%)")
    ax.set_title("Numeric parsing varies by edition",loc="left",pad=12)
    ax.grid(axis="y",color="#d8e0e6",lw=.6)
    save("10-numeric-share",fig)


def computed_values() -> None:
    rows=EVIDENCE["field_values_year"]
    rows=[r for r in rows if r["computed_values"]]
    fig,ax=plt.subplots(figsize=(7.0,2.65))
    ax.bar([r["year"] for r in rows],[r["computed_values"] for r in rows],color=GOLD,width=.75)
    ax.set_xticks([r["year"] for r in rows])
    ax.set_ylabel("Rows with IsComputed = 1")
    ax.set_title("Computed sub-values are explicitly flagged",loc="left",pad=12)
    ax.grid(axis="y",color="#d8e0e6",lw=.6)
    ax.set_axisbelow(True)
    save("11-computed-values",fig)


def validation_l1() -> None:
    text=(REPO/"raw-sources"/"VALIDATION.md").read_text(encoding="utf-8")
    rows=[]
    for line in text.splitlines():
        m=re.match(r'^\| (\d{4}) \| (text|html|json) \| (\d+(?:\.\d+)?)% \|',line)
        if m: rows.append((int(m[1]),m[2],float(m[3])))
    assert len(rows)==36,len(rows)
    color={"text":BLUE,"html":GOLD,"json":TEAL}
    fig,ax=plt.subplots(figsize=(7.0,3.0))
    for year,source,pct in rows:ax.bar(year,pct,color=color[source],width=.82)
    ax.set_xlim(1989.3,2025.7)
    ax.set_xticks([1990,1995,2000,2005,2010,2015,2020,2025])
    ax.set_ylim(0,105)
    ax.set_ylabel("Exact substring hits (%)")
    ax.set_title("L1 measures verbatim fragments, not source correctness",loc="left",pad=12)
    ax.grid(axis="y",color="#d8e0e6",lw=.6)
    ax.set_axisbelow(True)
    save("12-validation-l1",fig)


def validation_l3() -> None:
    text=(REPO/"raw-sources"/"L3_REPORT.md").read_text(encoding="utf-8")
    rows=[]
    for line in text.splitlines():
        m=re.match(r'^\| (\d{4}) \| (\w+) \| ([\d,]+) \| ([\d,]+) \| ([\d,]+) \|',line)
        if m: rows.append((int(m[1]),int(m[4].replace(',','')),int(m[5].replace(',',''))))
    assert len(rows)==36,len(rows)
    fig,ax=plt.subplots(figsize=(7.0,3.0))
    years=[r[0] for r in rows]
    share=[100*r[2]/r[1] for r in rows]
    ax.bar(years,share,color=[GOLD if y in (1996,2008) else BLUE for y in years],width=.84)
    ax.set_xlim(1989.3,2025.7)
    ax.set_xticks([1990,1996,2001,2008,2014,2020,2025])
    ax.set_ylim(0,105)
    ax.set_ylabel("Matched rows / DB rows (%)")
    ax.set_title("The May L3 rerun needs a corrected residual accounting",loc="left",pad=12)
    ax.grid(axis="y",color="#d8e0e6",lw=.6)
    ax.set_axisbelow(True)
    for year, label, text_year in [(1996, "1996 repair shape", 1998.0),
                                   (2008, "2008 duplicate source", 2010.0)]:
        ax.annotate(label, xy=(year, share[years.index(year)]),
                    xytext=(text_year, 77), ha="left", va="center",
                    color=NAVY, fontsize=8, fontweight="bold",
                    bbox={"boxstyle":"round,pad=0.25", "facecolor":"white",
                          "edgecolor":GOLD, "linewidth":0.8},
                    arrowprops={"arrowstyle":"-", "color":GOLD, "lw":0.9})
    save("13-validation-l3",fig)


def pipeline() -> None:
    fig,ax=plt.subplots(figsize=(7.0,3.1))
    ax.set_xlim(0,7);ax.set_ylim(0,3);ax.axis("off")
    nodes=[
        (.15,1.75,1.65,.75,"Released inputs\n38 files / 36 editions",BLUE),
        (2.05,1.75,1.55,.75,"Year-specific\nparsers",GOLD),
        (3.86,1.75,1.35,.75,"SQLite\ncanonical DB",TEAL),
        (5.48,2.25,1.35,.53,"Website",NAVY),
        (5.48,1.49,1.35,.53,"Offline app",NAVY),
        (5.48,.73,1.35,.53,"Data releases",NAVY),
    ]
    for x,y,w,h,label,color in nodes:
        ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle="round,pad=0.04,rounding_size=.08",facecolor=color,edgecolor=color))
        ax.text(x+w/2,y+h/2,label,ha="center",va="center",color="white",fontsize=8,fontweight="bold")
    for a,b in [((1.84,2.12),(2.01,2.12)),((3.64,2.12),(3.82,2.12)),
                ((5.25,2.12),(5.44,2.51)),((5.25,2.12),(5.44,1.75)),((5.25,2.12),(5.44,.99))]:
        ax.add_patch(FancyArrowPatch(a,b,arrowstyle="-|>",mutation_scale=10,color=GREY,lw=1.2))
    ax.text(.15,.51,"Evidence layers: hashes identify files; reruns test parsing; audits check identity and structure.",fontsize=7.8,color=GREY)
    ax.set_title("One source lineage, several access channels",loc="left",pad=11)
    save("14-provenance-pipeline",fig)


def estimate_tokens() -> None:
    rows=EVIDENCE["final_estimate_tokens"]
    years=[r["estimate_year"] for r in rows]
    vals=[r["fields_with_token"] for r in rows]
    fig,ax=plt.subplots(figsize=(7.0,3.0))
    colors=[GOLD if y in (2025,2026,2027) else BLUE for y in years]
    ax.bar([str(y) for y in years],vals,color=colors,width=.76)
    for i,v in enumerate(vals):
        ax.text(i,v+85,f"{v:,}",ha="center",fontsize=7.5)
    ax.set_ylim(0,max(vals)*1.15)
    ax.set_ylabel("2025 fields containing literal token")
    ax.set_title("The final edition includes estimates from earlier years",loc="left",pad=11)
    ax.grid(axis="y",color="#d8e0e6",lw=.6)
    ax.set_axisbelow(True)
    save("15-final-estimate-tokens",fig)


def source_bytes() -> None:
    manifest=json.loads((REPO/"raw-sources"/"MANIFEST.json").read_text(encoding="utf-8"))
    totals=defaultdict(int)
    for row in manifest["files"]:
        era="text (incl. repair)" if row["era"] in ("text","text-repair") else row["era"]
        totals[era]+=row["size_bytes"]
    items=sorted(totals.items(),key=lambda x:x[1])
    fig,ax=plt.subplots(figsize=(7.0,2.65))
    y=np.arange(len(items))
    values=[n/1e6 for _,n in items]
    ax.barh(y,values,color=[TEAL,BLUE,GOLD],height=.62)
    ax.set_yticks(y,[k.upper() if k!="text (incl. repair)" else "TEXT + REPAIR" for k,_ in items])
    ax.set_xlabel("Released input bytes (decimal MB; log scale)")
    ax.set_xscale("log")
    ax.set_xlim(10,10000)
    ax.set_title("Archived HTML ZIPs dominate the source bundle by bytes",loc="left",pad=11)
    ax.grid(axis="x",color="#d8e0e6",lw=.6)
    ax.set_axisbelow(True)
    for i,v in enumerate(values):ax.text(v*1.11,i,f"{v:,.1f} MB",va="center",fontsize=8)
    save("16-source-bytes",fig)


def main() -> None:
    setup()
    source_timeline()
    year_line("02-country-years",[r["country_years"] for r in EVIDENCE["years"]],
              "Edition coverage is not a fixed country roster","Country-year entries")
    year_line("03-field-rows",[r["fields"] for r in EVIDENCE["years"]],
              "Stored fields rise and fall with content and parsing rules","Field rows")
    fields_per_entry()
    year_line("05-field-names",[r["field_names"] for r in EVIDENCE["years"]],
              "Raw field-label counts change sharply in some text years","Distinct original labels",GOLD)
    category_2025()
    entity_editions()
    mapping_types()
    values_by_year()
    numeric_share()
    computed_values()
    validation_l1()
    validation_l3()
    pipeline()
    estimate_tokens()
    source_bytes()
    print(f"Created {len(list(FIG.glob('*.pdf')))} vector figures in {FIG}")


if __name__ == "__main__":
    main()
