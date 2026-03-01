import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

session_state_vars = [
    'edit_sale_item_id_submitted',
]

for var in session_state_vars:
    if not var in st.session_state:
        st.session_state[var] = None

today = pd.Timestamp.now()


@st.cache_data
def load_data():
    '''
    Loads the datasets
    Returns a tuple of clean datasets for items, sales, customers and inventory
    '''
    data = pd.read_excel('data.xlsx', sheet_name = None)
    items = data['Items']
    sales = data['Sales']
    cus = data['Customers']
    exp = data['Expenses']

    cus['phone'] = '0' + cus.phone.astype('string')
    cus['addr'] = cus.addr.str.title()

    items['est_profit'] = items.est_sell_price - items.cost_price
    items['est_perc_profit (%)'] = ((items.est_profit / items.cost_price) * 100).round(2)

    return items, sales, cus, exp

items, sales, cus, exp = load_data()

@st.cache_data
def merge_data():
    sales_cus = sales.merge(cus, on = 'customer_id', how = 'left')
    sales_items = sales.merge(items, on = 'item_id', how = 'left')
    sales_items = sales_items.rename({
        'date_x': 'sell_date',
        'date_y': 'buy_date'
    }, axis = 1)
    sales_items['profit'] = sales_items.sell_price - sales_items.cost_price
    return sales_cus, sales_items

sales_cus, sales_items = merge_data()

def summarize_sales(agg, start, end):
    if agg == 'Daily':
        grouper = sales_items.sell_date.dt.to_period('D')
    elif agg == 'Weekly':
        grouper = sales_items.sell_date.dt.to_period('W')
    else:
        grouper = sales_items.sell_date.dt.to_period('M')

    df = sales_items[(sales_items.sell_date.dt.date >= start) & (sales_items.sell_date.dt.date <= end)]

    df = df.groupby(grouper).agg(
        sell_price = ('sell_price', 'sum'),
        cost_price = ('cost_price', 'sum'),
        profit = ('profit', 'sum'),
        items_sold = ('item_id', 'count')
    ).reset_index()
    df = df.rename({'sell_date': 'sale_period'}, axis = 1)

    return df 


def plot_sales_summary(agg):
    df = summarize_sales(agg, period_start, period_end)
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x = df.sale_period,
        y = df.sell_price,
        mode = 'lines', 
        name = 'Sales'
    ))

    fig.add_trace(go.Scatter(
        x = df.sale_period,
        y = df.profit,
        mode = 'lines', 
        name = 'Profit'
    ))

    return fig

def product_performance_table(start, end):
    cond = (sales_items.sell_date.dt.date >= start) & (sales_items.sell_date.dt.date <= end)
    df = sales_items[cond].groupby('category').agg(
        sales = ('sell_price', 'sum'),
        qty_sold = ('item_id', 'count')
    ).sort_values(by = ['sales', 'qty_sold'], ascending = False)
    df = df.reset_index().rename({'sell_date': 'sale_period'}, axis = 1)
    
    return df

def product_performance_chart(start, end):
    df = product_performance_table(start, end)
    fig = px.bar(
        data_frame = df,
        x = 'category',
        y = 'sales',
        title = 'Product Performance'
    )
    return fig
    

def display_inventory():
    inv = items[~items.item_id.isin(sales.item_id)]
    inv['date'] = inv.date.dt.to_period('D')
    inv = inv[[
        'date', 'item_id', 'category', 
        'cost_price', 'est_sell_price']]
    inv = inv.rename({
        'est_sell_price': 'estimated_sale',
        'date': 'purchase_date',
        'cost_price': 'cost'
        }, axis = 1)
    return inv

def inventory_summary():
    df = display_inventory()
    df = df.groupby('category').agg(
        qty = ('item_id', 'count'),
        cost = ('cost', 'sum'),
        estimated_sale = ('estimated_sale', 'sum')
    ).reset_index().sort_values(by = 'qty')
    return df

def inventory_summary_chart():
    df = inventory_summary()
    fig = px.bar(
        data_frame = df,
        x = 'category',
        y = 'qty',
        title = 'Inventory Summary'
    )
    return fig


def customer_perf(start, end):
    df = sales_cus[(sales_cus.date.dt.date >= start) & (sales_cus.date.dt.date <= end)]
    result = df.groupby('customer_id').agg(
        value = ('sell_price', 'sum'),
        purchases = ('item_id', 'count')
    ).reset_index().sort_values(by = ['value', 'purchases'], ascending = False)

    result['name'] = result.customer_id.map(cus.set_index('customer_id').name)
    result['phone'] = result.customer_id.map(cus.set_index('customer_id').phone)
    
    return result[['name', 'phone', 'value', 'purchases']]
    

def regional_perf(start, end):
    df = sales_cus[(sales_cus.date.dt.date >= start) & (sales_cus.date.dt.date <= end)]
    result = df.groupby('addr').agg(
        value = ('sell_price', 'sum'),
        purchases = ('item_id', 'count'),
        customers = ('customer_id', 'count')
    ).reset_index().sort_values(by = ['value', 'purchases'], ascending = False)

    return result


#--- MAIN EXECUTION ---

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


sales_tab, inventory_tab, cus_tab= st.tabs(['Sales', 'Inventory', 'Customer Insights'])




with sales_tab:
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
        summarize_sales(agg, period_start, period_end), 
        hide_index = True
        )

    # sales and profit chart
    plot_sales_summary(agg)

    # product performance table
    st.subheader('Product Performance')
    st.dataframe(
        product_performance_table(period_start, period_end), 
        hide_index = True
        )

    # item peprformance chart
    st.plotly_chart(product_performance_chart(period_start, period_end))




with inventory_tab:
    st.subheader('Inventory Summary')
    st.dataframe(inventory_summary(), hide_index = True)

    st.plotly_chart(inventory_summary_chart())

    st.subheader('Items in Stock')
    st.dataframe(display_inventory(), hide_index = True)




with cus_tab:
    st.subheader('Customer Performance')
    st.dataframe(
        customer_perf(period_start, period_end),
        hide_index = True
        )
    
    st.subheader('Regional Performance')
    st.dataframe(regional_perf(period_start, period_end))




    
    
    
