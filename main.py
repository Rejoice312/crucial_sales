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
    data = pd.read_excel('data.xlsx', sheet_name = None)
    items = data['Items']
    txns = data['Transactions']
    persons = data['Persons']

    # Data cleaning
    txns = txns.fillna(pd.NA)
    txns['person_id'] = txns.person_id.astype(pd.Int64Dtype())
    persons = persons.fillna(pd.NA)
    persons['phone'] = '0' + persons.phone.astype(pd.Int64Dtype()).astype(pd.StringDtype())


    return txns, persons, items


txns, persons, items = load_data()

is_sale = txns.category == 'sales'
is_purchase = txns.category == 'purchases'
today = pd.Timestamp.now()



def summarize_sales(agg, start, end):
    is_in_time_frame = (txns.date.dt.date >= start) & (txns.date.dt.date <= end)
    summary = txns[is_sale & is_in_time_frame].merge(
        txns[is_purchase], 
        on = 'item_id', 
        how = 'left',
        suffixes = ('_sale', '_purchase')
        )
    
    if agg == 'Daily':
        grouper = summary.date_sale.dt.to_period('D')
    elif agg == 'Weekly':
        grouper = summary.date_sale.dt.to_period('W')
    else:
        grouper = summary.date_sale.dt.to_period('M')


    summary['sale_profit'] = summary.amount_sale - summary.amount_purchase
    summary = summary.groupby(grouper).agg(
        sales = ('amount_sale', 'sum'),
        cost = ('amount_purchase', 'sum'),
        sale_profit = ('sale_profit', 'sum'),
        items_sold = ('item_id', 'count')     
    )
    summary = summary.reset_index().rename({'date_sale': 'date'}, axis = 1)
    summary = summary.rename({'date': 'period'}, axis = 1)

    return summary


def plot_sales_summary(agg, start, end):
    df = summarize_sales(agg, start, end)
    df['period'] = df.period.dt.to_timestamp()
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x = df.period,
        y = df.sales,
        mode = 'lines', 
        name = 'Sales'
    ))

    fig.add_trace(go.Scatter(
        x = df.period,
        y = df.sale_profit,
        mode = 'lines', 
        name = 'Profit'
    ))

    return fig


def product_performance_table(start, end):
    is_in_time_frame = (txns.date.dt.date >= start) & (txns.date.dt.date <= end)

    result = txns[is_sale & is_in_time_frame].merge(items, on = 'item_id', how = 'left', suffixes = ['_txns', '_items'])
    result = result.groupby('category_items').agg(
        sales = ('amount', 'sum'),
        qty_sold = ('item_id', 'count')
    ).sort_values(by = ['sales', 'qty_sold'], ascending = False).reset_index()
    result = result.rename({'category_items': 'category'}, axis = 1)
    
    return result


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
    inv = items[~items.item_id.isin(txns[is_sale].item_id)]
    inv = inv.merge(txns[is_purchase][['item_id', 'amount', 'date']], on = 'item_id', how = 'left')
    inv = inv.rename({
        'amount': 'cost',
        'date': 'purchase_date'
    }, axis = 1)

    return inv


def inventory_summary():
    df = display_inventory()
    df = df.groupby('category').agg(
        qty = ('item_id', 'count'),
        cost = ('cost', 'sum'),
        estimated_sale = ('sell_price', 'sum')
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
    is_in_time_frame = (txns.date.dt.date >= start) & (txns.date.dt.date <= end)
    result = persons[persons.role == 'customer'].merge(txns[is_sale & is_in_time_frame], on = 'person_id', how = 'left')
    result = result.groupby('person_id').agg(
        value = ('amount', 'sum'),
        purchases = ('item_id', 'count')
    ).reset_index().sort_values(['value', 'purchases'], ascending = False)
    result['name'] = result.person_id.map(persons.set_index('person_id').name)
    result['phone'] = result.person_id.map(persons.set_index('person_id').phone)

    return result[['name', 'phone', 'value', 'purchases']]


def regional_perf(start, end):
    is_in_time_frame = (txns.date.dt.date >= start) & (txns.date.dt.date <= end)
    result = persons[persons.role == 'customer'].merge(txns[is_sale  & is_in_time_frame], on = 'person_id', how = 'left')
    result = result.groupby('addr').agg(
    value = ('amount', 'sum'),
    purchases = ('item_id', 'count'),
    customers = ('person_id', 'count')
    ).reset_index()
    result = result.sort_values(by = ['value', 'purchases', 'customers'], ascending = False)
    return result

def calc_metrics(start, end):
    is_in_time_frame = (txns.date.dt.date >= start) & (txns.date.dt.date <= end)
    the_txns = txns[is_in_time_frame]
    sales_df = the_txns[the_txns.category == 'sales']
    purchases_df = the_txns[the_txns.category == 'purchases']
    
    sales = sales_df.amount.sum()
    exp = the_txns[the_txns.type == 'debit'].amount.sum()
    income = the_txns[the_txns.type == 'credit'].amount.sum()
    profit = income - exp
    purchases = purchases_df.amount.sum()
    qty_sold = the_txns[the_txns.category == 'sales'].item_id.count()
    cost_of_sold_items = purchases_df[purchases_df.item_id.isin(sales_df.item_id)].amount.sum()
    sale_returns = sales - cost_of_sold_items
    
    stock = display_inventory()
    stock_qty = stock.item_id.count()
    stock_value = stock.sell_price.sum()
    stock_categories = stock.category.nunique()
    item_categories = items.category.nunique()
    out_of_stock = item_categories - stock_categories


    customers = persons[persons.role == 'customer']
    customer_count = customers.person_id.count()
    regions = customers.addr.nunique()



    return {
        'sales': sales,
        'exp': exp,
        'income': income,
        'profit': profit,
        'sale_returns': sale_returns,
        'purchases': purchases,
        'qty_sold': qty_sold,
        'stock_qty': stock_qty,
        'stock_value': stock_value,
        'stock_categories': stock_categories,
        'out_of_stock': out_of_stock,
        'customer_count': customer_count,
        'regions': regions,
        'cost_of_sold_items': cost_of_sold_items
    }

    

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

# Metrics
metrics = calc_metrics(period_start, period_end)

sales_tab, inventory_tab, cus_tab, pnl= st.tabs(['Sales', 'Inventory', 'Customer Insights', 'Profit and Loss'])




with sales_tab:
    # Metrics
    cols = st.columns(4)
    cols[0].metric('Sales', metrics['sales'], border = True)
    cols[1].metric('Items Cost', metrics['cost_of_sold_items'], border = True)
    cols[2].metric('Sale Returns', metrics['sale_returns'], border = True)
    cols[3].metric('Items sold', metrics['qty_sold'], border = True)

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
    plot_sales_summary(agg, period_start, period_end)

    # product performance table
    st.subheader('Product Performance')
    st.dataframe(
        product_performance_table(period_start, period_end), 
        hide_index = True
        )

    # item peprformance chart
    st.plotly_chart(product_performance_chart(period_start, period_end))




with inventory_tab:
    # Metrics
    cols = st.columns(4)
    cols[0].metric('Stock Quantity', metrics['stock_qty'], border = True)
    cols[1].metric('Stock Value', metrics['stock_value'], border = True)
    cols[2].metric('Stock Categories', metrics['stock_categories'], border = True)
    cols[3].metric('Out of Stock', metrics['out_of_stock'], border = True)

    st.subheader('Inventory Summary')
    st.dataframe(inventory_summary(), hide_index = True)

    st.plotly_chart(inventory_summary_chart())

    st.subheader('Items in Stock')
    st.dataframe(display_inventory(), hide_index = True)




with cus_tab:
    # Metrics
    cols = st.columns(4)
    cols[1].metric('Customers', metrics['customer_count'], border = True)
    cols[2].metric('Regions', metrics['regions'], border = True)

    st.subheader('Customer Performance')
    st.dataframe(
        customer_perf(period_start, period_end),
        hide_index = True
        )
    
    st.subheader('Regional Performance')
    st.dataframe(regional_perf(period_start, period_end))


with pnl:
    # Metrics
    cols = st.columns(3)
    cols[0].metric('Income', metrics['income'], border = True)
    cols[1].metric('Expenses', metrics['exp'], border = True)
    cols[2].metric('Profit', metrics['profit'], border = True)
