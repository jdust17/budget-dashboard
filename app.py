import pandas as pd
import streamlit as st
import plotly.express as px

# -----------------------------
# CONFIG — REPLACE WITH YOUR URLS
# -----------------------------
TRANSACTIONS_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSk2lX_RGYx7SCR7nsZPJWoUgybCQEThXTeot_1o5ee7FdJPaDCbl6cu-FbR4iNOvtF7ftslAAYNXK8/pub?gid=1013390825&single=true&output=csv"
MAPPING_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSk2lX_RGYx7SCR7nsZPJWoUgybCQEThXTeot_1o5ee7FdJPaDCbl6cu-FbR4iNOvtF7ftslAAYNXK8/pub?gid=1543886282&single=true&output=csv"

# -----------------------------
# Page setup
# -----------------------------
st.set_page_config(page_title="Personal Finance Dashboard", layout="wide")
st.title("💰 Personal Finance Dashboard")

# -----------------------------
# SAFE CSV READER
# -----------------------------
def safe_read_csv(url, expected_cols=None):
    try:
        df = pd.read_csv(url, skip_blank_lines=True, engine="python")

        # Remove completely empty rows
        df = df.dropna(how="all")

        # Trim whitespace from headers
        df.columns = df.columns.str.strip()

        # Keep only expected columns if provided
        if expected_cols:
            df = df.iloc[:, :len(expected_cols)]
            df.columns = expected_cols

        return df

    except Exception as e:
        st.error(f"❌ Failed to load data from URL:\n{url}")
        st.exception(e)
        st.stop()

# -----------------------------
# LOAD DATA
# -----------------------------
@st.cache_data(ttl=60)
def load_data():

    # -------- Transactions --------
    df = safe_read_csv(
        TRANSACTIONS_URL,
        expected_cols=["Month", "Category", "Type", "Amount"]
    )

    # Clean data
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    df = df.dropna(subset=["Amount"])

    # Normalize text fields
    df["Category"] = df["Category"].astype(str).str.strip()
    df["Type"] = df["Type"].astype(str).str.strip()

    # ---- Robust date handling ----
    df["Month"] = pd.to_datetime(df["Month"], errors="coerce")

    # Drop bad dates
    df = df.dropna(subset=["Month"])

    # Extract month name for charts
    df["MonthName"] = df["Month"].dt.strftime("%B")

    # -------- Mapping --------
    try:
        mapping = safe_read_csv(
            MAPPING_URL,
            expected_cols=["Title", "CategoryGroup"]
        )

        mapping["Title"] = mapping["Title"].astype(str).str.strip()
        mapping["CategoryGroup"] = mapping["CategoryGroup"].astype(str).str.strip()

        mapping_dict = dict(zip(mapping["Title"], mapping["CategoryGroup"]))

    except:
        mapping_dict = {}
        st.warning("⚠️ Mapping sheet could not be loaded. All items set to 'Uncategorized'.")

    # Apply mapping
    df["CategoryGroup"] = df["Category"].map(mapping_dict)

    # Keep uncategorized visible
    df["CategoryGroup"] = df["CategoryGroup"].fillna("Uncategorized")

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

df["MonthName"] = pd.Categorical(df["MonthName"], categories=MONTH_ORDER, ordered=True)

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

df_filtered = df[df["MonthName"].isin(selected_months)]

# -----------------------------
# Exclusion rules (optional)
# -----------------------------
EXCLUDE_KEYWORDS = ["total", "non-investment"]

def exclude_rows(df):
    return df[
        ~df["Category"].str.lower().str.contains("|".join(EXCLUDE_KEYWORDS), na=False)
    ]

df_spending = exclude_rows(df_filtered)

if include_income:
    df_spending = df_filtered

# -----------------------------
# SUMMARY CHART
# -----------------------------
summary_df = (
    df_spending
    .groupby(["CategoryGroup", "Type"], as_index=False)["Amount"]
    .sum()
)

fig_summary = px.bar(
    summary_df,
    x="CategoryGroup",
    y="Amount",
    color="Type",
    barmode="group",
    title="Expected vs Actual by Category Group"
)

fig_summary.update_layout(template="plotly_white")
st.plotly_chart(fig_summary, use_container_width=True)

# -----------------------------
# Monthly Spending Trend
# -----------------------------
st.subheader("📈 Monthly Spending Trend (Actual)")

monthly_trend = (
    df_spending[df_spending["Type"] == "Actual"]
    .groupby("MonthName", as_index=False)["Amount"]
    .sum()
    .sort_values("MonthName")
)

fig_trend = px.line(
    monthly_trend,
    x="MonthName",
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
    .pivot(index="CategoryGroup", columns="Type", values="Amount")
    .fillna(0)
)

variance_df["Actual"] = variance_df.get("Actual", 0)
variance_df["Expected"] = variance_df.get("Expected", 0)
variance_df["Variance"] = variance_df["Actual"] - variance_df["Expected"]
variance_df = variance_df.reset_index()

fig_variance = px.bar(
    variance_df,
    x="CategoryGroup",
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

df_top10_base = df_spending

top10 = (
    df_top10_base[df_top10_base["Type"] == "Actual"]
    .groupby("Category", as_index=False)["Amount"]
    .sum()
    .sort_values("Amount", ascending=False)
    .head(10)
)

fig_top10 = px.bar(
    top10,
    x="Amount",
    y="Category",
    orientation="h",
    title="Top 10 Spending Categories"
)

fig_top10.update_layout(template="plotly_white", yaxis=dict(autorange="reversed"))
st.plotly_chart(fig_top10, use_container_width=True)

# -----------------------------
# Monthly Trend — Top 10
# -----------------------------
st.subheader("📊 Monthly Trend — Top 10 Categories")

top10_categories = top10["Category"].tolist()

monthly_top10 = (
    df_top10_base[
        (df_top10_base["Type"] == "Actual") &
        (df_top10_base["Category"].isin(top10_categories))
    ]
    .groupby(["MonthName", "Category"], as_index=False)["Amount"]
    .sum()
    .sort_values(["Category", "MonthName"])
)

fig_monthly_top10 = px.bar(
    monthly_top10,
    x="MonthName",
    y="Amount",
    color="Category",
    facet_col="Category",
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
# Raw Data + Debug
# -----------------------------
with st.expander("🔍 Show Raw Data"):
    st.dataframe(df_filtered, use_container_width=True)

with st.expander("🛠 Debug Info"):
    st.write("Rows Loaded:", len(df))
    st.write("Unique Categories:", df["Category"].nunique())
    st.write("Uncategorized Rows:", (df["CategoryGroup"] == "Uncategorized").sum())
