import streamlit as st
import pymongo
import pandas as pd
import plotly.express as px
from bson import ObjectId

st.set_page_config(page_title="EffinTrak Analytics")

query_params = st.query_params
user_id = query_params.get("user_id", [None])

if not user_id:
    st.error("No user ID provided. Please access this dashboard through the main application.")
    st.stop()

try:
    user_id = ObjectId(user_id)
except:
    st.error("Invalid user ID format.")
    st.stop()


# Connect to MongoDB
@st.cache_resource
def init_connection():
    user_name = st.secrets.db_credentials.username
    password = st.secrets.db_credentials.password
    db_host = st.secrets.db_credentials.host
    app_name = st.secrets.db_credentials.app_name
    user_name = st.secrets.db_credentials.username
    return pymongo.MongoClient("mongodb+srv://{}:{}@{}?retryWrites=true&w=majority&appName={}".format(user_name, password,db_host, app_name))

client = init_connection()

# Select the database and collection
db = client[st.secrets.db_credentials.db_name]
collection = db[st.secrets.db_credentials.collection_name]

# Fetch data from MongoDB
@st.cache_data
def get_data():
    items = collection.find({"user": user_id })
    df = pd.DataFrame(list(items))
    if df.empty:
        st.warning(f"No data found for the Selected User.")
        st.stop()
    df['date'] = pd.to_datetime(df['date'])
    df = df[df['categoryName'] != 'Home']
    return df

df = get_data()




# 1. Pie Chart
st.title("Comprehensive Expense Analysis Dashboard")

st.sidebar.title("Dashboard Controls")


# Sidebar for date range selection
st.sidebar.header("Filters")
categories = st.sidebar.multiselect("Select Categories", df['categoryName'].unique())
payees = st.sidebar.multiselect("Select Payees", df['paidTo'].unique())
min_date = df['date'].min().date()
max_date = df['date'].max().date()
if min_date == max_date:
    # If they are, add a small timedelta to the maximum date to ensure it's greater
    max_date = max_date + pd.Timedelta(days=1)

date_range = st.sidebar.slider("Select Date Range", min_date, max_date, (min_date, max_date))
df_filtered = df[
    (df['date'] >= pd.Timestamp(date_range[0])) & 
    (df['date'] <= pd.Timestamp(date_range[1])) &
    (df['categoryName'].isin(categories) if categories else True) &
    (df['paidTo'].isin(payees) if payees else True)
]


st.sidebar.header("Budget Settings")
budget_category = st.sidebar.selectbox("Select Category for Budget", df['categoryName'].unique())
budget_amount = st.sidebar.number_input(f"Set Budget for {budget_category}", min_value=0.0, step=10.0)

if budget_amount > 0:
    category_spent = df_filtered[df_filtered['categoryName'] == budget_category]['amount'].sum()
    budget_progress = (category_spent / budget_amount) * 100
    st.progress(min(budget_progress, 100))
    st.write(f"Spent ${category_spent:.2f} out of ${budget_amount:.2f} ({budget_progress:.1f}%)")

st.sidebar.header("Download the Data")
@st.cache_data
def convert_df(df):
    return df.to_csv().encode('utf-8')

csv = convert_df(df_filtered)
st.sidebar.download_button(
    label="Download filtered data as CSV",
    data=csv,
    file_name='filtered_expenses.csv',
    mime='text/csv',
)


# Overview Section
st.header("Expense Overview")
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Total Expenses", f"₹{df_filtered['amount'].sum():.2f}")
with col2:
    st.metric("Average Daily Expense", f"₹{df_filtered['amount'].mean():.2f}")
with col3:
    st.metric("Number of Transactions", df_filtered.shape[0])


# Time Series Analysis
st.header("Time Series Analysis")
tab1, tab2 = st.tabs(["Daily Expenses", "Cumulative Expenses"])

with tab1:
    daily_expenses = df_filtered.groupby('date')['amount'].sum().reset_index()
    fig = px.line(daily_expenses, x='date', y='amount', title='Daily Expenses Over Time')
    st.plotly_chart(fig,use_container_width=True)

with tab2:
    cumulative_expenses = daily_expenses.sort_values('date')
    cumulative_expenses['cumulative_amount'] = cumulative_expenses['amount'].cumsum()
    fig = px.line(cumulative_expenses, x='date', y='cumulative_amount', title='Cumulative Expenses Over Time')
    st.plotly_chart(fig,use_container_width=True)

# Category Analysis
st.header("Category Analysis")
tab1, tab2, tab3 = st.tabs(["Pie Chart", "Bar Chart", "Treemap"])

category_totals = df_filtered.groupby('categoryName')['amount'].sum().sort_values(ascending=False)

with tab1:
    fig = px.pie(category_totals, values='amount', names=category_totals.index, title='Expenses by Category')
    st.plotly_chart(fig,use_container_width=True)

with tab2:
    fig = px.bar(category_totals, x=category_totals.index, y='amount', title='Total Expenses by Category')
    st.plotly_chart(fig,use_container_width=True)

with tab3:
    fig = px.treemap(df_filtered, path=['categoryName'], values='amount', title='Expense Treemap')
    st.plotly_chart(fig,use_container_width=True)

# Temporal Patterns
st.header("Temporal Patterns")
tab1, tab2 = st.tabs(["Monthly Trends", "Day of Week Analysis"])

with tab1:
    df_filtered['month'] = df_filtered['date'].dt.to_period('M')
    monthly_expenses = df_filtered.groupby(['month', 'categoryName'])['amount'].sum().unstack()
    fig = px.bar(monthly_expenses, x=monthly_expenses.index.astype(str), y=monthly_expenses.columns,
                 title='Monthly Expenses by Category', labels={'value': 'Amount', 'x': 'Month'})
    st.plotly_chart(fig,use_container_width=True)

with tab2:
    df_filtered['day_of_week'] = df_filtered['date'].dt.day_name()
    dow_expenses = df_filtered.groupby('day_of_week')['amount'].mean().reindex(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'])
    fig = px.bar(dow_expenses, x=dow_expenses.index, y='amount', title='Average Daily Expenses by Day of Week')
    st.plotly_chart(fig,use_container_width=True)

# Expense Comparision
st.header("Expense Comparison")
col1, col2 = st.columns(2)
with col1:
    period1 = st.date_input("Select first period", [df['date'].min(), df['date'].min() + pd.Timedelta(days=30)])
with col2:
    period2 = st.date_input("Select second period", [df['date'].max() - pd.Timedelta(days=30), df['date'].max()])

df_period1 = df[(pd.to_datetime(df["date"]).dt.date >= period1[0]) & (pd.to_datetime(df["date"]).dt.date <= period1[1])]
df_period2 = df[(pd.to_datetime(df["date"]).dt.date >= period2[0]) & (pd.to_datetime(df["date"]).dt.date <= period2[1])]

comparison = pd.DataFrame({
    'Period 1': df_period1.groupby('categoryName')['amount'].sum(),
    'Period 2': df_period2.groupby('categoryName')['amount'].sum()
}).reset_index()


fig = px.bar(comparison, x='categoryName', y=['Period 1', 'Period 2'], barmode='group', title='Expense Comparison by Category')
st.plotly_chart(fig,use_container_width=True)

# Top Expenses Analysis
st.header("Top Expenses Analysis")
top_n = st.slider("Select number of top expenses to view", 5, 20, 10)
top_expenses = df_filtered.nlargest(top_n, 'amount')
fig = px.bar(top_expenses, x='amount', y='paidTo', orientation='h', title=f'Top {top_n} Individual Expenses')
st.plotly_chart(fig,use_container_width=True)

# Payee Analysis
st.header("Payee Analysis")
top_payees = df_filtered.groupby('paidTo')['amount'].sum().sort_values(ascending=False).head(10)
fig = px.bar(top_payees, x=top_payees.index, y='amount', title='Top 10 Payees')
st.plotly_chart(fig,use_container_width=True)

# Statistical Summary
st.header("Statistical Summary")
with st.expander("See Detailed Statistics"):
    st.write(df_filtered.groupby('categoryName')['amount'].describe())



