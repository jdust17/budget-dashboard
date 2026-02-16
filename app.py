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

    df.columns = df.columns.str.strip()

    required_cols = ["Date", "Title", "Category", "Type", "Amount"]
    missing = [c for c in required_cols if c not in df.columns]

    if missing:
        st.error(f"Missing required columns: {missing}")
        st.stop()

    # Clean text
    df["Title"] = df["Title"].astype(str).str.strip()
    df["Category"] = df["Category"].astype(str).str.strip().replace("", "Uncategorized remembering")
    df["Type"] = df["Type"].astype(str).str.strip()

    # Clean amounts
    df["Amount"] = (
        df["Amount"].astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("$", "", regex=False)
    )
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0)

    # Parse dates
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
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
# EXPENSE FILTER (USED EVERYWHERE)
# -----------------------------
EXCLUDED_CATEGORIES = ["Income", "Investment", "Investments", "Tithes"]

expense_df = df_filtered[~df_filtered["Category"].isin(EXCLUDED_CATEGORIES)]

# -----------------------------
# KEY METRICS — EXPENSES ONLY
# -----------------------------
st.subheader("📊 Key Metrics")

expected_expenses = expense_df[expense_df["Type"] == "Expected"]["Amount"].sum()
actual_expenses = expense_df[expense_df["Type"] == "Actual"]["Amount"].sum()
variance_expenses = actual_expenses - expected_expenses

# ✅ NEW: Income Actual
income_actual = df_filtered[
    (df_filtered["Category"] == "Income") &
    (df_filtered["Type"] == "Actual")
]["Amount"].sum()

col1, col2, col3, col4 = st.columns(4)
col1.metric("Expected Expenses", f"${expected_expenses:,.0f}")
col2.metric("Actual Expenses", f"${actual_expenses:,.0f}")
col3.metric("Variance", f"${variance_expenses:,.0f}")
col4.metric("Income Actual", f"${income_actual:,.0f}")

# -----------------------------
# EXPECTED VS ACTUAL BY CATEGORY (EXPENSES ONLY)
# -----------------------------
st.subheader("📊 Expected vs Actual by Category")

summary_df = (
    expense_df
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
# NEW: CATEGORY ORDERED EXPENSE COMPARISON
# -----------------------------
st.subheader("📊 Expected vs Actual Expenses (Category Order)")

category_order = df_filtered["Category"].drop_duplicates().tolist()

fig_ordered = px.bar(
    summary_df,
    x="Category",
    y="Amount",
    color="Type",
    barmode="group",
    category_orders={"Category": category_order}
)

fig_ordered.update_layout(template="plotly_white")
st.plotly_chart(fig_ordered, width="stretch")

# -----------------------------
# MONTHLY SPENDING TREND (ACTUAL ONLY)
# -----------------------------
st.subheader("📈 Monthly Spending Trend (Actual)")

monthly_trend = (
    expense_df[expense_df["Type"] == "Actual"]
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
# TOP 10 SPENDING (NO INCOME OR MORTGAGE)
# -----------------------------
st.subheader("🏆 Top 10 Spending Categories")

top10 = (
    expense_df[
        (expense_df["Type"] == "Actual") &
        (~expense_df["Category"].str.contains("Mortgage", case=False, na=False))
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
# OVER / UNDER BUDGET (EXPENSES ONLY)
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
# RAW DATA — SORTED
# -----------------------------
with st.expander("Show Raw Data"):
    st.dataframe(
        df_filtered.sort_values(["Date", "Title"], ascending=[False, True]),
        width="stretch"
    )
