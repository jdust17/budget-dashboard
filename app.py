import pandas as pd
import streamlit as st
import plotly.express as px

# -----------------------------
# Page setup
# -----------------------------
st.set_page_config(page_title="Personal Finance Dashboard", layout="wide")
st.title("💰 Personal Finance Dashboard")

# -----------------------------
# Google Sheets URLs
# -----------------------------
SUMMARY_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSk2lX_RGYx7SCR7nsZPJWoUgybCQEThXTeot_1o5ee7FdJPaDCbl6cu-FbR4iNOvtF7ftslAAYNXK8/pub?gid=1013390825&single=true&output=csv"
MAPPING_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSk2lX_RGYx7SCR7nsZPJWoUgybCQEThXTeot_1o5ee7FdJPaDCbl6cu-FbR4iNOvtF7ftslAAYNXK8/pub?gid=1543886282&single=true&output=csv"

# -----------------------------
# Required categories
# -----------------------------
ALL_CATEGORIES = [
    "Income","Tithes","Mortgage","Long Term","Household","Subscription",
    "Insurance","Utilities","Transportation","Food","Housing","Misc","Kids",
    "Uncategorized"
]

# -----------------------------
# Safe CSV loader
# -----------------------------
def safe_read_csv(url, name):
    try:
        df = pd.read_csv(
            url,
            on_bad_lines="skip",   # skip malformed rows
            engine="python"        # more tolerant parser
        )
        return df
    except Exception as e:
        st.warning(f"⚠️ Could not load {name}. App will continue without it.")
        st.exception(e)
        return pd.DataFrame()

# -----------------------------
# Load data with refresh
# -----------------------------
@st.cache_data(ttl=60)
def load_data():
    # Load summary data
    df = safe_read_csv(SUMMARY_URL, "Summary Sheet")

    if df.empty:
        st.error("Summary sheet failed to load.")
        st.stop()

    # Auto-detect columns
    df.columns = [c.strip() for c in df.columns]

    # Try to standardize expected columns
    column_map = {}
    for col in df.columns:
        lc = col.lower()
        if "date" in lc:
            column_map[col] = "Date"
        elif "title" in lc or "description" in lc:
            column_map[col] = "Title"
        elif "type" in lc:
            column_map[col] = "Type"
        elif "amount" in lc:
            column_map[col] = "Amount"

    df = df.rename(columns=column_map)

    required_cols = ["Date", "Title", "Type", "Amount"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        st.error(f"Missing required columns: {missing}")
        st.stop()

    # Clean summary data
    df["Title"] = df["Title"].astype(str).str.strip()
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    df = df.dropna(subset=["Amount", "Date"])

    # -----------------------------
    # Load mapping safely
    # -----------------------------
    mapping = safe_read_csv(MAPPING_URL, "Mapping Sheet")

    if not mapping.empty:
        mapping.columns = [c.strip() for c in mapping.columns]

        # auto-detect mapping columns
        mapping_map = {}
        for col in mapping.columns:
            lc = col.lower()
            if "title" in lc:
                mapping_map[col] = "Title"
            elif "category" in lc:
                mapping_map[col] = "Category"

        mapping = mapping.rename(columns=mapping_map)

        if "Title" in mapping.columns and "Category" in mapping.columns:
            mapping["Title"] = mapping["Title"].astype(str).str.strip()
            mapping["Category"] = mapping["Category"].astype(str).str.strip()

            df = df.merge(mapping, on="Title", how="left")
        else:
            st.warning("Mapping sheet missing required columns.")
            df["Category"] = None
    else:
        df["Category"] = None

    # Fill missing categories
    df["Category"] = df["Category"].fillna("Uncategorized")

    # Enforce allowed categories
    df.loc[~df["Category"].isin(ALL_CATEGORIES), "Category"] = "Uncategorized"

    # Month column
    df["Month"] = df["Date"].dt.month_name()

    return df

# Manual refresh
if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()

df = load_data()

# -----------------------------
# Month ordering
# -----------------------------
MONTH_ORDER = [
    "January","February","March","April","May","June",
    "July","August","September","October","November","December"
]
df["Month"] = pd.Categorical(df["Month"], categories=MONTH_ORDER, ordered=True)

# -----------------------------
# Sidebar filters
# -----------------------------
st.sidebar.header("Filters")

selected_months = st.sidebar.multiselect(
    "Select Month(s)",
    options=MONTH_ORDER,
    default=MONTH_ORDER
)

include_income = st.sidebar.toggle("Include Income in Charts", value=False)

df_filtered = df[df["Month"].isin(selected_months)]

# -----------------------------
# Exclusions
# -----------------------------
EXCLUDE_KEYWORDS = ["total","non-investment","interest"]

def exclude_rows(df):
    return df[
        ~df["Title"].str.lower().str.contains("|".join(EXCLUDE_KEYWORDS), na=False)
    ]

df_spending = exclude_rows(df_filtered)
if include_income:
    df_spending = df_filtered

# -----------------------------
# Expected vs Actual
# -----------------------------
summary_df = (
    df_spending
    .groupby(["Category", "Type"], as_index=False)["Amount"]
    .sum()
)

fig_summary = px.bar(
    summary_df,
    x="Category",
    y="Amount",
    color="Type",
    barmode="group",
    title="Expected vs Actual by Category"
)
st.plotly_chart(fig_summary, width="stretch")

# -----------------------------
# Monthly Trend
# -----------------------------
st.subheader("📈 Monthly Spending Trend (Actual)")

monthly_trend = (
    df_spending[df_spending["Type"] == "Actual"]
    .groupby("Month", as_index=False)["Amount"]
    .sum()
    .sort_values("Month")
)

fig_trend = px.line(monthly_trend, x="Month", y="Amount", markers=True)
st.plotly_chart(fig_trend, width="stretch")

# -----------------------------
# Over / Under Budget
# -----------------------------
st.subheader("💸 Over / Under Budget")

variance_df = (
    summary_df
    .pivot(index="Category", columns="Type", values="Amount")
    .fillna(0)
)

variance_df["Variance"] = variance_df.get("Actual", 0) - variance_df.get("Expected", 0)
variance_df = variance_df.reset_index()

fig_variance = px.bar(variance_df, x="Category", y="Variance", color="Variance")
st.plotly_chart(fig_variance, width="stretch")

# -----------------------------
# Top 10
# -----------------------------
st.subheader("🏆 Top 10 Spending Categories")

top10 = (
    df_spending[df_spending["Type"] == "Actual"]
    .groupby("Title", as_index=False)["Amount"]
    .sum()
    .sort_values("Amount", ascending=False)
    .head(10)
)

fig_top10 = px.bar(top10, x="Amount", y="Title", orientation="h")
fig_top10.update_layout(yaxis=dict(autorange="reversed"))
st.plotly_chart(fig_top10, width="stretch")

# -----------------------------
# Metrics
# -----------------------------
st.subheader("📊 Key Metrics")

actual_total = df_spending[df_spending["Type"] == "Actual"]["Amount"].sum()
expected_total = df_spending[df_spending["Type"] == "Expected"]["Amount"].sum()
variance_total = actual_total - expected_total

col1, col2, col3 = st.columns(3)
col1.metric("Actual", f"${actual_total:,.0f}")
col2.metric("Expected", f"${expected_total:,.0f}")
col3.metric("Variance", f"${variance_total:,.0f}")

# -----------------------------
# Raw Data
# -----------------------------
with st.expander("Show Raw Data"):
    st.dataframe(df_filtered, width="stretch")
