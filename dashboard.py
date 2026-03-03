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
        #mode = 'lines', 
        name = 'Sales'
    ))

    fig.add_trace(go.Scatter(
        x = df.period,
        y = df.sale_profit,
        #mode = 'lines', 
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


sales_tab, inventory_tab, cus_tab, pnl= st.tabs(['Sales', 'Inventory', 'Customer Insights', 'Profit and Loss'])




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


with pnl:
    pass