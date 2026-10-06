import html
import re
import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Boston Food Inspections", layout="wide", page_icon="🍽️")

RESOURCE_ID = "4582bec6-2b4f-4f9e-bc55-cbaa73117f4c"
API_URL = "https://data.boston.gov/api/3/action/datastore_search"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
PAGE_SIZE = 32000

st.markdown("""
<style>
    h1 {color: #1e3a8a;}
    .disclaimer {background:#fff7ed; border-left:5px solid #f97316;
                 padding:12px; border-radius:8px; color:#7c2d12; font-size:0.88rem;}
    .footer {margin-top:40px; padding:14px; background:#f1f5f9;
             border-radius:8px; text-align:center; color:#475569; font-size:0.85rem;}
    .restaurant-card {border:1px solid #e2e8f0; border-radius:10px;
                      padding:18px 22px; margin-bottom:14px; background:white;}
    .restaurant-card.pass {border-left:6px solid #22c55e;}
    .restaurant-card.fail {border-left:6px solid #ef4444;}
    .restaurant-card.other {border-left:6px solid #94a3b8;}
    .badge {display:inline-block; padding:4px 12px; border-radius:20px;
            font-weight:700; font-size:0.85rem;}
    .badge.pass {background:#dcfce7; color:#166534;}
    .badge.fail {background:#fee2e2; color:#991b1b;}
    .badge.other {background:#e2e8f0; color:#334155;}
    .violations-box {margin-top:14px; padding:12px 14px; background:#fef2f2;
                     border-radius:8px; border:1px solid #fecaca;}
    .violations-box.ok {background:#f0fdf4; border-color:#bbf7d0;}
    .violations-title {font-weight:700; font-size:0.88rem; margin-bottom:6px; color:#991b1b;}
    .violations-title.ok {color:#166534;}
    .violations-list {margin:0; padding-left:18px; color:#475569; font-size:0.83rem;}
    .violations-list li {margin-bottom:4px;}
</style>
""", unsafe_allow_html=True)

st.title("🍽️ Boston Food Establishment Inspections")
st.caption("Source: City of Boston Open Data · 97,634 inspection records")

st.markdown("""
<div class="disclaimer">
⚠️ <b>Pilot Project:</b> Open-source tool for exploratory visualization.
The author assumes no responsibility for decisions derived from these outputs.
Always verify with official City of Boston records.
</div>
""", unsafe_allow_html=True)


def categorize(v):
    if pd.isna(v): return "Other"
    s = str(v).lower()
    if "pass" in s: return "Pass"
    if "fail" in s: return "Fail"
    return "Other"


def pick_name(row):
    for col in ["businessname", "dbaname", "legalowner"]:
        if col in row and pd.notna(row[col]) and str(row[col]).strip():
            return str(row[col]).strip()
    return "Unknown establishment"


def parse_loc(v):
    if pd.isna(v): return (None, None)
    m = re.match(r"\s*\(\s*([-0-9.]+)\s*,\s*([-0-9.]+)\s*\)", str(v))
    if not m: return (None, None)
    try: return (float(m.group(1)), float(m.group(2)))
    except: return (None, None)


@st.cache_data(ttl=3600, show_spinner=False)
def load_data():
    all_records = []
    offset = 0
    total = None
    while True:
        params = {"resource_id": RESOURCE_ID, "limit": PAGE_SIZE, "offset": offset}
        r = requests.get(API_URL, params=params, headers=HEADERS, timeout=120)
        r.raise_for_status()
        result = r.json()["result"]
        records = result["records"]
        if total is None:
            total = result["total"]
        all_records.extend(records)
        if len(records) < PAGE_SIZE or len(all_records) >= total:
            break
        offset += PAGE_SIZE

    df = pd.DataFrame(all_records)
    df["_name"] = df.apply(pick_name, axis=1)

    if "zip" in df.columns:
        z = df["zip"].astype(str).str.strip()
        df["_zip"] = z.where(~z.isin(["nan", "None", "", "NaN"]), None)
    else:
        df["_zip"] = None

    if "location" in df.columns:
        coords = df["location"].apply(parse_loc)
        df["lat"] = coords.apply(lambda t: t[0])
        df["lon"] = coords.apply(lambda t: t[1])
    else:
        df["lat"] = None
        df["lon"] = None

    parts = []
    for col in ["businessname", "dbaname", "legalowner", "address", "city", "zip"]:
        if col in df.columns:
            parts.append(df[col].fillna("").astype(str))
    if parts:
        blob = parts[0]
        for p in parts[1:]:
            blob = blob + " | " + p
        df["_search"] = blob.str.lower()
    else:
        df["_search"] = ""

    return df, total


with st.spinner("Loading records from Boston Open Data..."):
    try:
        df, total_api = load_data()
    except Exception as e:
        st.error(f"Error contacting the API: {e}")
        st.stop()

# Parse dates
if "resultdttm" in df.columns:
    df["resultdttm"] = pd.to_datetime(df["resultdttm"], errors="coerce", utc=True).dt.tz_localize(None)

# Category
if "result" in df.columns:
    df["_cat"] = df["result"].apply(categorize)
else:
    df["_cat"] = "Other"

# Date bounds
if "resultdttm" in df.columns and df["resultdttm"].notna().any():
    min_date = df["resultdttm"].min().date()
    max_date = df["resultdttm"].max().date()
else:
    from datetime import date
    min_date, max_date = date(2000, 1, 1), date.today()


# ============================================================
# TABS AT TOP
# ============================================================
tab_search, tab_map = st.tabs(["🔍 Search", "🗺️ Map View"])


# ============================================================
# TAB 1: SEARCH
# ============================================================
with tab_search:
    with st.sidebar:
        st.header("🔍 Filters")
        name_q = st.text_input("Restaurant name or keyword",
                               placeholder="e.g. pizza hut, dunkin",
                               key="f_name")
        zips = sorted(df["_zip"].dropna().unique())
        sel_zips = st.multiselect("ZIP code", zips, default=[], key="f_zips")
        st.markdown("**Inspection result**")
        sel_cats = st.multiselect("Category", ["Pass", "Fail"], default=[], key="f_cats")

    fdf = df.copy()
    if name_q.strip() and "_search" in fdf.columns:
        tokens = [t for t in name_q.strip().lower().split() if t]
        mask = pd.Series(True, index=fdf.index)
        for tok in tokens:
            mask &= fdf["_search"].str.contains(tok, regex=False, na=False)
        fdf = fdf[mask]
    if sel_zips:
        fdf = fdf[fdf["_zip"].isin(sel_zips)]
    if sel_cats:
        fdf = fdf[fdf["_cat"].isin(sel_cats)]

    pass_n = (fdf["_cat"] == "Pass").sum()
    fail_n = (fdf["_cat"] == "Fail").sum()
    rate = (pass_n / len(fdf) * 100) if len(fdf) else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total in dataset", f"{total_api:,}")
    c2.metric("After filters", f"{len(fdf):,}")
    c3.metric("Pass rate", f"{rate:.1f}%")
    c4.metric("Fail count", f"{fail_n:,}")

    st.divider()

    if len(fdf) == 0:
        st.warning("No records match the current filters.")
    else:
        cols = [c for c in ["businessname", "address", "city", "zip", "result",
                            "resultdttm", "viol_level", "violdesc", "comments"]
                if c in fdf.columns]
        view = fdf[cols].copy()
        if "resultdttm" in view.columns:
            view = view.sort_values("resultdttm", ascending=False)
        st.dataframe(view.head(5000), use_container_width=True, height=520)
        st.download_button("📥 Download filtered (CSV)",
                           fdf[cols].to_csv(index=False).encode("utf-8"),
                           "boston_inspections.csv", "text/csv")


# ============================================================
# TAB 2: MAP VIEW
# ============================================================
with tab_map:
    st.markdown("### 🗺️ Map View")
    st.caption("Choose a period, explore the map, then pick a restaurant to see its card.")

    from datetime import date, timedelta

    preset = st.radio(
        "Period",
        ["Last 30 days", "Last 15 days", "Last week", "Last year", "All time"],
        index=0, horizontal=True, key="map_period",
    )
    if preset == "Last week":
        m_from, m_to = max_date - timedelta(days=7), max_date
    elif preset == "Last 15 days":
        m_from, m_to = max_date - timedelta(days=15), max_date
    elif preset == "Last 30 days":
        m_from, m_to = max_date - timedelta(days=30), max_date
    elif preset == "Last year":
        m_from, m_to = max_date - timedelta(days=365), max_date
    else:
        m_from, m_to = min_date, max_date

    mdf = df.copy()
    if "resultdttm" in mdf.columns:
        mdf = mdf[mdf["resultdttm"] >= pd.Timestamp(m_from)]
        mdf = mdf[mdf["resultdttm"] <= pd.Timestamp(m_to) + pd.Timedelta("1D")]

    mdf = mdf.dropna(subset=["lat", "lon"]).copy()
    mdf = mdf[mdf["lat"].between(-90, 90) & mdf["lon"].between(-180, 180)]

    st.success(f"Period: **{m_from} → {m_to}** · {len(mdf):,} inspections with coordinates")

    if len(mdf) == 0:
        st.warning("No geolocated records in this period.")
    else:
        # ---- MAP ----
        st.markdown("#### 📍 Map")
        sample = mdf.sample(min(len(mdf), 15000), random_state=42) if len(mdf) > 15000 else mdf
        st.map(sample[["lat", "lon"]].rename(columns={"lat": "latitude", "lon": "longitude"}),
               zoom=11, use_container_width=True)

        # ---- RESTAURANT PICKER ----
        st.markdown("#### 🏪 Pick a restaurant")
        grouped = (mdf.groupby(["_name", "address"], dropna=False)
                     .size().reset_index(name="n")
                     .sort_values("n", ascending=False))

        labels = []
        for _, r in grouped.iterrows():
            nm = str(r["_name"])
            ad = str(r["address"]) if pd.notna(r["address"]) else "—"
            labels.append(f"{nm} · {ad}")

        sel = st.selectbox(f"Choose ({len(labels):,} restaurants in this period)",
                           labels, index=0, key="map_pick")

        if sel:
            idx = labels.index(sel)
            row = grouped.iloc[idx]
            rest = mdf[(mdf["_name"] == row["_name"]) &
                       (mdf["address"].astype(str) == str(row["address"]))]
            rest = rest.sort_values("resultdttm", ascending=False)

            inspections = len(rest)
            passes = (rest["_cat"] == "Pass").sum()
            fails = (rest["_cat"] == "Fail").sum()
            prate = int(round(passes / inspections * 100)) if inspections else 0

            latest = rest.iloc[0] if len(rest) else None
            latest_res = latest["_cat"] if latest is not None else "Other"
            latest_dt = latest["resultdttm"] if latest is not None else None
            date_str = latest_dt.strftime("%b %d, %Y") if pd.notna(latest_dt) else "N/A"

            if latest_res == "Pass":
                cls, bcls, btxt = "pass", "pass", "PASS"
            elif latest_res == "Fail":
                cls, bcls, btxt = "fail", "fail", "FAIL"
            else:
                cls, bcls, btxt = "other", "other", str(latest_res).upper()

            violations = []
            if latest is not None and "violdesc" in rest.columns:
                same_day = rest[rest["resultdttm"] == latest_dt]
                for _, vr in same_day.iterrows():
                    d = vr.get("violdesc")
                    if pd.notna(d) and str(d).strip():
                        violations.append(str(d).strip())

            if violations:
                items = "".join(f"<li>{html.escape(v)}</li>" for v in violations[:6])
                extra = f"<li>... +{len(violations)-6} more</li>" if len(violations) > 6 else ""
                vhtml = f'<div class="violations-box"><div class="violations-title">⚠️ Issues in latest inspection ({date_str}):</div><ul class="violations-list">{items}{extra}</ul></div>'
            else:
                vhtml = f'<div class="violations-box ok"><div class="violations-title ok">✅ No violations in latest inspection ({date_str}).</div></div>'

            st.markdown(f"""
            <div class="restaurant-card {cls}">
                <div style="display:flex; justify-content:space-between;">
                    <div>
                        <div style="font-size:1.1rem; font-weight:700; color:#0f172a;">{html.escape(str(row['_name']))}</div>
                        <div style="color:#64748b; font-size:0.88rem; margin-top:2px;">📍 {html.escape(str(row['address']))}</div>
                    </div>
                    <span class="badge {bcls}">{btxt}</span>
                </div>
                <div style="display:flex; gap:30px; margin-top:14px; font-size:0.9rem;">
                    <div><b>{inspections}</b> <span style="color:#64748b;">inspections</span></div>
                    <div><b style="color:#166534;">{passes}</b> <span style="color:#64748b;">passes</span></div>
                    <div><b style="color:#991b1b;">{fails}</b> <span style="color:#64748b;">fails</span></div>
                    <div><b>{prate}%</b> <span style="color:#64748b;">pass rate</span></div>
                </div>
                {vhtml}
            </div>
            """, unsafe_allow_html=True)


st.markdown("""
<div class="footer">
<b>Boston Food Inspections Dashboard</b> — Pilot Project · MIT License<br>
🔗 <a href="https://github.com/renatoerss">github.com/renatoerss</a>
</div>
""", unsafe_allow_html=True)
