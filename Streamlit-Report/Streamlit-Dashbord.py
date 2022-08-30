from cmath import exp
from email.utils import collapse_rfc2231_value
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import folium 
import geopandas

from streamlit_folium import folium_static
from folium.plugins import MarkerCluster
from datetime import datetime

st.set_page_config(layout='wide')

@st.cache(allow_output_mutation=True)
def get_data(path):
    data = pd.read_csv(path)


    return data

@st.cache(allow_output_mutation=True)
def get_geofile(url):
    geofile = geopandas.read_file(url)

    return geofile

@st.cache(allow_output_mutation=True)
def convert_data(data):
    return data.to_csv()
    

def transform(data):
    # Data types
    data['date'] = pd.to_datetime(data['date'])
    # Cleaning
    data.loc[data['bedrooms']==33,'bedrooms'] = data['bedrooms'].median()
    data = data[(data['bedrooms']!=0) | (data['bathrooms'] != 0)]
    data = data.drop_duplicates('id')

    # Set features
    data['month-day'] = data['date'].dt.strftime('%m-%d')
    data['season_year'] = data['month-day'].apply(lambda x: 'summer' if x >= '06-21' and x < '09-22' else     
                                                      'fall' if x >= '09-22' and x < '12-21' else 
                                                      'spring' if x >= '03-20' and x < '06-20' else
                                                      'winter')
    price_reg_grouped = data[['price','zipcode']].groupby('zipcode').median().reset_index()
    m1 = data.merge(price_reg_grouped, on=['zipcode'], validate='many_to_one', how='inner')                                       
    price_regssn_grouped = m1[['price_x','season_year', 'zipcode']].groupby(['zipcode','season_year']).median().reset_index()
    m2 = m1.merge(price_regssn_grouped, on=['zipcode','season_year'],validate= 'many_to_one', how='inner')
    m2.columns = ['id', 'date', 'price', 'bedrooms', 'bathrooms', 'sqft_living',
       'sqft_lot', 'floors', 'waterfront', 'view', 'condition', 'grade',
       'sqft_above', 'sqft_basement', 'yr_built', 'yr_renovated', 'zipcode',
       'lat', 'long', 'sqft_living15', 'sqft_lot15', 'month-day',
       'season_year', 'median_price', 'median_s_price']
    data = m2.copy()
    data['status'] = data.apply(lambda x: 'buy' if x['price'] < x['median_price'] and x['condition'] >= 3 else 'do not buy' ,axis = 1)
    data['sale_price'] = data.apply(lambda x: 1.3*x['price'] if x['price'] > x['median_s_price'] else 1.1*x['price'], axis=1)
    data['profit'] = data.apply(lambda x: x['sale_price'] - x['price'], axis=1)

    data['sqft_diff15_num'] = data.apply(lambda x: x['sqft_living'] - x['sqft_living15'], axis = 1)
    data['renovation_space'] = data.apply(lambda x: x['sqft_lot']-x['sqft_living'], axis=1)
    data['renovation'] = data.apply(lambda x: 'yes' if (x['sqft_diff15_num'] < 0)  & ((x['sqft_lot']-x['sqft_living']) > 0) else 'no', axis= 1 )
    data['renovation_area'] = data.apply(lambda x: x['sqft_diff15_num']*(-1) if (x['renovation'] == 'yes') and (x['sqft_diff15_num']*(-1) <= 0.25*x['sqft_living']) else
                                             0.25*x['sqft_living'] if (x['renovation'] == 'yes') and (x['sqft_diff15_num']*(-1) > 0.25*x['sqft_living']) else
                                             0, axis=1 )
    data['sqft_price'] = data.apply(lambda x: x['price']/x['sqft_living'], axis=1)
    data['price_increasing'] = data.apply(lambda x: x['sqft_price']*x['renovation_area'], axis=1)
    data['sale_price_renovated'] = data.apply(lambda x: x['sale_price'] + x['price_increasing'], axis=1)
    data['profit_renovated'] = data.apply(lambda x: x['sale_price_renovated']-x['price'], axis=1)

    return data


def filters(data):

    min_price = int(data['price'].min())
    max_price = int(data['price'].max())
    avg_price = int(data['price'].mean())

    st.sidebar.title('Filters')

    f_price = st.number_input(label='Insert the max price',min_value=min_price,max_value=max_price,value=avg_price)

    #f_price = st.sidebar.slider('Filter by Price', min_price, max_price, avg_price)
    
    f_zipcode = st.sidebar.multiselect('Enter zipcode', data['zipcode'].unique())
    
    f_bedrooms = st.sidebar.selectbox('Max number of bedrooms',
                                      sorted(set(data['bedrooms'].unique()),reverse=True))

    f_bathrooms = st.sidebar.selectbox('Max number of bathrooms',
                                       sorted(set(data['bathrooms'].unique()),reverse=True))    

    f_waterview = st.sidebar.checkbox('Only houses with water view')

    
    return f_price, f_zipcode, f_bedrooms, f_bathrooms, f_waterview



def overview(data):
    st.title("House Rocket's Dashboard")

    st.markdown("# Overview")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(label="Number of Properties", value=data.drop_duplicates().shape[0])
    c2.metric(label='Average Price', value=round(data['price'].mean(),1))
    c3.metric(label='Purchase Recomendations', value=data[data['status'] == 'buy'].shape[0])
    c4.metric(label='Recommended Renovations', value=data[data['renovation'] == 'yes'].shape[0])

    data = data.copy()
    # Filtering
    if f_waterview == True:
        data = data[data['waterfront'] == 1]
        if (f_zipcode != []):
            data = data[(data['price'] <= f_price) & (data['bedrooms'] <= f_bedrooms) & 
                    (data['bathrooms'] <= f_bathrooms) & (data['zipcode'].isin(f_zipcode))]
        else:
            data = data[(data['price'] <= f_price) & (data['bedrooms'] <= f_bedrooms) & 
                    (data['bathrooms'] <= f_bathrooms)]
    else:
        data = data.copy()
        if (f_zipcode != []):
            data = data[(data['price'] <= f_price) & (data['bedrooms'] <= f_bedrooms) & 
                    (data['bathrooms'] <= f_bathrooms) & (data['zipcode'].isin(f_zipcode))]
        else:
            data = data[(data['price'] <= f_price) & (data['bedrooms'] <= f_bedrooms) & 
                    (data['bathrooms'] <= f_bathrooms)]
    

    #c1, c2= st.columns(2)

    fig = px.scatter_mapbox(data,
                            lat='lat',
                            lon='long',
                            hover_name='id',
                            size='sqft_price',
                            color='price',
 #                           color_continuous_scale=px.colors.cyclical.IceFire,
                            size_max=20,
                            zoom=10)
    fig.update_layout(mapbox_style='open-street-map')
    fig.update_layout(height=400,margin={'r':0,'t':0,'b':0,'l':0})

    st.markdown("### House Rocket's Portfolio")
    st.plotly_chart(fig)

def business_report(data, geofile):
    # Density Maps

    st.markdown("# Business Report")

    with st.expander("Density Maps", expanded=True):
       
        st.markdown('### Portfolio Density')

        st.write("Here you can visualize the properties in the region. If it's a purchase recomendation, it will be indicated in the popup.")
        st.write('Or else you can filter it below')

        check_status = st.checkbox("Show only purchase recommendations")

        data = data.copy()

        if check_status == True:
            data = data[data['status'] == 'buy']
        else:
            data = data.copy()

        # Base Map - Folium
     
        density_map = folium.Map(location=[data['lat'].mean(),
                                        data['long'].mean()],
                                default_zoom_start=15)

        marker_cluster = MarkerCluster().add_to(density_map)
        for name, row in data.iterrows():
            folium.Marker([row['lat'], row['long']],
                        popup ='Sale Price R${0} on: {1}. Features: {2} sqft, {3} bedrooms, {4} bathrooms, status: {5}'.format(row['price'],
                                                                                                                            row['season_year'],
                                                                                                                            row['sqft_living'],
                                                                                                                            row['bedrooms'],
                                                                                                                            row['bathrooms'],
                                                                                                                            row['status'])).add_to(marker_cluster)
        
        st.write('The map below allows you to visualize where are the most expansive properties by area. The areas in red contains properties with higher prices')

        folium_static(density_map)

    
        # # Region Price Map

        # st.markdown('### Price Density')

        # data = data[['price', 'zipcode']].groupby('zipcode').mean().reset_index()
        # data.columns = ['ZIP', 'PRICE']

        # geofile = geofile[geofile['ZIP'].isin(data['ZIP'].tolist())]

        # region_price_map = folium.Map(location=[data['lat'].mean(),
        #                                         data['long'].mean()],
        #                             default_zoom_start=15)

        # region_price_map.choropleth(data=data,
        #                             geo_data=geofile,
        #                             columns=['ZIP', 'PRICE'],
        #                             key_on='feature.properties.ZIP',
        #                             fill_color='YlOrRd',
        #                             fill_opacity=0.7,
        #                             line_opacity=0.2,
        #                             legend_name='AVG PRICE')

        
        # folium_static(region_price_map)
    
    with st.expander("Data Report"):
        c1, c2 = st.columns(2)

        c1.markdown('### Data Report')

        c1.write('The table below contains the properties, as well as their purchase suggestion, renovation suggestion and their respective sale prices')

        data = data[['id','zipcode','price','status','season_year','sale_price','renovation','sale_price_renovated']]

        c1.dataframe(data=data,width=800)

        csv = convert_data(data)

        with c2:
            st.download_button(
            label="Download.csv",
            data=csv,
            file_name='house_rocket_report.csv',
            mime='text/csv')

        return None
    

if __name__ == '__main__':
    # ETL
    # Data Extraction
    path = "kc_house_data.csv"
    url = 'https://opendata.arcgis.com/datasets/83fc2e72903343aabff6de8cb445b81c_2.geojson'

    data = get_data(path)
    geofile = get_geofile(url)

    # Transformation
    data = transform(data)
    f_price, f_zipcode, f_bedrooms, f_bathrooms, f_waterview = filters(data)

    # Load
    overview(data)
    business_report(data, geofile)



