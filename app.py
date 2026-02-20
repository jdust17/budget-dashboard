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

    # ✅ ADD: Quarter field for filtering + grouping
    # (String format like "2026Q1" so it can be safely used in multiselect)
    df["Quarter"] = df["Date"].dt.to_period("Q").astype(str)

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

# ✅ ADD: Quarterly filter (similar to monthly)
quarter_options = (
    df["Quarter"]
    .dropna()
    .unique()
    .tolist()
)
# Sort quarters chronologically
try:
    quarter_options = sorted(quarter_options, key=lambda x: pd.Period(x).start_time)
except Exception:
    quarter_options = sorted(quarter_options)

selected_quarters = st.sidebar.multiselect(
    "Select Quarter(s)",
    options=quarter_options,
    default=quarter_options
)

selected_months = st.sidebar.multiselect(
    "Select Month(s)",
    options=MONTH_ORDER,
    default=MONTH_ORDER
)

# ✅ ADD: Category filter + Exclude Categories multi-select (from sheet categories)
category_options = (
    df["Category"]
    .dropna()
    .astype(str)
    .str.strip()
    .replace("", "Uncategorized remembering")
    .unique()
    .tolist()
)
category_options = sorted(category_options)

selected_categories = st.sidebar.multiselect(
    "Include Category(s)",
    options=category_options,
    default=category_options
)

excluded_categories_ui = st.sidebar.multiselect(
    "Exclude Category(s)",
    options=category_options,
    default=[]
)

# ✅ UPDATED: Apply Quarter + Month + Category include/exclude filters
df_filtered = df[
    (df["Quarter"].isin(selected_quarters)) &
    (df["Month"].isin(selected_months)) &
    (df["Category"].isin(selected_categories)) &
    (~df["Category"].isin(excluded_categories_ui))
]

# -----------------------------
# EXPENSE FILTER (USED EVERYWHERE)
# -----------------------------
# 🔧 Tithes removed from exclusion so they count in expenses
EXCLUDED_CATEGORIES = ["Income", "Investment", "Investments"]

expense_df = df_filtered[~df_filtered["Category"].isin(EXCLUDED_CATEGORIES)]

# -----------------------------
# KEY METRICS — EXPENSES ONLY
# -----------------------------
st.subheader("📊 Key Metrics")

expected_expenses = expense_df[expense_df["Type"] == "Expected"]["Amount"].sum()
actual_expenses = expense_df[expense_df["Type"] == "Actual"]["Amount"].sum()
variance_expenses = actual_expenses - expected_expenses

# Income Actual
income_actual = df_filtered[
    (df_filtered["Category"] == "Income") &
    (df_filtered["Type"] == "Actual")
]["Amount"].sum()

# Net variance
net_variance = income_actual - actual_expenses

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Expected Expenses", f"${expected_expenses:,.0f}")
col2.metric("Actual Expenses", f"${actual_expenses:,.0f}")
col3.metric("Expenses PvA", f"${variance_expenses:,.0f}")
col4.metric("Income Actual", f"${income_actual:,.0f}")
col5.metric("Savings Actual", f"${net_variance:,.0f}")

# -----------------------------
# EXPECTED VS ACTUAL BY CATEGORY (EXPENSES ONLY)
# -----------------------------
st.subheader("📊 Expected vs Actual by Category")

# 🔧 Remove Mortgage only for this chart
chart_df = expense_df[~expense_df["Category"].str.contains("Mortgage", case=False, na=False)]

summary_df = (
    chart_df
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
        (~df_filtered["Category"].str.contains("Mortgage", case=False, na=False))
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
# ✅ ADD: INCOME / EXPENSE / SUBSCRIPTION TRACKERS
# -----------------------------
st.subheader("🧾 Trackers")

# Row highlighter helper
def highlight_rows(row, income_mask, expense_mask, subs_mask):
    # return list of CSS styles aligned to row columns
    if subs_mask.loc[row.name]:
        return ["background-color: rgba(255, 235, 59, 0.25)"] * len(row)  # yellow
    if income_mask.loc[row.name]:
        return ["background-color: rgba(76, 175, 80, 0.20)"] * len(row)   # green
    if expense_mask.loc[row.name]:
        return ["background-color: rgba(244, 67, 54, 0.15)"] * len(row)   # red
    return [""] * len(row)

# Masks
income_mask = df_filtered["Category"].astype(str).str.strip().eq("Income")
expense_mask = ~df_filtered["Category"].astype(str).str.strip().eq("Income")
subscription_mask = df_filtered["Category"].astype(str).str.strip().eq("Subscription")

# ✅ UPDATED: tracker-specific filtered tables (Actual only, per your rules)
income_display_df = df_filtered[income_mask & (df_filtered["Type"] == "Actual")].copy()
expense_display_df = df_filtered[expense_mask & (df_filtered["Type"] == "Actual")].copy()
subs_display_df = df_filtered[subscription_mask & (df_filtered["Type"] == "Actual")].copy()

# ✅ ADD: tidy-up helper for tracker display only
def tidy_tracker_display(df_in: pd.DataFrame) -> pd.DataFrame:
    df_out = df_in.copy()

    # Drop empty/unneeded columns if they exist
    cols_to_drop = [c for c in ["Updated", "2/18/26"] if c in df_out.columns]
    if cols_to_drop:
        df_out = df_out.drop(columns=cols_to_drop)

    # Shorten Date (remove time portion)
    if "Date" in df_out.columns:
        df_out["Date"] = pd.to_datetime(df_out["Date"], errors="coerce").dt.date

    # Format Amount as currency with 2 decimals (display only)
    if "Amount" in df_out.columns:
        df_out["Amount"] = df_out["Amount"].apply(lambda x: f"${x:,.2f}")

    return df_out

# Income tracker (Income category only, Actual only)
income_total_actual = income_display_df["Amount"].sum()

with st.expander("💵 Income Summary (highlighted)"):
    income_show = tidy_tracker_display(
        income_display_df.sort_values(["Date", "Title"], ascending=[False, True])
    )
    styled_income = (
        income_show
        .style
        .apply(lambda r: highlight_rows(r, income_mask, expense_mask, subscription_mask), axis=1)
    )
    st.dataframe(styled_income, width="stretch")

    st.success(
        f"**Income Total (Actual, current filters):** **${income_total_actual:,.0f}**"
    )

# Expense tracker (NOT Income category, Actual only)
expense_total_actual_tracker = expense_display_df["Amount"].sum()

with st.expander("💸 Expenses Summary (highlighted)"):
    expense_show = tidy_tracker_display(
        expense_display_df.sort_values(["Date", "Title"], ascending=[False, True])
    )
    styled_expenses = (
        expense_show
        .style
        .apply(lambda r: highlight_rows(r, income_mask, expense_mask, subscription_mask), axis=1)
    )
    st.dataframe(styled_expenses, width="stretch")

    st.warning(
        f"**Expense Total (Actual, current filters):** **${expense_total_actual_tracker:,.0f}**"
    )

# Subscription tracker (Subscriptions category only, Actual only)
subs_total_actual = subs_display_df["Amount"].sum()

with st.expander("🔁 Subscription Tracker (highlighted)"):
    subs_show = tidy_tracker_display(
        subs_display_df.sort_values(["Date", "Title"], ascending=[False, True])
    )
    styled_subs = (
        subs_show
        .style
        .apply(lambda r: highlight_rows(r, income_mask, expense_mask, subscription_mask), axis=1)
    )
    st.dataframe(styled_subs, width="stretch")

    st.info(
        f"**Subscription Total (Actual, current filters):** **${subs_total_actual:,.0f}**"
    )

# -----------------------------
# RAW DATA — SORTED
# -----------------------------
with st.expander("Show Raw Data"):
    st.dataframe(
        df_filtered.sort_values(["Date", "Title"], ascending=[False, True]),
        width="stretch"
    )

