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
# Load data (HARDENED VERSION)
# -----------------------------
@st.cache_data(ttl=60)
def load_data():
    # ---------- LOAD SUMMARY ----------
    try:
        df = pd.read_csv(
            SUMMARY_URL,
            dtype=str,
            on_bad_lines="skip",
            encoding="utf-8"
        )
    except Exception as e:
        st.error(f"Failed to load Summary sheet: {e}")
        return pd.DataFrame()

    # Keep only first 4 columns
    df = df.iloc[:, :4]
    df.columns = ["Date", "Title", "Type", "Amount"]

    # Clean text fields
    df["Title"] = df["Title"].astype(str).str.strip()
    df["Type"] = df["Type"].astype(str).str.strip()

    # Convert amount safely
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    df = df.dropna(subset=["Amount"])

    # Parse dates safely
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])

    df["Month"] = df["Date"].dt.month_name()

    # ---------- LOAD MAPPING ----------
    try:
        mapping = pd.read_csv(
            MAPPING_URL,
            dtype=str,
            on_bad_lines="skip",
            encoding="utf-8"
        )

        mapping = mapping.iloc[:, :2]
        mapping.columns = ["Title", "Category"]

        mapping["Title"] = mapping["Title"].str.strip()
        mapping["Category"] = mapping["Category"].str.strip()

        mapping_dict = dict(zip(mapping["Title"], mapping["Category"]))
        df["Category"] = df["Title"].map(mapping_dict).fillna("Uncategorized")

    except Exception:
        st.warning("⚠️ Mapping sheet failed to load — defaulting to 'Uncategorized'")
        df["Category"] = "Uncategorized"

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
# Exclusions for spending charts
# -----------------------------
EXCLUDE_KEYWORDS = [
    "total",
    "non-investment",
    "jacob income",
    "zoe income",
    "interest"
]

def exclude_rows(df):
    return df[
        ~df["Title"].str.lower().str.contains("|".join(EXCLUDE_KEYWORDS), na=False)
    ]

df_spending = exclude_rows(df_filtered)

if include_income:
    df_spending = df_filtered

# -----------------------------
# SUMMARY CHART
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

fig_summary.update_layout(template="plotly_white")
st.plotly_chart(fig_summary, use_container_width=True)

# -----------------------------
# Monthly Spending Trend
# -----------------------------
st.subheader("📈 Monthly Spending Trend (Actual)")

monthly_trend = (
    df_spending[df_spending["Type"] == "Actual"]
    .groupby("Month", as_index=False)["Amount"]
    .sum()
    .sort_values("Month")
)

fig_trend = px.line(
    monthly_trend,
    x="Month",
    y="Amount",
    markers=True,
    title="Total Actual Spending by Month"
)

fig_trend.update_layout(template="plotly_white")
st.plotly_chart(fig_trend, use_container_width=True)

# -----------------------------
# Over / Under Budget
# -----------------------------
st.subheader("💸 Over / Under Budget")

variance_df = (
    summary_df
    .pivot(index="Category", columns="Type", values="Amount")
    .fillna(0)
)

variance_df["Actual"] = variance_df.get("Actual", 0)
variance_df["Expected"] = variance_df.get("Expected", 0)
variance_df["Variance"] = variance_df["Actual"] - variance_df["Expected"]
variance_df = variance_df.reset_index()

fig_variance = px.bar(
    variance_df,
    x="Category",
    y="Variance",
    color="Variance",
    title="Over / Under Budget"
)

fig_variance.update_layout(template="plotly_white")
st.plotly_chart(fig_variance, use_container_width=True)

# -----------------------------
# Top 10 Spending Categories
# -----------------------------
st.subheader("🏆 Top 10 Spending Categories")

df_top10_base = df_spending[
    ~df_spending["Category"].str.lower().str.contains("mortgage", na=False)
]

top10 = (
    df_top10_base[df_top10_base["Type"] == "Actual"]
    .groupby("Title", as_index=False)["Amount"]
    .sum()
    .sort_values("Amount", ascending=False)
    .head(10)
)

fig_top10 = px.bar(
    top10,
    x="Amount",
    y="Title",
    orientation="h",
    title="Top 10 Spending Categories"
)

fig_top10.update_layout(template="plotly_white", yaxis=dict(autorange="reversed"))
st.plotly_chart(fig_top10, use_container_width=True)

# -----------------------------
# Monthly Trend for Top 10
# -----------------------------
st.subheader("📊 Monthly Trend — Top 10 Categories")

top10_titles = top10["Title"].tolist()

monthly_top10 = (
    df_top10_base[
        (df_top10_base["Type"] == "Actual") &
        (df_top10_base["Title"].isin(top10_titles))
    ]
    .groupby(["Month", "Title"], as_index=False)["Amount"]
    .sum()
    .sort_values(["Title", "Month"])
)

fig_monthly_top10 = px.bar(
    monthly_top10,
    x="Month",
    y="Amount",
    color="Title",
    facet_col="Title",
    facet_col_wrap=2,
    title="Monthly Spending for Top Categories"
)

fig_monthly_top10.update_layout(template="plotly_white", height=1000)
st.plotly_chart(fig_monthly_top10, use_container_width=True)

# -----------------------------
# Key Metrics
# -----------------------------
st.subheader("📊 Key Metrics")

actual_total = df_spending[df_spending["Type"] == "Actual"]["Amount"].sum()
expected_total = df_spending[df_spending["Type"] == "Expected"]["Amount"].sum()
variance_total = actual_total - expected_total

col1, col2, col3 = st.columns(3)
col1.metric("Actual Spending", f"${actual_total:,.0f}")
col2.metric("Expected Spending", f"${expected_total:,.0f}")
col3.metric("Over / Under", f"${variance_total:,.0f}")

# -----------------------------
# Raw Data
# -----------------------------
with st.expander("Show Raw Data"):
    st.dataframe(df_filtered, use_container_width=True)
