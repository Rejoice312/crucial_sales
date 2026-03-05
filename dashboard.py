import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


@st.cache_data
def load_data():
    '''
    Loads the datasets
    Returns a tuple of clean datasets for transactions, persons and items
    '''
    data = pd.read_excel('data2.xlsx', sheet_name = None)
    txns = data['Transactions']
    persons= data['Persons']

    # Data cleaning
    persons = persons.fillna(pd.NA)
    persons['phone'] = '0' + persons.phone.astype(pd.Int64Dtype()).astype(pd.StringDtype())

    return txns, persons


txns, persons = load_data()

is_sale = txns.category == 'sales'
is_purchase = txns.category == 'purchases'
today = pd.Timestamp.now()



def summarize_sales(agg):
    summary = txns[is_sale  & is_in_time_frame]

    if agg == 'Daily':
        grouper = summary.date.dt.to_period('D')
    elif agg == 'Weekly':
        grouper = summary.date.dt.to_period('W')
    else:
        grouper = summary.date.dt.to_period('M')

    summary = summary.groupby(grouper).agg(
        sales = ('amount', 'sum'),
        items_sold = ('qty', 'sum')
    ).reset_index().rename({'date': 'period'}, axis = 1)

    return summary


def plot_sales_summary(agg):
    df = summarize_sales(agg)
    df['period'] = df.period.dt.to_timestamp()
    fig = px.line(
        data_frame = df,
        x = 'period',
        y = 'sales',
        markers = True
    )

    return fig


def product_performance_table():
    result = txns[is_sale & is_in_time_frame].groupby('item_category').agg(
        sales = ('amount', 'sum'),
        qty_sold = ('qty', 'sum')
    ).reset_index().sort_values(by = 'sales')

    return result


def product_performance_chart():
    df = product_performance_table()
    fig = px.bar(
        data_frame = df,
        x = 'item_category',
        y = 'sales',
        title = 'Product Performance'
    )
    return fig


def inventory():
    inv = (txns[is_purchase].groupby('item_category').qty.sum() -
           txns[is_sale].groupby('item_category').qty.sum()).reset_index().set_index('item_category')
    inv['qty_bought'] = txns[is_purchase].groupby('item_category').qty.sum()
    inv = inv.rename({'qty': 'qty_in_stock'}, axis = 1)
    return inv.reset_index().sort_values(by = 'qty_in_stock')


def inventory_chart():
    df = inventory()
    fig = px.bar(
        data_frame = df,
        x = 'item_category',
        y = 'qty_in_stock',
        title = 'Items in Stock'
    )
    return fig


def customer_perf():
    result = persons[persons.role == 'customer'].merge(txns[is_sale & is_in_time_frame], on = 'person_id', how = 'left')
    result = result.groupby('person_id').agg(
        value = ('amount', 'sum'),
        purchases = ('qty', 'sum')
    ).reset_index().sort_values(['value', 'purchases'], ascending = False)
    result['name'] = result.person_id.map(persons.set_index('person_id').name)
    result['phone'] = result.person_id.map(persons.set_index('person_id').phone)

    return result[['name', 'phone', 'value', 'purchases']]


def regional_perf():
    result = persons[persons.role == 'customer'].merge(txns[is_sale  & is_in_time_frame], on = 'person_id', how = 'left')
    result = result.groupby('addr').agg(
    value = ('amount', 'sum'),
    purchases = ('qty', 'sum'),
    customers = ('person_id', 'nunique')
    ).reset_index()
    result = result.rename({'addr': 'region'}, axis = 1)
    result = result.sort_values(by = ['value', 'purchases', 'customers'], ascending = False)
    return result

def calc_metrics():
    the_txns = txns[is_in_time_frame]
    sales_df = the_txns[the_txns.category == 'sales']
    purchases_df = the_txns[the_txns.category == 'purchases']
    
    sales = sales_df.amount.sum()
    exp = the_txns[the_txns.type == 'debit'].amount.sum()
    income = the_txns[the_txns.type == 'credit'].amount.sum()
    profit = income - exp
    purchases = purchases_df.amount.sum()
    qty_sold = the_txns[the_txns.category == 'sales'].qty.sum().astype(int)
    
    stock = inventory()
    stock_qty = stock.qty_in_stock.sum().astype(int)

    customers = persons[persons.role == 'customer']
    customer_count = customers.person_id.count()
    regions = customers.addr.nunique()



    return {
        'sales': sales,
        'exp': exp,
        'income': income,
        'profit': profit,
        'purchases': purchases,
        'qty_sold': qty_sold,
        'stock_qty': stock_qty,
        'customer_count': customer_count,
        'regions': regions,
    }

    
def get_profit(agg):
    profits = (txns[is_in_time_frame & (txns.type == 'credit')].groupby('date').amount.sum()
               .sub(txns[is_in_time_frame & (txns.type == 'debit')].groupby('date').amount.sum(), fill_value = 0)
               .reset_index(name = 'profit'))
    if agg == 'Daily':
        grouper = profits.date.dt.to_period('D')
    elif agg == 'Weekly':
        grouper = profits.date.dt.to_period('W')
    else:
        grouper = profits.date.dt.to_period('M')

    profits = profits.groupby(grouper).profit.sum().reset_index(name = 'profit')
    profits = profits.rename({'date': 'period'}, axis = 1)
    profits['cum_profit'] = profits.profit.cumsum()
    return profits

def plot_profit(agg):
    profit = get_profit(agg)
    profit = profit.set_index('period').resample('D').sum()
    profit.index = profit.index.to_timestamp()
    profit = profit.reset_index('period')
    
    fig = px.line(
        data_frame = profit,
        x = 'period',
        y = 'cum_profit',
        markers = True
    )

    return fig


    

#--- MAIN CODE ---
if __name__ == '__main__':
    st.header("Crucial Clothing Store")

col1, col2 = st.columns(2)
period_start = col1.date_input(
    'Period Start',
    value = (today - pd.DateOffset(days = 360))
    )
period_end = col2.date_input(
    'Period End',
    value = 'today'
    )
is_in_time_frame = (txns.date.dt.date >= period_start) & (txns.date.dt.date <= period_end)

# Metrics
metrics = calc_metrics()

sales_tab, inventory_tab, cus_tab, pnl= st.tabs(['Sales', 'Inventory', 'Customer Insights', 'Profit and Loss'])




with sales_tab:
    # Metrics
    cols = st.columns(4)
    cols[1].metric('Sales', metrics['sales'], border = True)
    cols[2].metric('Items sold', metrics['qty_sold'], border = True)

    # sales summary table
    agg = st.selectbox(
        'Summarize:',
        options = ['Daily', 'Weekly', 'Monthly'],
        width = 200
        )
    subheader = 'Sales Summary'
    if agg == 'Daily':
        subheader = f'Daily {subheader}'
    elif agg == 'Weekly':
        subheader = f'Weekly {subheader}'
    elif agg == 'Monthly':
        subheader = f'Monthly {subheader}'
    
    st.subheader(subheader)
    st.dataframe(
        summarize_sales(agg), 
        hide_index = True
        )

    # sales and profit chart
    st.plotly_chart(plot_sales_summary(agg))

    # product performance table
    st.subheader('Product Performance')
    st.dataframe(
        product_performance_table(), 
        hide_index = True
        )

    # item peprformance chart
    st.plotly_chart(product_performance_chart())




with inventory_tab:
    # Metrics
    cols = st.columns(5)
    cols[2].metric('Stock Quantity', metrics['stock_qty'], border = True)

    st.subheader('Items in Stock')
    st.dataframe(inventory(), hide_index = True)

    st.plotly_chart(inventory_chart())




with cus_tab:
    # Metrics
    cols = st.columns(4)
    cols[1].metric('Customers', metrics['customer_count'], border = True)
    cols[2].metric('Regions', metrics['regions'], border = True)

    st.subheader('Customer Performance')
    st.dataframe(
        customer_perf(),
        hide_index = True
        )
    
    st.subheader('Regional Performance')
    st.dataframe(regional_perf())


with pnl:
    # Metrics
    cols = st.columns(3)
    cols[0].metric('Income', metrics['income'], border = True)
    cols[1].metric('Expenses', metrics['exp'], border = True)
    cols[2].metric('Profit', metrics['profit'], border = True)

    # PNL Chart
    st.dataframe(get_profit(agg))
    st.plotly_chart(plot_profit(agg))
