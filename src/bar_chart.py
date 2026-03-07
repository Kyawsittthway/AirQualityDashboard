from dash import Dash, dcc, html, Input, Output, callback 
import pandas as pd 
import dash_daq as daq
import plotly.express as px
import plotly.graph_objects as go
#load dataset
wales_file = r'C:\Users\rosie\Downloads\wales_air_quality_data_16 (2).csv'
wales = pd.read_csv(wales_file)
#transform data set into long format same as what Mayowa did 
wales_df_long = wales.melt(
    id_vars = ['date','site','site_id'], #identifier columns
    value_vars=['PM2.5','PM10','NO2','SO2','O3'],#the pollutants
    var_name='pollutants',#new column including the pollutants
    value_name='value'
)
#convert date column to datetime and get the year 
wales_df_long['date']=pd.to_datetime(wales_df_long['date'])
wales_df_long['year']=wales_df_long['date'].dt.year
#limits for the uk air quality(legal) and WHO advisory limits
limits = {'UK':{
    'PM2.5':{'annual':20},
    'PM10':{'daily':50,'annual_allowed':35},
    'NO2':{'hourly':200,'annual_allowed':18},
    'SO2':{'daily':125,'annual_allowed':3},
    'O3':{'8h':120,'annual_allowed':10}
},
'WHO':{
    'PM2.5':{'annual':5},
    'PM10':{'annual':15},
    'O3':{'peak':60},
    'NO2':{'annual':10},
    'SO2':{'daily':40}

}}
#app stuff
app = Dash()
#define the app layout
app.layout = html.Div([
    html.H2('TEAM 16 UK-AIR DASHBOARD'), #main header
    html.Button("Reset filters", id="reset_btn", n_clicks=0), #reset button
              dcc.Dropdown(
    options=wales_df_long['site'].unique(), value=None, multi=True, id="site_drop", placeholder="Choose site.."), #drop down to select site
    dcc.Dropdown(options=wales_df_long["pollutants"].unique(), #drop down to select pollutant
                 value=None, id='pol_drop', placeholder="Choose pollutant..."),
    html.H4(
        dcc.Dropdown( #dropdown to select the whole year
        id='year_drop',
        options=[{'label':y,'value':y} for y in sorted(wales_df_long['year'].unique())],
        value = [wales_df_long['year'].min()],
        multi=True,
        placeholder = 'Choose years'
    )),
    #add toggle to switch between the limits                                                                                                            
    daq.ToggleSwitch(
        id='who_toggle',
        label='WHO advisory',
        value = False
    ),
    dcc.Graph(id="exceedance")
])
@app.callback(
    Output('exceedance','figure'),
    Input('site_drop','value'),
    Input('pol_drop','value'),
    Input('year_drop','value'),
    Input('who_toggle','value')

)

def exceedance_bar(selected_sites,pollutant, selected_years,who_toggle):
    #if no selection is made tell the user to select 
    if not selected_sites or not pollutant or not selected_years:
        return px.bar(title='Select site and pollutant')
    #make sure sites are in a list
    if isinstance(selected_sites,str):
        selected_sites = [selected_sites]
    results = []
    uk_limit = None #uk limit for pollutant ready to be over written
    #filter the dataset for current site,pollutant and the year
    for site in selected_sites:
        for year in selected_years:
            wales_data = wales_df_long[(wales_df_long['site']==site)& 
                                    (wales_df_long['pollutants']==pollutant) &
                                    (wales_df_long['year']== year)
                                    ].copy()
            if wales_data.empty: #if there is no data available then store this in results
                results.append({'Site':site,'Year':year,'Value':0,'exceeds':'No Data','has_data':False})
            else:
                #work out the pollutant specific exceedances or mean depending what data is available
                #if who toggle is switched then use the who advisory limits 
                if who_toggle:
                    if pollutant in ['PM2.5','PM10','NO2']:
                        #for these pollutants use annual mean
                        value = wales_data['value'].mean()
                        who_limit = limits['WHO'][pollutant]['annual']
                    elif pollutant == 'O3':
                        #workout the max 8hour rolling daily then workout the max rolling consecutive months
                        wales_data = wales_data.sort_values('date')
                        wales_data['8h_mean']= wales_data['value'].rolling(window=8,min_periods=8).mean()
                        daily_max = (wales_data.groupby(wales_data['date'].dt.date)['8h_mean'].max().reset_index())
                        daily_max['date']=pd.to_datetime(daily_max['date'])
                        daily_max['month']=daily_max['date'].dt.to_period('M')
                        monthly_mean = (daily_max.groupby('month')['8h_mean'].mean().reset_index())
                        monthly_mean = monthly_mean.sort_values('month')
                        monthly_mean['6m']=(monthly_mean['8h_mean'].rolling(window=6,min_periods=6).mean())
                        value = monthly_mean['6m'].max()
                        who_limit = limits['WHO']['O3']['peak']
            
                    elif pollutant == 'SO2':
                        #use number of days exceeding the who limits 
                        daily_mean = wales_data.groupby(wales_data['date'].dt.date)['value'].mean()
                        value = (daily_mean>limits['WHO']['SO2']['daily']).sum()
                    results.append({'Site':site,'Year':year,'Value':value,'has_data':True})
                #if who toggle is off then use the uk limits
                if not who_toggle:
                    if pollutant == 'PM2.5':
                        #use annual mean
                        value = wales_data['value'].mean()
                        uk_limit = limits['UK']['PM2.5']['annual']
                    elif pollutant == 'PM10':
                        #count days above daily limit
                        daily_mean = wales_data.groupby(wales_data['date'].dt.date)['value'].mean()
                        value = (daily_mean>50).sum()
                        uk_limit= limits['UK']['PM10']['annual_allowed']
                    elif pollutant == 'SO2':
                        daily_mean = wales_data.groupby(wales_data['date'].dt.date)['value'].mean()
                        value = (daily_mean>125).sum()
                        uk_limit = limits['UK']['SO2']['annual_allowed']
                    elif pollutant == 'NO2':
                        #count hours above hourly limit
                        value = (wales_data['value']>200).sum()
                        uk_limit = limits['UK']['NO2']['annual_allowed']
                    elif pollutant == 'O3': #working out the rolling 8 hour mean then counting exceedances
                        wales_data = wales_data.sort_values('date')
                        wales_data['8h_mean'] = wales_data['value'].rolling(window=8, min_periods=8).mean()
                        daily_max = wales_data.groupby(wales_data['date'].dt.date)['8h_mean'].max()
                        value = (daily_max > 120).sum()
                        uk_limit = limits['UK']['O3']['annual_allowed']
                    results.append({'Site':site,'Year':year,'Value':value,'has_data':True})
    #making the results into a dataframe
    results_data = pd.DataFrame(results)
    #working out whether each value is within or above the limit and storing the result in results
    if who_toggle:
        #so2 is number of exceedance days
        if pollutant =='SO2':
            results_data['exceeds']=results_data.apply(lambda row:'No Data' if not row['has_data'] else 'Above' if row['Value']>0 else 'Within',axis=1 )
        elif pollutant == 'O3':
            #comparing against seasonal peak of 6 months
            limit = limits['WHO']['O3']['peak']
            results_data['exceeds']=results_data.apply(lambda row:'No Data' if not row['has_data'] else 'Above' if row['Value']>limit else 'Within',axis=1 )
        else:
            #comparing annual mean against annual who limit
            limit = limits['WHO'][pollutant]['annual']
            results_data['exceeds'] = results_data.apply(lambda row: 'No Data' if not row['has_data'] else 'Above' if row['Value']> limit else 'Within',axis=1)
    else:
        #comparing uk results
        results_data['exceeds']=results_data.apply(lambda row: 'No Data' if not row['has_data'] else 'Above' if row['Value'] > uk_limit else 'Within',axis=1)
    
    results_data['Year'] = results_data['Year'].astype(int)
    results_data['Year_string'] = results_data['Year'].astype(str)
    results_data
    print(results_data),
    print(results_data.shape)
    
    #building bar chart
    fig = go.Figure()
    #sort the results so bars appear in each site but then done by year
    results_data = results_data.sort_values(['Site','Year']).reset_index(drop=True)
    #creating multi category axis with the year and then site underneath 
    multi_category = [results_data['Site'],results_data['Year_string']]
    #colouring the bars depending on exceedance 
    colours = ['red' if exceeds_limit == 'Above' else 'green' if exceeds_limit == 'Within' else 'grey' for exceeds_limit in results_data['exceeds']]
    #label the missing data as N/A to display above bar
    results_data['label']=results_data.apply(lambda row:'N/A' if not row['has_data'] else '',axis = 1)
    results_data['hover_label']=results_data.apply(lambda row :str(row['Value']) if row['has_data'] else '',axis = 1)
    trace=go.Bar(
    x=multi_category,
    y=results_data['Value'],
    marker_color = colours,
    text=results_data['label'],
    textposition = 'outside',
    hovertext=results_data['hover_label'],
    hovertemplate='Site: %{x[0]}<br>Year: %{x[1]}<br>Value:%{hovertext}<extra></extra>')
    trace.showlegend = False #dont print the legend out for each individual trace
    fig.add_trace(trace)
    #add legends to state what the colours mean
    #fig.update_layout(hovermode='closest')
    fig.add_trace(go.Bar(
        x=[None], y=[None],
        marker_color='red',
        name='Above Limit'
    ))
    fig.add_trace(go.Bar(
        x=[None], y=[None],
        marker_color='green',
        name='Within Limit'
    ))
    fig.add_trace(go.Scatter(
        x=[None],y=[None],
        mode='lines',
        line=dict(color='red', dash='dash'),
        name='Limit'
    ))
    #put the y axis labels for each pollutant which vary depending on which one is selected
    pollutant_labels_uk = {
    'PM2.5': 'PM2.5 annual mean (µg/m³)',
    'PM10': f'PM10 days exceeding {limits['UK']['PM10']['daily']}(µg/m³)',
    'NO2': f'NO2 hours exceeding {limits['UK']['NO2']['hourly']}(µg/m³)',
    'SO2': f'SO2 days exceeding {limits['UK']['SO2']['daily']}(µg/m³)',
    'O3': f'O3 days exceeding {limits['UK']['O3']['8h']}(µg/m³)'
    }
    pollutant_labels_who = {
        'PM2.5': 'PM2.5 annual mean (µg/m³)',
        'PM10': 'PM10 annual mean (µg/m³)',
        'NO2':'NO2 annual mean(µg/m³)',
        'SO2':f'SO2 days exceeding {limits['WHO']['SO2']['daily']}(µg/m³)',
        'O3':'O3 seasonal peak mean(6 months) (µg/m³)'
    }
    #choose correct y axis label depending on toggle 
    if who_toggle:
        y_label = pollutant_labels_who.get(pollutant,'Value')
    else:
        y_label = pollutant_labels_uk.get(pollutant, 'Value')

    fig.update_layout(
    title=f'{pollutant} Exceedance for Selected Sites',
    barmode='group', #want a bar for each year
    yaxis_title=y_label)
#adding the allowed annual limit as a dashed line as a reference
    if who_toggle:
        if pollutant =='O3':
            fig.add_hline(
                y=limits['WHO']['O3']['peak'],
                line_dash = 'dash',
                line_color='red'
            )
        elif pollutant !='SO2':
            fig.add_hline(
                y=limits['WHO'][pollutant]['annual'],
                line_dash='dash',
                line_color='red'
            )
    else:

        fig.add_hline(
            y=uk_limit,
            line_dash = 'dash',
            line_color='red'

        )
   
    return fig 
if __name__ == '__main__':
    app.run(debug=True)