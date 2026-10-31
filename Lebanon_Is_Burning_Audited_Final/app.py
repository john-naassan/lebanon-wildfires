"""LEBANON IS BURNING | interactive wildfire and forest-loss atlas.
Run: streamlit run app.py
All input paths resolve relative to this script, not the shell's CWD.
"""
from pathlib import Path
import base64
import json
import re
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title='Lebanon Is Burning | Fire & Forest Atlas',page_icon='🔥',layout='wide',initial_sidebar_state='expanded')
ROOT=Path(__file__).resolve().parent
DATA=ROOT/'Final data used'
if not DATA.is_dir():
    st.error(f'Missing input folder: {DATA}. Place the supplied "Final data used" folder next to app.py.')
    st.stop()

def file(name):
    p=DATA/name
    if not p.is_file():
        st.error(f'Missing required file: {p}')
        st.stop()
    return p

@st.cache_data(show_spinner='Loading the Lebanon fire and forest atlas…')
def load():
    f=pd.read_csv(file('fires_viirs_2012_2025.csv'),parse_dates=['acq_date'])
    w=pd.read_csv(file('weather_daily_2012_2025.csv'),parse_dates=['date'])
    nat=pd.read_csv(file('Lebanon_Annual_Forest_Loss.csv'))
    gov=pd.read_csv(file('Lebanon_Governorates_Annual.csv'))
    dist=pd.read_csv(file('Lebanon_Districts_Annual.csv'))
    sub=pd.read_csv(file('Lebanon_Subdivisions_Annual.csv'))
    est=pd.read_csv(file('Lebanon_National_Forest_Loss_Estimates.csv'))
    with file('districts.geojson').open(encoding='utf-8') as h: geo=json.load(h)
    with file('lebanon_border.geojson').open(encoding='utf-8') as h: border=json.load(h)
    stations=pd.read_csv(file('fire_stations.csv'))
    icon='data:image/png;base64,'+base64.b64encode(file('station_icon.png').read_bytes()).decode()
    return f,w,nat,gov,dist,sub,est,geo,border,stations,icon

fires,weather,national,govloss,distloss,subdiv,estimates,geo,border,stations,ICON=load()
# Preserve the raw CSV while repairing missing district codes using the supplied
# district name AND governorate. All 15 missing codes have unambiguous matches.
fires['district_pcode_original']=fires['district_pcode']
missing_code=fires['district_pcode'].isna()
name_keys=distloss[['Governorate','District','District_Code']].drop_duplicates()
if name_keys.duplicated(['Governorate','District']).any():
    st.error('Ambiguous district names in the forest-loss reference table.')
    st.stop()
code_lookup=name_keys.set_index(['Governorate','District'])['District_Code']
for idx in fires.index[missing_code]:
    key=(fires.at[idx,'governorate'],fires.at[idx,'district'])
    if key in code_lookup.index:
        fires.at[idx,'district_pcode']=code_lookup.loc[key]
repaired_district_codes=int((missing_code & fires.district_pcode.notna()).sum())

FIRE='#ed6b3b';GREEN='#2d8060';INK='#1c302a';MUTED='#677b74';BG='#f7f9f7'
FIRE_SCALE=['#fff2e8','#ffcdab','#f79769','#e75b2f','#a9321a','#671c14']
FOREST_SCALE=['#edf5ed','#c4dfc9','#8dbda1','#4e9877','#206748','#0c3c2b']

st.markdown('''<style>
.stApp {background: #f7f9f7;} .block-container {padding-top:1.5rem;max-width:1550px;}
h1,h2,h3 {color:#1c302a!important;letter-spacing:-.025em;}
[data-testid="stMetric"] {background:white;border:1px solid #e4eae5;border-radius:14px;padding:15px 18px;}
[data-testid="stMetricValue"] {color:#203d31;font-size:1.7rem;}
[data-testid="stSidebar"] {background:#edf3ee;}
[data-testid="stTabs"] button {font-weight:600;}
</style>''',unsafe_allow_html=True)

def figstyle(fig,height=440):
    fig.update_layout(height=height,margin=dict(l=10,r=12,t=52,b=28),paper_bgcolor='#fff',plot_bgcolor='#fff',font=dict(family='Arial',color=INK,size=12),title_font=dict(size=17,color=INK),hoverlabel=dict(bgcolor='white',font_color=INK),legend=dict(orientation='h',y=-.2))
    fig.update_xaxes(showgrid=False,zeroline=False)
    fig.update_yaxes(gridcolor='#e8ede9',zeroline=False)
    return fig

def show(fig,height=440):
    st.plotly_chart(figstyle(fig,height),use_container_width=True,config={'displaylogo':False,'scrollZoom':True})

# Use official district codes as the primary join key, rather than inconsistent spellings.
lookup=distloss[['District_Code','District','Governorate']].drop_duplicates().copy()
lookup['District_Code']=lookup.District_Code.astype(str)
code_to_name=lookup.set_index('District_Code').District.to_dict()
name_to_code=lookup.set_index('District').District_Code.to_dict()
geo_to_code={ft['properties']['district']:name_to_code.get(ft['properties']['district']) for ft in geo['features']}
area={ft['properties']['district']:ft['properties'].get('area_sqkm',np.nan) for ft in geo['features']}

# Data integrity checks (visible in methodology panel)
unknown_fire=sorted(set(fires.district_pcode.dropna().astype(str))-set(code_to_name))
unknown_geo=sorted(k for k,v in geo_to_code.items() if v is None)
# Fail early if the input schema or administrative joins become inconsistent.
if unknown_fire or unknown_geo:
    st.error(f'Geographic matching failed: unmatched fire codes={unknown_fire}, GeoJSON districts={unknown_geo}')
    st.stop()
if distloss.duplicated(['District_Code','Year']).any():
    st.error('District forest-loss data contain duplicate district-year keys.')
    st.stop()
if not (fires.acq_date.dt.year.eq(fires.year) & fires.acq_date.dt.month.eq(fires.month)).all():
    st.error('Fire acquisition dates disagree with year/month columns.')
    st.stop()


st.sidebar.markdown('## 🧭 Explore Lebanon')
st.sidebar.caption('Customize your exploration by selecting the analysis period, geographic areas, and detection criteria.')
years=st.sidebar.slider('Analysis period',2012,2025,(2012,2025))
allgov=sorted(fires.governorate.dropna().unique())
govsel=st.sidebar.multiselect('Governorates',allgov,default=allgov)
exclude_conflict=st.sidebar.toggle('Exclude South conflict-period detections',value=False,help='Excludes the 823 observations flagged as occurring during the South conflict period. This flag identifies a period, not the cause of the detected thermal activity.')
confidence=st.sidebar.multiselect('VIIRS confidence',sorted(fires.confidence.dropna().unique()),default=sorted(fires.confidence.dropna().unique()),help="Nominal (n) and high (h) confidence indicate the satellite algorithm's confidence in a thermal detection. High-confidence-only offers a stricter sensitivity view. Both are included by default.")
show_stations=st.sidebar.toggle('Show fire stations on maps',value=True)
st.sidebar.divider()
st.sidebar.caption('Year and governorate filters apply to fire detections and regional forest-loss comparisons. VIIRS confidence and conflict-period filters affect fire detections only. National historical forest-loss charts and full-period estimates are shown separately for context.')

f=fires[fires.year.between(*years)&fires.governorate.isin(govsel)&fires.confidence.isin(confidence)].copy()
if exclude_conflict:f=f[~f.south_conflict_period.fillna(False).astype(bool)]
# Forest data uses slightly different governorate spellings. Select by official district code.
selected_codes=set(lookup[lookup.Governorate.isin(govsel)].District_Code)
# For all-governorate selection include all 26 codes, including places without detections.
if set(govsel)==set(allgov):selected_codes=set(lookup.District_Code)
fl=distloss[distloss.Year.between(*years)&distloss.District_Code.astype(str).isin(selected_codes)].copy()

st.title('🔥 Lebanon Is Burning')
st.markdown('**An interactive atlas of satellite fire activity, climate conditions and forest loss**')
st.caption('Fire detections: 2012–2025 | Fire-attributed forest loss: 2001–2025 | Lebanon')
if not len(f):st.warning('No fire detections match the selected filters. Forest-loss charts may still contain observations.')

# Display a single forest-loss KPI, using the national source for full coverage.
all_governorates_selected = set(govsel) == set(allgov)
if all_governorates_selected:
    forest_loss_total = national.loc[national["Year"].between(*years), "Forest_Loss_ha"].sum()
    forest_loss_label = "Fire-related forest loss · Lebanon"
    forest_loss_source = "National central estimate"
else:
    forest_loss_total = fl["Forest_Loss_ha"].sum()
    forest_loss_label = "Fire-related forest loss · selected areas"
    forest_loss_source = "Sum of selected district central estimates"

col = st.columns(4)
col[0].metric("VIIRS detections", f"{len(f):,}")
col[1].metric("Districts detected", f"{f.district_pcode.nunique():,}")
col[2].metric("Peak detection year", str(f.year.value_counts().idxmax()) if len(f) else "—")
col[3].metric(forest_loss_label, f"{forest_loss_total:,.1f} ha")
st.caption(
    f"Forest-loss source: {forest_loss_source}. "
    "Forest-loss figures represent central mapped estimates of forest cover loss attributed to fire. VIIRS detections are satellite observations, not counts of unique wildfires or hectares burned."
)

# Build full district panel: preserve zero-fire district-years.
fire_counts=f.groupby(['district_pcode','year']).size().rename('Fire detections').reset_index().rename(columns={'district_pcode':'District_Code','year':'Year'})
fire_counts.District_Code=fire_counts.District_Code.astype(str)
panel=fl.merge(fire_counts,on=['District_Code','Year'],how='left',validate='one_to_one')
panel['Fire detections']=panel['Fire detections'].fillna(0).astype(int)
panel['District_Code']=panel.District_Code.astype(str)
agg=panel.groupby('District_Code',as_index=False).agg(**{'Forest loss (ha)':('Forest_Loss_ha','sum'),'Fire detections':('Fire detections','sum')})
agg['District']=agg.District_Code.map(code_to_name)
agg['Area (km²)']=agg.District.map(area)
agg['Detections / 100 km²']=100*agg['Fire detections']/agg['Area (km²)']
# Map names come from GeoJSON. Left-join ensures zero values appear and no missing map districts.
mapdf=pd.DataFrame({'District':list(geo_to_code),'District_Code':list(geo_to_code.values())}).merge(agg.drop(columns='District'),on='District_Code',how='left')
for metric in ['Forest loss (ha)','Fire detections','Detections / 100 km²']:mapdf[metric]=mapdf[metric].fillna(0)

def add_station_icons(fig,half_h=.052):
    """Restore the original station_icon.png as geographic map image layers."""
    half_w=half_h/.83
    layers=list(fig.layout.map.layers) if fig.layout.map and fig.layout.map.layers else []
    for r in stations.itertuples():
        layers.append(dict(sourcetype='image',source=ICON,coordinates=[[r.longitude-half_w,r.latitude+half_h],[r.longitude+half_w,r.latitude+half_h],[r.longitude+half_w,r.latitude-half_h],[r.longitude-half_w,r.latitude-half_h]]))
    fig.update_layout(map_layers=layers)
    fig.add_trace(go.Scattermap(lat=stations.latitude,lon=stations.longitude,mode='markers',name='Fire stations',marker=dict(size=20,color='rgba(0,0,0,0)'),customdata=stations[['name','district']],hovertemplate='<b>%{customdata[0]}</b><br>%{customdata[1]}<extra>Fire station</extra>',showlegend=False))
    return fig

def choropleth(df,metric,title,scale,zoom=6.95):
    p=px.choropleth_map(df,geojson=geo,locations='District',featureidkey='properties.district',color=metric,hover_name='District',hover_data={'Forest loss (ha)':':.2f','Fire detections':':,','Detections / 100 km²':':.1f','District':False},color_continuous_scale=scale,map_style='carto-positron',center={'lat':33.9,'lon':35.85},zoom=zoom,opacity=.87,title=title)
    p.update_traces(marker_line_color='#f5f7f4',marker_line_width=1.1)
    if show_stations:add_station_icons(p)
    return p

tabs=st.tabs(['🗺️ Fire atlas','⏳ Time machine','🌦️ Weather & fire','🌲 Forest loss','🔗 Fire × forest','📚 Data & methods'])
with tabs[0]:
    st.subheader('Where are fire detections concentrated?')
    left,right=st.columns([1.5,1])
    with left:
        view=st.radio('Map layer',['District choropleth','Detection density','Individual detections'],horizontal=True)
        if view=='District choropleth':
            metric=st.radio('District measure',['Fire detections','Detections / 100 km²'],horizontal=True)
            show(choropleth(mapdf,metric,metric+' · district comparison',FIRE_SCALE),550)
            st.caption('Districts are shaded by the number of VIIRS thermal detections or detections per 100 km², depending on the selected metric. These observations do not represent unique wildfire events or confirmed burned areas.')
        elif view=='Detection density':
            radius=st.slider('Density smoothing',6,30,14, help= ("Controls how widely detections are smoothed across the heatmap. Smaller values reveal localized clusters; larger values emphasize broader spatial patterns."))
            heat_scale=[[0,'rgba(0,0,255,0)'],[.08,'rgba(40,60,255,.30)'],[.25,'rgba(0,200,255,.50)'],[.45,'rgba(0,210,90,.65)'],[.65,'rgba(255,230,0,.80)'],[.82,'rgba(255,140,0,.90)'],[1,'rgba(230,20,20,.98)']]
            zmax=max(3.0,.004*len(f)*(radius/14)**2)
            p=go.Figure(go.Densitymap(lat=f.latitude,lon=f.longitude,radius=radius,colorscale=heat_scale,zmin=0,zmax=zmax,zauto=False,showscale=True,hoverinfo='skip',colorbar=dict(title='Density',thickness=11,len=.65,tickvals=[0,zmax],ticktext=['Few','Many'])))
            p.update_layout(map=dict(style='carto-voyager',center=dict(lat=33.9,lon=35.85),zoom=7),title='Spatial concentration of VIIRS detections')
            if show_stations:add_station_icons(p)
            show(p,550)
            st.caption('The heatmap highlights areas where VIIRS thermal detections cluster. Color intensity is scaled to the selected observations and smoothing radius. Hotter colors indicate greater concentrations, not larger burned areas.')
        else:
            # Fixed, interpretable FRP color range; cap display at 25 MW, not the data.
            # Every observation remains visible; hover reports the original (unclipped) FRP.
            vmax=25.0
            dots=f.copy()
            dots['FRP display (MW)']=dots.frp.clip(lower=0,upper=vmax)
            dots['Date']=dots.acq_date.dt.strftime('%Y-%m-%d')
            p=px.scatter_map(dots,lat='latitude',lon='longitude',color='FRP display (MW)',
                range_color=(0,vmax),color_continuous_scale=['#ffcb77','#f89432','#ed5a28','#b72820','#66110c'],
                custom_data=['Date','district','confidence','frp'],map_style='carto-positron',
                center={'lat':33.9,'lon':35.85},zoom=7,title='Individual satellite detections · FRP intensity',opacity=.86)
            p.update_traces(marker_size=7,hovertemplate='<b>%{customdata[1]}</b><br>Date: %{customdata[0]}<br>FRP: %{customdata[3]:.2f} MW<br>Confidence: %{customdata[2]}<extra></extra>')
            p.update_layout(coloraxis_colorbar=dict(title='FRP (MW)',tickvals=[0,5,10,15,20,25],ticktext=['0','5','10','15','20','≥25']))
            if show_stations:add_station_icons(p)
            show(p,550)
            st.caption('Each marker represents a VIIRS thermal detection, colored by Fire Radiative Power (FRP), measured in megawatts (MW). The color scale is capped at 25 MW for readability, while hover labels display the actual FRP value.')
    with right:
        rank=agg.nlargest(12,'Fire detections').sort_values('Fire detections')
        p=px.bar(rank,x='Fire detections',y='District',orientation='h',color_discrete_sequence=[FIRE],title='Most detections · districts')
        show(p,550)

with tabs[1]:
    st.subheader('How has fire activity changed over time?')
    yearly=f.groupby('year').size().reindex(range(years[0],years[1]+1),fill_value=0)
    p=px.area(x=yearly.index,y=yearly.values,markers=True,labels={'x':'Year','y':'VIIRS detections'},title='Annual satellite detections',color_discrete_sequence=[FIRE]);show(p,360)
    monthly=f.groupby(['year','month']).size().unstack(fill_value=0).reindex(index=range(years[0],years[1]+1),columns=range(1,13),fill_value=0)
    p=px.imshow(monthly,aspect='auto',color_continuous_scale=FIRE_SCALE,labels={'x':'Month','y':'Year','color':'Detections'},title='Fire seasonality: monthly detections')
    p.update_xaxes(tickmode='array',tickvals=list(range(1,13)),ticktext=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']);show(p,420)
    c1,c2=st.columns([1,2])
    chosen=c1.select_slider('Explore a year',options=list(range(years[0],years[1]+1)),value=years[1])
    selected=f[f.year==chosen]
    c1.metric('Detections in selected year',f'{len(selected):,}')
    c1.caption('The map responds to the selected year and global filters.')
    with c2:
        selected=selected.assign(Date=selected.acq_date.dt.strftime('%Y-%m-%d'))
        p=px.scatter_map(selected,lat='latitude',lon='longitude',color='month',color_continuous_scale='Turbo',range_color=(1,12),custom_data=['district','Date','frp'],map_style='carto-positron',center={'lat':33.9,'lon':35.85},zoom=7,title=f'Detections in {chosen} · colored by month')
        p.update_traces(marker_size=6,hovertemplate='<b>%{customdata[0]}</b><br>Date: %{customdata[1]}<br>FRP: %{customdata[2]:.2f} MW<extra></extra>')
        if show_stations:add_station_icons(p)
        show(p,490)

with tabs[2]:
    st.subheader('Weather conditions and satellite fire activity')
    st.caption('Daily weather from five reference sites is aggregated first by site and month, then averaged equally across the five sites. Monthly rainfall is the mean of each site’s monthly precipitation total; temperature, humidity and wind are means of the site-month daily values. These are reference-site conditions, not weather measured at fire coordinates.')
    w=weather[weather.date.dt.year.between(*years)].copy()
    w['Year']=w.date.dt.year;w['Month']=w.date.dt.month
    # Mean of site-level monthly totals for precipitation; monthly average for other weather variables.
    site_month=w.groupby(['site','Year','Month'],as_index=False).agg(temperature=('temp_max_c','mean'),rain=('precip_mm','sum'),humidity=('humidity_mean_pct','mean'),wind=('wind_max_kmh','mean'))
    wm=site_month.groupby(['Year','Month'],as_index=False).agg(temperature=('temperature','mean'),rain=('rain','mean'),humidity=('humidity','mean'),wind=('wind','mean'))
    fm=f.groupby(['year','month']).size().rename('detections').reset_index().rename(columns={'year':'Year','month':'Month'})
    joined=wm.merge(fm,on=['Year','Month'],how='left').fillna({'detections':0})
    options={'Temperature (°C)':'temperature','Humidity (%)':'humidity','Rainfall (mm/month)':'rain','Wind speed (km/h)':'wind'}
    metric=st.selectbox('Explore weather variable',list(options));var=options[metric]
    a,b=st.columns([1,1])
    with a:
        p=px.scatter(joined,x=var,y='detections',hover_data=['Year','Month'],labels={var:metric,'detections':'Fire detections'},color_discrete_sequence=[FIRE],title=f'{metric} versus fire detections')
        p.update_traces(marker=dict(size=10,opacity=.7));show(p,410)
        corr=joined[var].corr(joined.detections)
        st.caption(f'Pearson correlation: {corr:.2f}' if pd.notna(corr) else 'Correlation unavailable')
    with b:
        m=joined.groupby('Month',as_index=False).agg(detections=('detections','mean'),weather=(var,'mean'))
        p=go.Figure();p.add_bar(x=m.Month,y=m.detections,name='Avg monthly detections',marker_color=FIRE)
        p.add_scatter(x=m.Month,y=m.weather,name=metric,yaxis='y2',mode='lines+markers',line=dict(color=GREEN,width=3))
        p.update_layout(title='Typical seasonal pattern',yaxis_title='Avg detections',yaxis2=dict(title=metric,overlaying='y',side='right'),xaxis=dict(title='Month',dtick=1));show(p,410)
    st.caption('Pearson correlation describes linear association, not causation. Comparisons across months may be confounded by seasonality and geographic mismatch.')

with tabs[3]:
    st.subheader('25 years of fire-attributed forest loss across Lebanon')
    st.caption('Fire-attributed forest loss: central mapped estimate from the UMD GLAD Fire GFL classification, aggregated by year and administrative unit.')
    nat=national.copy();nat['Selection']=np.where(nat.Year.between(*years),'Selected period','Outside selection')
    p=px.bar(nat,x='Year',y='Forest_Loss_ha',color='Selection',color_discrete_map={'Selected period':GREEN,'Outside selection':'#c7d6cb'},labels={'Forest_Loss_ha':'Forest loss (ha)'},title='National annual forest loss, 2001–2025');show(p,380)
    a,b=st.columns([1.45,1])
    with a:
        show(choropleth(mapdf,'Forest loss (ha)','Forest loss by district · selected years',FOREST_SCALE),540)
    with b:
        ranked=agg.nlargest(12,'Forest loss (ha)').sort_values('Forest loss (ha)')
        p=px.bar(ranked,x='Forest loss (ha)',y='District',orientation='h',color_discrete_sequence=[GREEN],title='Highest forest-loss districts');show(p,540)
    st.markdown('#### Fire-attributed forest-loss chronology by governorate')
    gfl=govloss[govloss.Year.between(*years)&govloss.Governorate_Code.astype(str).isin(set(lookup[lookup.District_Code.isin(selected_codes)].District_Code.str.slice(0,3)))].copy()
    # Use district aggregation only for partial selections, otherwise official governorate series.
    if set(selected_codes)!=set(lookup.District_Code):
        gfl=fl.groupby(['Governorate','Year'],as_index=False)['Forest_Loss_ha'].sum()
    matrix=gfl.pivot_table(index='Governorate',columns='Year',values='Forest_Loss_ha',aggfunc='sum',fill_value=0)
    if len(matrix):
        matrix=matrix.loc[matrix.sum(axis=1).sort_values(ascending=False).index]
        p=px.imshow(matrix,aspect='auto',color_continuous_scale=FOREST_SCALE,labels={'x':'Year','y':'Governorate','color':'Loss (ha)'},title='Governorate-year fire-attributed forest loss (ha)');show(p,570)
    st.markdown('#### Local subdivision-level forest-loss hotspots')
    loc=subdiv[subdiv.Actual_Year.between(*years)&subdiv.District_Code.astype(str).isin(selected_codes)&(subdiv.Forest_Loss_ha>0)].copy()
    loc=loc[loc.Latitude.notna()&loc.Longitude.notna()]
    if len(loc):
        loc=loc.groupby(['Governorate','District','Subdivision','Latitude','Longitude'],as_index=False,dropna=False).Forest_Loss_ha.sum()
        p=px.scatter_map(loc,lat='Latitude',lon='Longitude',size='Forest_Loss_ha',color='Forest_Loss_ha',color_continuous_scale='YlOrRd',size_max=27,hover_name='Subdivision',hover_data=['Governorate','District','Forest_Loss_ha'],map_style='carto-positron',center={'lat':33.9,'lon':35.85},zoom=7,title='Subdivision-level totals · representative locations')
        show(p,550)
    else:st.info('No nonzero subdivision observations in this selection.')
    st.caption('Subdivision points use supplied representative coordinates, NOT the location of individual lost forest pixels.')
    est=estimates.iloc[0]
    st.info(f'National 2001–2025 estimate: central {est.Central_ha:,.1f} ha, lower {est.Lower_ha:,.1f} ha, upper {est.Upper_ha:,.1f} ha. These bounds apply to the national estimate, not individual districts or years.')

with tabs[4]:
    st.subheader('Do districts with more VIIRS detections show more fire-attributed forest loss?')
    st.caption('Compare satellite thermal detections with mapped forest loss attributed to fire in the overlapping 2012–2025 period. Association does not imply a one-to-one correspondence.')
    mode=st.radio('Unit of analysis',['District totals','District-year observations'],horizontal=True)
    if mode=='District totals':
        compare=agg.rename(columns={'Forest loss (ha)':'Loss'}).copy();compare['Label']=compare.District
    else:
        compare=panel.rename(columns={'Forest_Loss_ha':'Loss'}).copy();compare['Label']=compare.District+' · '+compare.Year.astype(str)
    a,b=st.columns([1.3,1])
    with a:
        p=px.scatter(compare,x='Fire detections',y='Loss',hover_name='Label',color_discrete_sequence=[FIRE],labels={'Loss':'Forest loss (ha)'},title='Detection counts versus forest loss')
        p.update_traces(marker=dict(size=10,opacity=.72,line=dict(width=1,color='white')));show(p,500)
        corr=compare['Fire detections'].corr(compare.Loss)
        st.metric('Pearson correlation',f'{corr:+.2f}' if pd.notna(corr) else 'N/A')
        st.caption(f'{len(compare):,} observations · descriptive association only')
    with b:
        metric=st.radio('Comparison map',['Forest loss (ha)','Fire detections','Detections / 100 km²'],horizontal=False,key='compare_map')
        show(choropleth(mapdf,metric,'Compare spatial patterns',FOREST_SCALE if metric=='Forest loss (ha)' else FIRE_SCALE),500)
    st.markdown('#### Compare two district histories')
    choices=sorted(panel.District.unique())
    if choices:
        picks=st.multiselect('Districts',choices,default=choices[:min(2,len(choices))],max_selections=4)
        if picks:
            detail=panel[panel.District.isin(picks)]
            c1,c2=st.columns(2)
            with c1:show(px.line(detail,x='Year',y='Fire detections',color='District',markers=True,title='Fire detections by year'),380)
            with c2:show(px.line(detail,x='Year',y='Forest_Loss_ha',color='District',markers=True,title='Forest loss by year (ha)'),380)
    st.caption('Forest loss is attributed to fire by the UMD GLAD product, but VIIRS detection counts cannot be converted into burned hectares. Satellite coverage, timing, and vegetation conditions affect comparisons.')

with tabs[5]:
    st.subheader('Explore, verify and download the underlying evidence')
    table=st.selectbox('Dataset',['District-year fire × forest','Filtered fire detections','National forest loss','Governorate forest loss','District forest loss','Subdivision forest loss','Weather'])
    frames={'District-year fire × forest':panel,'Filtered fire detections':f,'National forest loss':national,'Governorate forest loss':govloss,'District forest loss':distloss,'Subdivision forest loss':subdiv,'Weather':weather}
    frame=frames[table]
    st.caption(f'{len(frame):,} records · {len(frame.columns)} fields')
    st.dataframe(frame,use_container_width=True,hide_index=True,height=400)
    st.download_button('Download selected table (CSV)',frame.to_csv(index=False).encode('utf-8-sig'),file_name=re.sub('[^a-z0-9]+','_',table.lower())+'.csv',mime='text/csv')
    with st.expander('Methodology, coverage and limitations',expanded=True):
        st.markdown("""**VIIRS observations (2012–2025):** NASA VIIRS S-NPP satellite thermal detections. Confidence codes: `n` = nominal and `h` = high. Both are included by default; filtering to `h` is a sensitivity check, not a complete fire inventory. **FRP** means Fire Radiative Power (MW), the instantaneous radiative intensity of the detected source. A detection is neither a unique wildfire nor a mapped burned-area footprint. The dataset retains urban/industrial detections. Missing district codes are filled only when the supplied district name and governorate unambiguously match the district reference table; the original code is retained in `district_pcode_original`. The optional conflict-period filter removes records flagged `south_conflict_period = True` (823 records in the unfiltered source). This flag does not prove the cause of an ignition. Hover labels show acquisition **date**, not time.

**Fire-attributed forest loss (2001–2025):** Derived from the University of Maryland GLAD **Fire GFL** 30 m forest-cover-loss raster. The original raster separates non-fire disturbance (code 1) from fire-related loss confidence classes. In the workflow used for these supplied CSVs, **lower** = code 4 (high-certainty), **central** = codes 3 + 4 (medium + high), and **upper** = codes 2 + 3 + 4 (low + medium + high). The annual national, governorate, district and subdivision CSVs represent **central mapped fire-attributed loss**, not all-cause loss. These are raster-derived area estimates; they are not a census of individual fire incidents. The national lower/central/upper totals cover 2001–2025. See [UMD GLAD Fire GFL](https://www.glad.geog.umd.edu/dataset/Fire_GFL/).

**Filters and exceptions:** Year and governorate selections affect fire detections and local forest-loss comparisons. VIIRS confidence and the conflict-period exclusion affect **only VIIRS detections**; they do not change the forest-loss raster estimates. The **national forest-loss chronology** intentionally shows all years from 2001 to 2025 for historical context, highlighting the selected period; the **forest-loss KPI** uses the national series when all governorates are selected, otherwise the sum of selected districts for the selected years; the **national full-period lower/central/upper estimates** remain fixed for all Lebanon, 2001–2025.

**Weather aggregation:** Daily observations at five reference sites are first aggregated into a site-month. Site-month temperature, humidity and wind are averages of available daily measurements; precipitation is the sum of daily precipitation within the month. Then the five site-month values are **averaged equally** to obtain one monthly Lebanon-reference value. Thus the plotted monthly rainfall is the **average site total**, not the sum of rainfall over five sites or a Lebanon-wide rainfall volume. Weather is not measured at each fire location; the correlations are descriptive and subject to seasonality and spatial mismatch.

**Spatial comparison:** Fire detections are joined to fire-attributed forest loss by official district code. District maps use supplied GeoJSON administrative boundaries. Forest-loss chronology is shown by governorate. The subdivision bubble map uses representative subdivision coordinates, not locations of individual loss pixels. No causal claim or one-to-one conversion from VIIRS detections to forest-loss hectares is made.

**Uncertainty:** The national lower/central/upper figures come from raster classification thresholds corresponding to sample-based uncertainty bounds in the Fire GFL methodology. They should not be presented as independently estimated confidence intervals for individual districts, years or selected filters. Lebanon lies outside Africa; the source also defines a separate code 5 for African fire loss.""")
        nt=national.Forest_Loss_ha.sum();dt=distloss.Forest_Loss_ha.sum()
        st.write(f'**Reconciliation:** national annual total = {nt:,.4f} ha; district annual total = {dt:,.4f} ha; difference = {nt-dt:+.4f} ha. Original values have not been adjusted.')
        st.write('**District-code validation:**',{'repaired_missing_fire_district_codes':repaired_district_codes,'remaining_unmatched_fire_codes':unknown_fire,'unmatched_geo_names':unknown_geo})
        st.write('**Source files:**',', '.join(sorted(p.name for p in DATA.iterdir() if p.is_file())))

st.divider()
st.caption('Lebanon Is Burning · AUB MSBA data visualization project · Data: NASA FIRMS VIIRS, supplied forest-loss datasets, weather reference sites, administrative boundaries and fire stations. Basemap © OpenStreetMap / CARTO.')
