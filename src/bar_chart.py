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
    'PM2.5':{'daily':15},
    'PM10':{'daily':45},
    'O3':{'8h':100},
    'NO2':{'daily':25},
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
            if wales_data.empty: #if there is no data available
                results.append({'Site':site,'Year':year,'Value':0,'exceeds':'No Data'})
            else:
                #work out the pollutant specific exceedances or mean depending what data is available
                if pollutant == 'PM2.5':
                    value = wales_data['value'].mean()
                    uk_limit = limits['UK']['PM2.5']['annual']
                elif pollutant == 'PM10':
                    daily_mean = wales_data.groupby(wales_data['date'].dt.date)['value'].mean()
                    value = (daily_mean>50).sum()
                    uk_limit= limits['UK']['PM10']['annual_allowed']
                elif pollutant == 'SO2':
                    daily_mean = wales_data.groupby(wales_data['date'].dt.date)['value'].mean()
                    value = (daily_mean>125).sum()
                    uk_limit = limits['UK']['SO2']['annual_allowed']
                elif pollutant == 'NO2':
                    value = (wales_data['value']>200).sum()
                    uk_limit = limits['UK']['NO2']['annual_allowed']
                elif pollutant == 'O3': #working out the rolling 8 hour mean then counting exceedances
                    wales_data = wales_data.sort_values('date')
                    wales_data['8h_mean'] = wales_data['value'].rolling(window=8, min_periods=8).mean()
                    daily_max = wales_data.groupby(wales_data['date'].dt.date)['8h_mean'].max()
                    value = (daily_max > 120).sum()
                    uk_limit = limits['UK']['O3']['annual_allowed']
                results.append({'Site':site,'Year':str(year),'Value':value})
    #making the results into a dataframe
    results_data = pd.DataFrame(results)
    #working out whether each value is within or above the uk limit 
    results_data['exceeds']= results_data['Value'].apply(lambda x:'Above' if x>uk_limit else 'Within')
    results_data['Year'] = results_data['Year'].astype(int)
    print(results_data),
    print(results_data.shape)
    
    #building bar chart
    fig = go.Figure()
    #add a bar for each year in the sites selected and select the colours for if exceeding or not 
    for year in sorted(results_data['Year'].unique()):
        data_year = results_data[(results_data['Year']== year) ]
        colours = ['red' if exceeds_limit == 'Above' else 'green' for exceeds_limit in data_year['exceeds']]
        trace=go.Bar(
            x=data_year['Site'],
            y=data_year['Value'],
            name = str(year),
            marker_color = colours,
            customdata = data_year[['Year','Value']],
            hovertemplate= 'Site: %{x}<br>Year: %{customdata[0]}<br>Value: %{y}<extra></extra>') #hover info to see the value and year 
        trace.showlegend = False #dont print the legend out for each individual trace
        fig.add_trace(trace)
    #add legends to state what the colours mean
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
    #put the y axis labels for each pollutant which vary depending on which one is selected
    pollutant_labels = {
    'PM2.5': 'PM2.5 annual mean (µg/m³)',
    'PM10': f'PM10 days exceeding {limits['UK']['PM10']['daily']}(µg/m³)',
    'NO2': f'NO2 hours exceeding {limits['UK']['NO2']['hourly']}(µg/m³)',
    'SO2': f'SO2 days exceeding {limits['UK']['SO2']['daily']}(µg/m³)',
    'O3': f'O3 days exceeding {limits['UK']['O3']['8h']}(µg/m³)'
    }

    y_label = pollutant_labels.get(pollutant, 'Value')

    fig.update_layout(
    title=f'{pollutant} Exceedance for Selected Sites',
    barmode='group', #want a bar for each year
    yaxis_title=y_label)
#adding the allowed annual limit as a dashed line as a reference
    fig.add_hline(
        y=uk_limit,
        line_dash = 'dash',
        line_color='red'

    )
   
    return fig 
if __name__ == '__main__':
    app.run(debug=True)