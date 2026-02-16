import pandas as pd
import streamlit as st
import plotly.express as px

# -----------------------------
# PAGE SETUP
# -----------------------------
st.set_page_config(page_title="Personal Finance Dashboard", layout="wide")
st.title("💰 Personal Finance Dashboard")

# -----------------------------
# GOOGLE SHEET CSV EXPORT
# -----------------------------
SUMMARY_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSk2lX_RGYx7SCR7nsZPJWoUgybCQEThXTeot_1o5ee7FdJPaDCbl6cu-FbR4iNOvtF7ftslAAYNXK8/pub?gid=1013390825&single=true&output=csv"

# -----------------------------
# SAFE CSV LOADER
# -----------------------------
def load_csv(url):
    try:
        return pd.read_csv(url, encoding="utf-8")
    except:
        return pd.read_csv(url, encoding="latin1")

# -----------------------------
# LOAD & CLEAN DATA
# -----------------------------
@st.cache_data(ttl=60)
def load_data():
    df = load_csv(SUMMARY_URL)

    # Normalize column names
    df.columns = df.columns.str.strip()

    required_cols = ["Date", "Title", "Category", "Type", "Amount"]
    missing = [c for c in required_cols if c not in df.columns]

    if missing:
        st.error(f"Missing required columns: {missing}")
        st.stop()

    # Clean text
    df["Title"] = df["Title"].astype(str).str.strip()
    df["Category"] = df["Category"].astype(str).str.strip().replace("", "Uncategorized")
    df["Type"] = df["Type"].astype(str).str.strip()

    # Clean amounts (keeps zeros)
    df["Amount"] = (
        df["Amount"]
        .astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("$", "", regex=False)
    )
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0)

    # Parse dates safely
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    # Create Month column
    df["Month"] = df["Date"].dt.month_name()

    return df

# Manual refresh
if st.sidebar.button("🔄 Refresh Data"):
    st.cache_data.clear()

df = load_data()

# -----------------------------
# MONTH ORDER
# -----------------------------
MONTH_ORDER = [
    "January","February","March","April","May","June",
    "July","August","September","October","November","December"
]

df["Month"] = pd.Categorical(df["Month"], categories=MONTH_ORDER, ordered=True)

# -----------------------------
# SIDEBAR FILTERS
# -----------------------------
st.sidebar.header("Filters")

selected_months = st.sidebar.multiselect(
    "Select Month(s)",
    options=MONTH_ORDER,
    default=MONTH_ORDER
)

df_filtered = df[df["Month"].isin(selected_months)]

# -----------------------------
# KEY METRICS (ALWAYS INCLUDE ALL INCOME)
# -----------------------------
st.subheader("📊 Key Metrics")

income_total = df_filtered[df_filtered["Category"] == "Income"]["Amount"].sum()
expense_total = df_filtered[df_filtered["Category"] != "Income"]["Amount"].sum()
net_total = income_total - expense_total

col1, col2, col3 = st.columns(3)
col1.metric("Total Income", f"${income_total:,.0f}")
col2.metric("Total Expenses", f"${expense_total:,.0f}")
col3.metric("Net", f"${net_total:,.0f}")

# -----------------------------
# EXPECTED VS ACTUAL BY CATEGORY
# -----------------------------
st.subheader("📊 Expected vs Actual by Category")

summary_df = (
    df_filtered
    .groupby(["Category", "Type"], as_index=False)["Amount"]
    .sum()
)

fig_summary = px.bar(
    summary_df,
    x="Category",
    y="Amount",
    color="Type",
    barmode="group"
)

fig_summary.update_layout(template="plotly_white")
st.plotly_chart(fig_summary, width="stretch")

# -----------------------------
# MONTHLY SPENDING TREND (ACTUAL ONLY)
# -----------------------------
st.subheader("📈 Monthly Spending Trend (Actual)")

monthly_trend = (
    df_filtered[
        (df_filtered["Type"] == "Actual") &
        (df_filtered["Category"] != "Income")
    ]
    .groupby("Month", as_index=False)["Amount"]
    .sum()
    .sort_values("Month")
)

fig_trend = px.line(
    monthly_trend,
    x="Month",
    y="Amount",
    markers=True
)

fig_trend.update_layout(template="plotly_white")
st.plotly_chart(fig_trend, width="stretch")

# -----------------------------
# TOP 10 SPENDING (NO INCOME)
# -----------------------------
st.subheader("🏆 Top 10 Spending Categories")

top10 = (
    df_filtered[
        (df_filtered["Category"] != "Income") &
        (df_filtered["Type"] == "Actual")
    ]
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
)

fig_top10.update_layout(
    template="plotly_white",
    yaxis=dict(autorange="reversed")
)

st.plotly_chart(fig_top10, width="stretch")

# -----------------------------
# OVER / UNDER BUDGET
# -----------------------------
st.subheader("💸 Over / Under Budget")

variance_df = (
    summary_df
    .pivot(index="Category", columns="Type", values="Amount")
    .fillna(0)
)

variance_df["Variance"] = variance_df.get("Actual", 0) - variance_df.get("Expected", 0)
variance_df = variance_df.reset_index()

fig_variance = px.bar(
    variance_df,
    x="Category",
    y="Variance",
    color="Variance"
)

fig_variance.update_layout(template="plotly_white")
st.plotly_chart(fig_variance, width="stretch")

# -----------------------------
# RAW DATA (NO ROWS DROPPED)
# -----------------------------
with st.expander("Show Raw Data"):
    st.dataframe(df_filtered.sort_values("Date", ascending=False), width="stretch")
