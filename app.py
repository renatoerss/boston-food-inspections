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


# ---------- Styling ----------
st.markdown(
    """
    <style>
        h1 {color: #1e3a8a;}
        .disclaimer {
            background: #fff7ed;
            border-left: 5px solid #f97316;
            padding: 12px;
            border-radius: 8px;
            color: #7c2d12;
            font-size: 0.88rem;
        }
        .footer {
            margin-top: 40px;
            padding: 14px;
            background: #f1f5f9;
            border-radius: 8px;
            text-align: center;
            color: #475569;
            font-size: 0.85rem;
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
    return pd.DataFrame(all_records), total


def categorize_result(value):
    """Map raw result values to Pass / Fail / Other."""
    if pd.isna(value):
        return "Unknown"
    v = str(value).lower()
    if "pass" in v:
        return "Pass"
    if "fail" in v:
        return "Fail"
    return "Other"


with st.spinner("Loading all records from Boston Open Data (first run ~15–25 s)..."):
    try:
        df, total_api = load_all_data()
    except Exception as e:
        st.error(f"Error contacting the API: {e}")
        st.stop()

# Parse dates
if "resultdttm" in df.columns:
    df["resultdttm"] = pd.to_datetime(
        df["resultdttm"], errors="coerce", utc=True
    ).dt.tz_localize(None)

# Simplified result category
if "result" in df.columns:
    df["result_category"] = df["result"].apply(categorize_result)
else:
    df["result_category"] = "Unknown"

# Date bounds
if "resultdttm" in df.columns and df["resultdttm"].notna().any():
    min_date = df["resultdttm"].min().date()
    max_date = df["resultdttm"].max().date()
else:
    min_date, max_date = date(2000, 1, 1), date.today()

# Unique neighborhoods
cities = sorted(df["city"].dropna().unique()) if "city" in df else []


# ---------- Sidebar ----------
with st.sidebar:
    st.header("🔍 Filters")

    if st.button("🔄 Reset all filters", use_container_width=True):
        for k in list(st.session_state.keys()):
            if k.startswith("filter_"):
                del st.session_state[k]
        st.rerun()

    # --- Restaurant search ---
    name_q = st.text_input(
        "Restaurant name contains",
        placeholder="e.g. pizza hut, dunkin",
        key="filter_name",
        help="Searches for all words. 'pizza hut' finds 'Pizza Hut #1234'.",
    )

    # --- Neighborhood ---
    sel_cities = st.multiselect(
        "Neighborhood",
        cities,
        default=[],
        key="filter_cities",
        placeholder="All neighborhoods",
    )

    # --- Result category ---
    st.markdown("**Inspection result**")
    sel_categories = st.multiselect(
        "Category",
        ["Pass", "Fail", "Other"],
        default=[],
        key="filter_categories",
        placeholder="All results",
        label_visibility="collapsed",
    )

    show_exact = st.checkbox(
        "Show exact result values",
        value=False,
        key="filter_exact_toggle",
    )
    sel_exact = []
    if show_exact and "result" in df.columns:
        exact_values = sorted(df["result"].dropna().unique())
        sel_exact = st.multiselect(
            "Exact value",
            exact_values,
            default=[],
            key="filter_exact_values",
        )

    # --- Date range with presets ---
    st.markdown("**Inspection date range**")
    preset = st.radio(
        "Period",
        ["All time", "Last 30 days", "Last 6 months", "Last year", "Custom"],
        index=0,
        key="filter_date_preset",
        label_visibility="collapsed",
    )

    date_from = date_to = None

    if preset == "All time":
        date_from, date_to = min_date, max_date
    elif preset == "Last 30 days":
        date_from, date_to = max_date - timedelta(days=30), max_date
    elif preset == "Last 6 months":
        date_from, date_to = max_date - timedelta(days=180), max_date
    elif preset == "Last year":
        date_from, date_to = max_date - timedelta(days=365), max_date
    else:  # Custom
        c1, c2 = st.columns(2)
        with c1:
            date_from = st.date_input(
                "From", value=min_date, min_value=min_date, max_value=max_date
            )
        with c2:
            date_to = st.date_input(
                "To", value=max_date, min_value=min_date, max_value=max_date
            )

    st.caption(f"Data spans {min_date} → {max_date}")


# ---------- Filtering ----------
filtered_df = df.copy()

# Search: match ALL words (case-insensitive, regex-safe)
if name_q.strip() and "businessname" in filtered_df.columns:
    tokens = [t for t in name_q.strip().lower().split() if t]
    for token in tokens:
        filtered_df = filtered_df[
            filtered_df["businessname"]
            .astype(str)
            .str.lower()
            .str.contains(token, regex=False, na=False)
        ]

if sel_cities and "city" in filtered_df.columns:
    filtered_df = filtered_df[filtered_df["city"].isin(sel_cities)]

if sel_categories and "result_category" in filtered_df.columns:
    filtered_df = filtered_df[filtered_df["result_category"].isin(sel_categories)]

if sel_exact and "result" in filtered_df.columns:
    filtered_df = filtered_df[filtered_df["result"].isin(sel_exact)]

if date_from and "resultdttm" in filtered_df.columns:
    filtered_df = filtered_df[filtered_df["resultdttm"] >= pd.Timestamp(date_from)]
if date_to and "resultdttm" in filtered_df.columns:
    filtered_df = filtered_df[
        filtered_df["resultdttm"] <= pd.Timestamp(date_to) + pd.Timedelta(days=1)
    ]


# ---------- KPIs ----------
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
    st.stop()


# ---------- Results ----------
left, right = st.columns([2, 1])

with left:
    st.subheader("📋 Inspection results")
    display_cols = [
        c
        for c in [
            "businessname",
            "address",
            "city",
            "zip",
            "result",
            "resultdttm",
            "viol_level",
            "violdesc",
            "comments",
        ]
        if c in filtered_df.columns
    ]

    view = filtered_df[display_cols].copy()
    if "resultdttm" in view.columns:
        view = view.sort_values("resultdttm", ascending=False)

    MAX_ROWS = 5000
    if len(view) > MAX_ROWS:
        st.caption(
            f"Showing first {MAX_ROWS:,} of {len(view):,} rows "
            f"(use filters to narrow down). Full set available in the CSV export."
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
            st.bar_chart(cat_counts, height=220)

    if "city" in filtered_df.columns:
        st.markdown("**Top 10 neighborhoods**")
        top_cities = filtered_df["city"].dropna().value_counts().head(10)
        if len(top_cities) > 0:
            st.bar_chart(top_cities, height=280)


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
