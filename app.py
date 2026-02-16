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
# Safe CSV loader
# -----------------------------
def safe_read_csv(url):
    try:
        return pd.read_csv(url, engine="python")
    except Exception:
        return pd.read_csv(url, engine="python", on_bad_lines="skip")

# -----------------------------
# Load data
# -----------------------------
@st.cache_data(ttl=60)
def load_data():
    df = safe_read_csv(SUMMARY_URL)
    mapping = safe_read_csv(MAPPING_URL)

    # Standardize headers
    df.columns = [c.strip() for c in df.columns]
    mapping.columns = [c.strip() for c in mapping.columns]

    required_cols = {"Date", "Title", "Type", "Amount"}
    if not required_cols.issubset(df.columns):
        st.error(f"Missing required columns: {required_cols - set(df.columns)}")
        st.stop()

    # Clean text
    df["Title"] = df["Title"].astype(str).str.strip()
    mapping["Title"] = mapping["Title"].astype(str).str.strip()

    # Merge mapping
    df = df.merge(mapping, on="Title", how="left")
    df["Category"] = df["Category"].fillna("Uncategorized")

    # Convert types
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
    df = df.dropna(subset=["Amount"])

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])

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
# Income detection helper
# -----------------------------
def is_income(row):
    title = str(row["Title"]).lower()
    category = str(row["Category"]).lower()
    return (
        category == "income"
        or "income" in title
        or "payroll" in title
        or "salary" in title
    )

# -----------------------------
# Spending dataset (charts only)
# -----------------------------
if include_income:
    df_spending = df_filtered.copy()
else:
    df_spending = df_filtered[~df_filtered.apply(is_income, axis=1)]

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

st.plotly_chart(fig_summary, width="stretch")

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

variance_df["Actual"] = variance_df.get("Actual", 0)
variance_df["Expected"] = variance_df.get("Expected", 0)
variance_df["Variance"] = variance_df["Actual"] - variance_df["Expected"]
variance_df = variance_df.reset_index()

fig_variance = px.bar(variance_df, x="Category", y="Variance", color="Variance")
st.plotly_chart(fig_variance, width="stretch")

# -----------------------------
# Top 10 Spending Categories (NO INCOME)
# -----------------------------
st.subheader("🏆 Top 10 Spending Categories")

top10_base = df_filtered[
    (~df_filtered.apply(is_income, axis=1)) &
    (df_filtered["Type"] == "Actual")
]

top10 = (
    top10_base
    .groupby("Title", as_index=False)["Amount"]
    .sum()
    .sort_values("Amount", ascending=False)
    .head(10)
)

fig_top10 = px.bar(top10, x="Amount", y="Title", orientation="h")
fig_top10.update_layout(yaxis=dict(autorange="reversed"))
st.plotly_chart(fig_top10, width="stretch")

# -----------------------------
# Key Metrics (NEVER EXCLUDE INCOME)
# -----------------------------
st.subheader("📊 Key Metrics")

actual_total = df_filtered[df_filtered["Type"] == "Actual"]["Amount"].sum()
expected_total = df_filtered[df_filtered["Type"] == "Expected"]["Amount"].sum()
variance_total = actual_total - expected_total

col1, col2, col3 = st.columns(3)
col1.metric("Actual Spending", f"${actual_total:,.0f}")
col2.metric("Expected Spending", f"${expected_total:,.0f}")
col3.metric("Over / Under", f"${variance_total:,.0f}")

# -----------------------------
# Raw Data
# -----------------------------
with st.expander("Show Raw Data"):
    st.dataframe(df_filtered, width="stretch")
