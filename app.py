import html
import re
import streamlit as st
import pandas as pd
import requests
from datetime import date, timedelta

st.set_page_config(
    page_title="Boston Food Inspections",
    layout="wide",
    page_icon="🍽️",
)

RESOURCE_ID = "4582bec6-2b4f-4f9e-bc55-cbaa73117f4c"
API_URL = "https://data.boston.gov/api/3/action/datastore_search"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}
PAGE_SIZE = 32000
SEARCH_FIELDS = ["businessname", "dbaname", "legalowner", "address", "city", "zip"]


# ---------- Styling ----------
st.markdown(
    """
    <style>
        h1 {color: #1e3a8a;}
        .disclaimer {
            background: #fff7ed; border-left: 5px solid #f97316;
            padding: 12px; border-radius: 8px; color: #7c2d12; font-size: 0.88rem;
        }
        .footer {
            margin-top: 40px; padding: 14px; background: #f1f5f9;
            border-radius: 8px; text-align: center; color: #475569; font-size: 0.85rem;
        }
        .restaurant-card {
            border: 1px solid #e2e8f0; border-radius: 10px;
            padding: 18px 22px; margin-bottom: 14px; background: white;
        }
        .restaurant-card.pass {border-left: 6px solid #22c55e;}
        .restaurant-card.fail {border-left: 6px solid #ef4444;}
        .restaurant-card.other {border-left: 6px solid #94a3b8;}
        .badge {
            display: inline-block; padding: 4px 12px; border-radius: 20px;
            font-weight: 700; font-size: 0.85rem;
        }
        .badge.pass {background: #dcfce7; color: #166534;}
        .badge.fail {background: #fee2e2; color: #991b1b;}
        .badge.other {background: #e2e8f0; color: #334155;}
        .violations-box {
            margin-top: 14px; padding: 12px 14px; background: #fef2f2;
            border-radius: 8px; border: 1px solid #fecaca;
        }
        .violations-box.ok {background: #f0fdf4; border-color: #bbf7d0;}
        .violations-title {
            font-weight: 700; font-size: 0.88rem; margin-bottom: 6px; color: #991b1b;
        }
        .violations-title.ok {color: #166534;}
        .violations-list {
            margin: 0; padding-left: 18px; color: #475569; font-size: 0.83rem;
        }
        .violations-list li {margin-bottom: 4px;}
        .viol-level {
            display: inline-block; padding: 1px 6px; border-radius: 4px;
            font-size: 0.72rem; font-weight: 700; margin-left: 4px;
        }
        .viol-level.minor {background: #fef3c7; color: #92400e;}
        .viol-level.moderate {background: #fed7aa; color: #9a3412;}
        .viol-level.critical {background: #fecaca; color: #7f1d1d;}
        .hbar-row {
            display: flex; align-items: center; margin-bottom: 6px; font-size: 0.85rem;
        }
        .hbar-label {
            width: 40%; padding-right: 8px; color: #334155;
            white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
        }
        .hbar-track {
            flex: 1; background: #e2e8f0; border-radius: 6px; height: 20px; overflow: hidden;
        }
        .hbar-fill {height: 100%; border-radius: 6px;}
        .hbar-value {
            min-width: 60px; text-align: right; color: #475569; padding-left: 8px;
        }
        .step-box {
            background: #eff6ff; border-left: 5px solid #3b82f6;
            padding: 12px 16px; border-radius: 8px; margin: 8px 0 16px 0;
            color: #1e3a8a; font-size: 0.92rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------- Header ----------
st.title("🍽️ Boston Food Establishment Inspections")
st.caption("Source: City of Boston Open Data · 97,634 inspection records")

st.markdown(
    """
    <div class="disclaimer">
        ⚠️ <b>Pilot Project:</b> This is a pilot-stage, open-source tool for exploratory
        visualization. The author assumes <b>no responsibility</b> for decisions derived
        from these outputs. Always verify with official City of Boston records.
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------- Helpers ----------
def categorize_result(value):
    if pd.isna(value):
        return "Other"
    v = str(value).lower()
    if "pass" in v:
        return "Pass"
    if "fail" in v:
        return "Fail"
    return "Other"


def pick_display_name(row):
    for col in ["businessname", "dbaname", "legalowner"]:
        if col in row and pd.notna(row[col]) and str(row[col]).strip():
            return str(row[col]).strip()
    return "Unknown establishment"


def classify_severity(level):
    if pd.isna(level):
        return "minor", ""
    s = str(level).strip()
    if s == "***" or "critical" in s.lower():
        return "critical", "CRITICAL"
    if s == "**" or "moderate" in s.lower():
        return "moderate", "MODERATE"
    if s == "*" or "minor" in s.lower():
        return "minor", "MINOR"
    return "minor", s


def parse_latlon(loc):
    if pd.isna(loc):
        return (None, None)
    m = re.match(r"\s*\(\s*([-0-9.]+)\s*,\s*([-0-9.]+)\s*\)\s*", str(loc))
    if not m:
        return (None, None)
    try:
        return (float(m.group(1)), float(m.group(2)))
    except Exception:
        return (None, None)


def render_hbar_chart(series, color="#3b82f6"):
    if series is None or len(series) == 0:
        st.caption("No data to display.")
        return
    max_val = series.max() or 1
    rows = []
    for label, value in series.items():
        pct = (value / max_val) * 100
        safe_label = html.escape(str(label))
        rows.append(
            f'<div class="hbar-row">'
            f'<div class="hbar-label" title="{safe_label}">{safe_label}</div>'
            f'<div class="hbar-track">'
            f'<div class="hbar-fill" style="width:{pct:.1f}%; background:{color};"></div>'
            f'</div>'
            f'<div class="hbar-value">{value:,}</div>'
            f'</div>'
        )
    st.markdown("".join(rows), unsafe_allow_html=True)


def render_restaurant_card(rest_df, name, addr):
    """
    Given all inspection rows for one restaurant (already filtered),
    render the summary card with the latest-result badge and violations.
    """
    rest_df = rest_df.sort_values("resultdttm", ascending=False, na_position="last")

    inspections = len(rest_df)
    passes = (rest_df["result_category"] == "Pass").sum()
    fails = (rest_df["result_category"] == "Fail").sum()
    pass_rate = int(round(passes / inspections * 100)) if inspections else 0

    latest_row = rest_df.iloc[0] if len(rest_df) else None
    latest_result = latest_row["result_category"] if latest_row is not None else "Other"
    latest_date = latest_row["resultdttm"] if latest_row is not None else None

    if latest_result == "Pass":
        card_cls, badge_cls, badge_txt = "pass", "pass", "PASS"
    elif latest_result == "Fail":
        card_cls, badge_cls, badge_txt = "fail", "fail", "FAIL"
    else:
        card_cls, badge_cls, badge_txt = "other", "other", str(latest_result).upper()

    date_str = latest_date.strftime("%b %d, %Y") if pd.notna(latest_date) else "N/A"

    # Violations from the most recent inspection
    violations = []
    if latest_row is not None and "violdesc" in rest_df.columns:
        latest_rows = rest_df[rest_df["resultdttm"] == latest_date] if pd.notna(latest_date) else rest_df.head(0)
        for _, vr in latest_rows.iterrows():
            desc = vr.get("violdesc")
            lvl = vr.get("viol_level")
            if pd.notna(desc) and str(desc).strip():
                violations.append((str(desc).strip(), lvl))

    if violations:
        items_html = ""
        for desc, lvl in violations[:6]:
            sev_cls, sev_txt = classify_severity(lvl)
            sev_html = f'<span class="viol-level {sev_cls}">{sev_txt}</span>' if sev_txt else ""
            items_html += f"<li>{html.escape(desc)}{sev_html}</li>"
        extra = ""
        if len(violations) > 6:
            extra = f"<li style='color:#94a3b8;'>... and {len(violations)-6} more</li>"
        viol_html = f"""
            <div class="violations-box">
                <div class="violations-title">⚠️ Issues found in latest inspection ({date_str}):</div>
                <ul class="violations-list">{items_html}{extra}</ul>
            </div>
        """
    else:
        viol_html = f"""
            <div class="violations-box ok">
                <div class="violations-title ok">✅ No violations recorded in latest inspection ({date_str}).</div>
            </div>
        """

    st.markdown(
        f"""
        <div class="restaurant-card {card_cls}">
            <div style="display:flex; justify-content:space-between; align-items:start;">
                <div>
                    <div style="font-size:1.1rem; font-weight:700; color:#0f172a;">
                        {html.escape(str(name))}
                    </div>
                    <div style="color:#64748b; font-size:0.88rem; margin-top:2px;">
                        📍 {html.escape(str(addr))}
                    </div>
                </div>
                <div style="text-align:right;">
                    <span class="badge {badge_cls}">{badge_txt}</span>
                </div>
            </div>
            <div style="display:flex; gap:30px; margin-top:14px; font-size:0.9rem;">
                <div><b>{inspections}</b> <span style="color:#64748b;">inspections</span></div>
                <div><b style="color:#166534;">{passes}</b> <span style="color:#64748b;">passes</span></div>
                <div><b style="color:#991b1b;">{fails}</b> <span style="color:#64748b;">fails</span></div>
                <div><b>{pass_rate}%</b> <span style="color:#64748b;">pass rate</span></div>
            </div>
            {viol_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------- Data loading ----------
@st.cache_data(ttl=3600, show_spinner=False)
def load_all_data():
    all_records = []
    offset = 0
    total = None
    while True:
        params = {"resource_id": RESOURCE_ID, "limit": PAGE_SIZE, "offset": offset}
        r = requests.get(API_URL, params=params, headers=HEADERS, timeout=120)
        r.raise_for_status()
        payload = r.json()
        result = payload["result"]
        records = result["records"]
        if total is None:
            total = result["total"]
        all_records.extend(records)
        if len(records) < PAGE_SIZE or len(all_records) >= total:
            break
        offset += PAGE_SIZE

    df = pd.DataFrame(all_records)

    df["_display_name"] = df.apply(pick_display_name, axis=1)

    if "zip" in df.columns:
        z = df["zip"].astype(str).str.strip()
        z = z.where(~z.isin(["nan", "None", "", "NaN"]), None)
        df["_zip_clean"] = z
    else:
        df["_zip_clean"] = None

    # Parse location into lat/lon
    if "location" in df.columns:
        coords = df["location"].apply(parse_latlon)
        df["lat"] = coords.apply(lambda t: t[0])
        df["lon"] = coords.apply(lambda t: t[1])
    else:
        df["lat"] = None
        df["lon"] = None

    parts = []
    for col in SEARCH_FIELDS:
        if col in df.columns:
            parts.append(df[col].fillna("").astype(str))
    if parts:
        blob = parts[0]
        for p in parts[1:]:
            blob = blob + " | " + p
        df["_search_blob"] = blob.str.lower()
    else:
        df["_search_blob"] = ""

    return df, total


with st.spinner("Loading all records from Boston Open Data (first run ~15–25 s)..."):
    try:
        df, total_api = load_all_data()
    except Exception as e:
        st.error(f"Error contacting the API: {e}")
        st.stop()

if "resultdttm" in df.columns:
    df["resultdttm"] = pd.to_datetime(
        df["resultdttm"], errors="coerce", utc=True
    ).dt.tz_localize(None)

if "result" in df.columns:
    df["result_category"] = df["result"].apply(categorize_result)
else:
    df["result_category"] = "Other"

if "resultdttm" in df.columns and df["resultdttm"].notna().any():
    min_date = df["resultdttm"].min().date()
    max_date = df["resultdttm"].max().date()
else:
    min_date, max_date = date(2000, 1, 1), date.today()

zips = sorted(df["_zip_clean"].dropna().unique()) if "_zip_clean" in df else []


# ---------- Sidebar (Search filters) ----------
with st.sidebar:
    st.header("🔍 Search Filters")
    st.caption("These filters apply to the **Search** tab only.")

    if st.button("🔄 Reset all filters", use_container_width=True):
        for k in list(st.session_state.keys()):
            if k.startswith("filter_"):
                del st.session_state[k]
        st.rerun()

    name_q = st.text_input(
        "Restaurant name or keyword",
        placeholder="e.g. pizza hut, dunkin, mcdonald",
        key="filter_name",
        help="Searches across name, DBA, owner, address and ZIP.",
    )

    sel_zips = st.multiselect(
        "ZIP code", zips, default=[], key="filter_zips",
        placeholder="All ZIP codes",
    )

    st.markdown("**Inspection result**")
    sel_categories = st.multiselect(
        "Category", ["Pass", "Fail"], default=[], key="filter_categories",
        placeholder="All results", label_visibility="collapsed",
    )

    st.markdown("**Inspection date range**")
    preset = st.radio(
        "Period",
        ["All time", "Last week", "Last 15 days", "Last 30 days", "Last year", "Custom"],
        index=0, key="filter_date_preset", label_visibility="collapsed",
    )

    date_from = date_to = None
    if preset == "All time":
        date_from, date_to = min_date, max_date
    elif preset == "Last week":
        date_from, date_to = max_date - timedelta(days=7), max_date
    elif preset == "Last 15 days":
        date_from, date_to = max_date - timedelta(days=15), max_date
    elif preset == "Last 30 days":
        date_from, date_to = max_date - timedelta(days=30), max_date
    elif preset == "Last year":
        date_from, date_to = max_date - timedelta(days=365), max_date
    else:
        c1, c2 = st.columns(2)
        with c1:
            date_from = st.date_input("From", value=min_date,
                                       min_value=min_date, max_value=max_date)
        with c2:
            date_to = st.date_input("To", value=max_date,
                                     min_value=min_date, max_value=max_date)

    st.caption(f"Data spans {min_date} → {max_date}")


# ---------- Filtering (Search tab) ----------
filtered_df = df.copy()

if name_q.strip() and "_search_blob" in filtered_df.columns:
    tokens = [t for t in name_q.strip().lower().split() if t]
    mask = pd.Series(True, index=filtered_df.index)
    for token in tokens:
        mask &= filtered_df["_search_blob"].str.contains(token, regex=False, na=False)
    filtered_df = filtered_df[mask]

if sel_zips and "_zip_clean" in filtered_df.columns:
    filtered_df = filtered_df[filtered_df["_zip_clean"].isin(sel_zips)]

if sel_categories and "result_category" in filtered_df.columns:
    filtered_df = filtered_df[filtered_df["result_category"].isin(sel_categories)]

if date_from and "resultdttm" in filtered_df.columns:
    filtered_df = filtered_df[filtered_df["resultdttm"] >= pd.Timestamp(date_from)]
if date_to and "resultdttm" in filtered_df.columns:
    filtered_df = filtered_df[
        filtered_df["resultdttm"] <= pd.Timestamp(date_to) + pd.Timedelta(days=1)
    ]


# ---------- Tabs ----------
tab_search, tab_map = st.tabs(["🔍 Search", "🗺️ Map View"])


# ============ TAB 1 — SEARCH ============
with tab_search:
    pass_n = (filtered_df["result_category"] == "Pass").sum()
    fail_n = (filtered_df["result_category"] == "Fail").sum()
    rate = (pass_n / len(filtered_df) * 100) if len(filtered_df) else 0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total in dataset", f"{total_api:,}")
    c2.metric("After filters", f"{len(filtered_df):,}")
    c3.metric("Pass rate", f"{rate:.1f}%")
    c4.metric("Fail count", f"{fail_n:,}")

    st.divider()

    if len(filtered_df) == 0:
        st.warning("⚠️ No records match the current filters. Try broadening your search.")
    else:
        search_active = bool(name_q.strip())
        display_cols = [
            c for c in [
                "businessname", "address", "city", "zip",
                "result", "resultdttm", "viol_level", "violdesc", "comments",
            ] if c in filtered_df.columns
        ]

        if search_active:
            st.subheader(f"🏪 Restaurant summary — {len(filtered_df):,} inspections found")

            sorted_df = filtered_df.sort_values("resultdttm", ascending=False, na_position="last")
            grouped = (
                sorted_df.groupby(["_display_name", "address"], dropna=False)
                .size()
                .reset_index(name="inspections")
                .sort_values("inspections", ascending=False)
                .head(50)
            )

            for _, grow in grouped.iterrows():
                rest_df = sorted_df[
                    (sorted_df["_display_name"] == grow["_display_name"]) &
                    (sorted_df["address"].astype(str) == str(grow["address"]))
                ]
                render_restaurant_card(rest_df, grow["_display_name"], grow["address"])

            with st.expander("📋 Show detailed records table", expanded=False):
                view = filtered_df[display_cols].copy()
                if "resultdttm" in view.columns:
                    view = view.sort_values("resultdttm", ascending=False)
                st.dataframe(view, use_container_width=True, height=420)

            st.download_button(
                "📥 Download all matching records (CSV)",
                data=filtered_df[display_cols].to_csv(index=False).encode("utf-8"),
                file_name="boston_inspections.csv",
                mime="text/csv",
            )
        else:
            left, right = st.columns([2, 1])

            with left:
                st.subheader("📋 Inspection results")
                view = filtered_df[display_cols].copy()
                if "resultdttm" in view.columns:
                    view = view.sort_values("resultdttm", ascending=False)

                MAX_ROWS = 5000
                if len(view) > MAX_ROWS:
                    st.caption(
                        f"Showing first {MAX_ROWS:,} of {len(view):,} rows. "
                        f"Use filters to narrow down — full set available in the CSV export."
                    )
                    view = view.head(MAX_ROWS)

                st.dataframe(view, use_container_width=True, height=520)

                st.download_button(
                    "📥 Download full filtered results (CSV)",
                    data=filtered_df[display_cols].to_csv(index=False).encode("utf-8"),
                    file_name="boston_inspections.csv",
                    mime="text/csv",
                )

            with right:
                st.subheader("📊 Summary")
                if "result_category" in filtered_df.columns:
                    st.markdown("**By category**")
                    cat_counts = (
                        filtered_df["result_category"]
                        .value_counts()
                        .reindex(["Pass", "Fail", "Other"], fill_value=0)
                    )
                    cat_counts = cat_counts[cat_counts > 0]
                    if len(cat_counts) > 0:
                        render_hbar_chart(cat_counts, color="#3b82f6")

                if "_zip_clean" in filtered_df.columns:
                    st.markdown("**Top 10 ZIP codes**")
                    top_zips = filtered_df["_zip_clean"].dropna().value_counts().head(10)
                    if len(top_zips) > 0:
                        render_hbar_chart(top_zips, color="#8b5cf6")


# ============ TAB 2 — MAP VIEW ============
with tab_map:
    st.markdown("### 🗺️ Map View — Guided Exploration")
    st.caption("Follow the 3 steps below to explore restaurants visually on the map.")

    # ---------- STEP 1 ----------
    st.markdown("---")
    st.markdown("### Step 1️⃣ — Choose a date range")
    st.markdown(
        '<div class="step-box">Pick the inspection period you want to see on the map. '
        'The narrower the range, the fewer the points.</div>',
        unsafe_allow_html=True,
    )

    map_preset = st.radio(
        "Map period",
        ["Last week", "Last 15 days", "Last 30 days", "Last year", "All time", "Custom"],
        index=2,
        horizontal=True,
        key="map_preset",
        label_visibility="collapsed",
    )

    if map_preset == "Last week":
        map_from, map_to = max_date - timedelta(days=7), max_date
    elif map_preset == "Last 15 days":
        map_from, map_to = max_date - timedelta(days=15), max_date
    elif map_preset == "Last 30 days":
        map_from, map_to = max_date - timedelta(days=30), max_date
    elif map_preset == "Last year":
        map_from, map_to = max_date - timedelta(days=365), max_date
    elif map_preset == "All time":
        map_from, map_to = min_date, max_date
    else:  # Custom
        mc1, mc2 = st.columns(2)
        with mc1:
            map_from = st.date_input(
                "From", value=max_date - timedelta(days=30),
                min_value=min_date, max_value=max_date,
                key="map_from",
            )
        with mc2:
            map_to = st.date_input(
                "To", value=max_date,
                min_value=min_date, max_value=max_date,
                key="map_to",
            )

    # Filter by date range for map
    map_base = df.copy()
    if map_from and "resultdttm" in map_base.columns:
        map_base = map_base[map_base["resultdttm"] >= pd.Timestamp(map_from)]
    if map_to and "resultdttm" in map_base.columns:
        map_base = map_base[
            map_base["resultdttm"] <= pd.Timestamp(map_to) + pd.Timedelta(days=1)
        ]

    # Keep only rows with valid coordinates
    map_df = map_base.dropna(subset=["lat", "lon"]).copy()
    map_df = map_df[
        (map_df["lat"].between(-90, 90)) & (map_df["lon"].between(-180, 180))
    ]

    st.success(
        f"✅ Period: **{map_from} → {map_to}** · "
        f"{len(map_base):,} inspections · {len(map_df):,} with coordinates"
    )

    # ---------- STEP 2 ----------
    st.markdown("---")
    st.markdown("### Step 2️⃣ — Explore the map")

    if len(map_df) == 0:
        st.warning("⚠️ No geolocated records in this date range. Try a wider period.")
    else:
        st.markdown(
            '<div class="step-box">Each dot is one inspection. '
            'Zoom and pan to explore. Then move to Step 3 to inspect a specific restaurant.</div>',
            unsafe_allow_html=True,
        )

        # Optional: limit for performance
        MAX_MAP_POINTS = 15000
        map_plot = map_df
        if len(map_df) > MAX_MAP_POINTS:
            st.caption(
                f"⚠️ Showing a random sample of {MAX_MAP_POINTS:,} points "
                f"out of {len(map_df):,} for performance."
            )
            map_plot = map_df.sample(MAX_MAP_POINTS, random_state=42)

        st.map(
            map_plot[["lat", "lon"]],
            latitude="lat",
            longitude="lon",
            zoom=11,
            use_container_width=True,
        )

        # ---------- STEP 3 ----------
        st.markdown("---")
        st.markdown("### Step 3️⃣ — Pick a restaurant to see its report card")

        grouped_map = (
            map_df.groupby(["_display_name", "address"], dropna=False)
            .size()
            .reset_index(name="n")
            .sort_values(["n", "_display_name"], ascending=[False, True])
        )

        # Build unique labels for the dropdown
        labels = []
        for _, r in grouped_map.iterrows():
            name = str(r["_display_name"])
            addr = str(r["address"]) if pd.notna(r["address"]) else "—"
            labels.append(f"{name}  ·  {addr}")

        selected_label = st.selectbox(
            f"Choose a restaurant ({len(labels):,} available in this period)",
            options=labels,
            index=0,
            key="map_select_restaurant",
        )

        if selected_label:
            idx = labels.index(selected_label)
            sel = grouped_map.iloc[idx]
            rest_df = map_df[
                (map_df["_display_name"] == sel["_display_name"]) &
                (map_df["address"].astype(str) == str(sel["address"]))
            ]
            render_restaurant_card(rest_df, sel["_display_name"], sel["address"])


# ---------- Footer ----------
st.markdown(
    """
    <div class="footer">
        <b>Boston Food Inspections Dashboard</b> — Pilot Project · MIT License<br>
        🔗 <a href="https://github.com/renatoerss">github.com/renatoerss</a>
    </div>
    """,
    unsafe_allow_html=True,
)
