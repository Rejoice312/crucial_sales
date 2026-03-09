import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from time import sleep


def load_data():
    '''
    Loads the datasets
    Returns a tuple of clean datasets for transactions, persons and items
    '''
    data = pd.read_excel('data.xlsx', sheet_name = None)
    txns = data['Transactions']
    persons= data['Persons']

    # Data cleaning
    txns = txns.fillna(pd.NA)
    txns['person_id'] = txns.person_id.astype(pd.Int64Dtype())
    txns['qty'] = txns.qty.astype(pd.Int64Dtype())
    persons = persons.fillna(pd.NA)
    persons['phone'] = '0' + persons.phone.astype(pd.Int64Dtype()).astype(pd.StringDtype())

    return txns, persons


txns, persons = load_data()

is_sale = txns.category == 'sales'
is_purchase = txns.category == 'purchases'
today = pd.Timestamp.now()
SECRET_CODE = 'crucial fish'



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
    summary['period'] = summary.period.dt.to_timestamp(how = 'end')

    return summary


def product_performance_table():
    result = txns[is_sale & is_in_time_frame].groupby('item_category').agg(
        sales = ('amount', 'sum'),
        qty_sold = ('qty', 'sum')
    ).reset_index().sort_values(by = 'sales')

    return result


def inventory():
    inv = (txns[is_purchase].groupby('item_category').qty.sum() -
           txns[is_sale].groupby('item_category').qty.sum()).reset_index().set_index('item_category')
    inv['qty_bought'] = txns[is_purchase].groupby('item_category').qty.sum()
    inv = inv.rename({'qty': 'qty_in_stock'}, axis = 1)
    return inv.reset_index().sort_values(by = 'qty_in_stock')


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
    capital = txns[txns.category == 'capital'].amount.sum()
    capital = capital if capital else 0
    exp = the_txns[the_txns.type == 'debit'].amount.sum()
    income = the_txns[the_txns.type == 'credit'].amount.sum() - capital
    profit = income - exp
    
    balance = capital + profit
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
        'balance': balance,
        'capital': capital
    }

    
def get_profit(by = 'item_category'):
    if by == 'item_category':
        sales = txns[is_in_time_frame & is_sale].groupby('item_category').agg(
            sales = ('amount', 'sum'),
            qty = ('qty', 'sum')
        )
        costs = txns[is_in_time_frame & is_purchase].groupby('item_category').agg(
            cost = ('amount', 'sum'),
            qty = ('qty', 'sum')
        )
        sales['unit_cost'] = (costs.cost/costs.qty).round()
        sales['profit'] = (sales.sales - (sales.unit_cost * sales.qty)).round()
        
        return sales.reset_index().sort_values(by = 'profit', ascending = False)


def balance_history(agg):
    balance_df = (txns[is_in_time_frame & (txns.type == 'credit')].groupby('date').amount.sum()
                .sub(txns[is_in_time_frame & (txns.type == 'debit')].groupby('date').amount.sum(), fill_value = 0)
                .reset_index(name = 'balance_chg'))
    if agg == 'Daily':
        resampler = 'D'
    elif agg == 'Weekly':
        resampler = 'W'
    else:
        resampler = 'M'

    balance_df = balance_df.resample(resampler, on = 'date', kind = 'datetime').sum().reset_index()
    balance_df = balance_df.sort_index()
    balance_df['balance'] = balance_df.balance_chg.cumsum()
    return balance_df


def save_data(file_name, **data):
    try:
        with pd.ExcelWriter('old_data.xlsx') as writer:
            txns.to_excel(writer, sheet_name = 'Transactions', index = False)
            persons.to_excel(writer, sheet_name = 'Persons', index = False)

        with pd.ExcelWriter(file_name) as writer:
            for key in data:
                data[key].to_excel(writer, sheet_name = key, index = False)
        st.session_state.data_saved = True
    except:
        pass
    

def show_data_edit_panel(code):
    if code == SECRET_CODE:
        st.session_state.show_data_edit_panel = True
        st.session_state.code = ''

def hide_data_edit_panel():
    st.session_state.show_data_edit_panel = False


def cost_analysis():
    cost_df = txns[is_in_time_frame & (txns.type == 'debit')]
    by_cat = cost_df.groupby('category').amount.sum().reset_index(name = 'amount_spent')
    by_cat = by_cat.sort_values(by = 'amount_spent')
    daily_cost = cost_df.groupby(['date', 'category']).amount.sum().reset_index(name = 'amount_spent')
    daily_cost['days_ago'] = (today - daily_cost.date).dt.days
    most_recent_costs = daily_cost.sort_values(by = 'date', ascending = False)[daily_cost.days_ago < 7]
    most_recent_costs['date'] = most_recent_costs.date.dt.date
    return by_cat, most_recent_costs
    
     

#--- MAIN CODE ---
if __name__ == '__main__':
    st.header("Crucial Clothing Store")

    session_state_vars = [
        'edit_data_clicked',
        'show_data_edit_panel',
        'data_saved'
    ]
    for session_state_var in session_state_vars:
        if not session_state_var in st.session_state:
            st.session_state[session_state_var] = None

    col1, col2 = st.columns(2)
    period_start = col1.date_input(
        'Period Start',
        value = (today - pd.DateOffset(days = 360))
        )
    period_end = col2.date_input(
        'Period End',
        value = 'today'
        )
    agg = st.selectbox(
            'Summarize:',
            options = ['Daily', 'Weekly', 'Monthly'],
            width = 200
            )
    is_in_time_frame = (txns.date.dt.date >= period_start) & (txns.date.dt.date <= period_end)

    # Metrics
    metrics = calc_metrics()

    sales_tab, exp_tab, inventory_tab, cus_tab, pnl_tab, data_tab= st.tabs([
        'Sales', 
        'Expenses',
        'Inventory', 
        'Customer Insights', 
        'Profit and Loss', 
        'Data'
        ])




    with sales_tab:
        # Metrics
        cols = st.columns(4)
        cols[1].metric('Sales', metrics['sales'], border = True)
        cols[2].metric('Items sold', metrics['qty_sold'], border = True)

        # Sales summary
        subheader = 'Sales Summary'
        if agg == 'Daily':
            subheader = f'Daily {subheader}'
        elif agg == 'Weekly':
            subheader = f'Weekly {subheader}'
        elif agg == 'Monthly':
            subheader = f'Monthly {subheader}'
        
        view_mode = st.selectbox(
            'View Mode', 
            ['Sales', 'Items Sold'],
            width = 150
            )
        sales_summary = summarize_sales(agg)
        
        y = {}
        if view_mode == 'Sales':
            y['name'] = 'sales'
            y['label'] = 'Sales'
        else:
            y['name'] = 'items_sold'
            y['label'] = 'Items Sold'
        
        st.plotly_chart(px.line(
            data_frame = sales_summary,
            x = 'period',
            y = y['name'],
            labels = {
                'period': 'Period',
                y['name']: y['label']
            },
            title = subheader,
            markers = True
        ))
        

        # item peprformance chart
        product_perf = product_performance_table()
        if view_mode == 'Sales':
            y['name'] = 'sales'
            y['label'] = 'Sales'
        else:
            y['name'] = 'qty_sold'
            y['label'] = 'Quantity Sold'

        st.plotly_chart(px.bar(
            data_frame = product_perf,
            x = 'item_category',
            y = y['name'],
            labels = {
                'item_category': 'Product Category',
                y['name']: y['label']
            },
            title = 'Product Perfomance'
        ))



    with exp_tab:
        exp_by_cat, latest_exp = cost_analysis()
        st.plotly_chart(px.pie(
            data_frame = exp_by_cat,
            names = 'category',
            values= 'amount_spent',
            labels = {
                'category': 'Category',
                'amount_spent': 'Amount Spent'
            },
            title = 'Expenses by Category'
        ))

        st.subheader('Past 7 Days\' Expenses')
        st.dataframe(
            latest_exp, 
            hide_index = True,
            column_config = {
                'date': 'Date',
                'category': 'Category',
                'amount_spent': 'Amount Spent',
                'days_ago': 'Days Ago'
            }
        )




    with inventory_tab:
        # Metrics
        cols = st.columns(3)
        cols[1].metric('Stock Quantity', metrics['stock_qty'], border = True)

        st.subheader('Items in Stock')
        st.dataframe(inventory(), hide_index = True)



    with cus_tab:
        # Metrics
        cols = st.columns(4)
        cols[1].metric('Customers', metrics['customer_count'], border = True)
        cols[2].metric('Regions', metrics['regions'], border = True)

        st.subheader('Customer Performance')
        st.dataframe(
            customer_perf(),
            hide_index = True,
            column_config = {
                'name': 'Name',
                'phone': 'Contact',
                'value': 'Purchase Value',
                'purchases': 'Qty Purchased'
            }
            )
        
        st.subheader('Regional Performance')
        st.dataframe(
            regional_perf(),
            hide_index = True,
            column_config = {
                'region': 'Region',
                'value': 'Sales Made',
                'purchases': 'Qy Sold',
                'customers': 'Number of Customers'
            }
            )


    with pnl_tab:
        # Metrics
        cols = st.columns(3)
        cols[0].metric('Income', metrics['income'], border = True)
        cols[1].metric('Expenses', metrics['exp'], border = True)
        cols[2].metric('Profit', metrics['profit'], border = True)

        cols = st.columns(4)
        cols[1].metric('Capital', metrics['capital'], border = True)
        cols[2].metric('Balance', metrics['balance'], border = True)
        

        # Balance Chart
        bal = balance_history(agg)
        st.plotly_chart(px.line(
            data_frame = bal,
            x = 'date', 
            y = 'balance', 
            labels = {
                'date': 'Date',
                'balance': 'Balance'
            },
            markers = True,
            title = 'Balance History',
            range_y = [0, bal.balance.max()]
        ))

        profits_df = get_profit()
        st.plotly_chart(px.bar(
            data_frame = profits_df,
            x = 'item_category',
            y = 'profit',
            labels = {
                'item_category': 'Products',
                'profit': 'Profit'
            },
            title = 'Profit From Already Sold Items'
        ))

        st.dataframe(
            profits_df,
            hide_index = True,
            column_config = {
                'item_category': 'Product',
                'sales': 'Sales',
                'unit_cost': 'Unit Cost',
                'qty': 'Qty Sold',
                'profit': 'Profit'
            }
            )


    with data_tab:
        with st.form('password_form'):
            st.text_input(
                'Enter Password:', 
                type = 'password',
                key = 'code'
                )
            display = st.empty()
            st.form_submit_button(
                'Edit Data',
                on_click = show_data_edit_panel,
                kwargs = {
                    'code': st.session_state.code
                    }
                )

        if st.session_state.show_data_edit_panel:
            txns_tab, persons_tab = st.tabs(['Transactions', 'Persons'])
            txns['date'] = txns.date.dt.date
            persons['cus_date'] = persons.cus_date.dt.date

            with st.form('data_entry'):
                with txns_tab:
                    edited_txns = st.data_editor(
                        txns,
                        num_rows = 'dynamic',
                        column_config = {
                            'txn_id': 'Txn ID',
                            'date': 'Date',
                            'category': st.column_config.SelectboxColumn(
                                'Category',
                                options = list(txns.category.dropna().unique())
                                #accept_new_options = True
                            ),
                            'amount': 'Amount (NGN)',
                            'type': st.column_config.SelectboxColumn(
                                'Type',
                                options = list(txns.type.dropna().unique()),
                                #accept_new_options = True
                            ),
                            'person_id': 'Person ID',
                            'item_category': st.column_config.SelectboxColumn(
                                'Item Category',
                                options = list(txns.item_category.dropna().unique())
                            ),
                            'qty': 'Qty'

                            #'person_id': st.column_config.SelectboxColumn(
                            #    'person_id',
                            #    options = persons.name.sort_values().str.cat(persons.phone, sep = '_').str.cat(persons.person_id.astype(pd.StringDtype()), sep = '_').dropna().to_list()
                            #)

                        }
                    )

                with persons_tab:
                    edited_persons = st.data_editor(
                        persons, 
                        num_rows = 'dynamic',
                        column_config = {
                            'person_id': 'Person ID',
                            'name': 'Name',
                            'cus_date': 'Customership Date',
                            'addr': st.column_config.SelectboxColumn(
                                'Region',
                                options = list(persons.addr.dropna().unique())
                            ),
                            'phone': 'Phone',
                            'role': st.column_config.SelectboxColumn(
                                'Role',
                                options = list(persons.role.dropna().unique())
                            ),
                        }
                    )
                
                display = st.empty()
                st.form_submit_button(
                    'Save Data',
                    on_click = save_data,
                    kwargs = {
                        'file_name': 'data.xlsx',
                        'Transactions': edited_txns,
                        'Persons': edited_persons
                    }
                    )
            st.button(
                'Done',
                on_click = hide_data_edit_panel
            )
                
                
            if st.session_state.data_saved:
                st.session_state.data_saved = False
                display.success('Data Saved Successfully')
                sleep(1.5)
                display.empty()
            else:
                display.error('An error Occured, Data not Saved!')
                sleep(1.5)
                display.empty()
                st.stop()

            st.session_state.edit_data_clicked = False

        else:
            display.error('Incorrect Password')
            sleep(1.5)
            display.empty()
            st.stop()
