from pathlib import Path
import json
import pandas as pd
import numpy as np
P=Path(__file__).resolve().parent/'Final data used'
f=pd.read_csv(P/'fires_viirs_2012_2025.csv',parse_dates=['acq_date'])
d=pd.read_csv(P/'Lebanon_Districts_Annual.csv');g=pd.read_csv(P/'Lebanon_Governorates_Annual.csv');n=pd.read_csv(P/'Lebanon_Annual_Forest_Loss.csv');sub=pd.read_csv(P/'Lebanon_Subdivisions_Annual.csv');w=pd.read_csv(P/'weather_daily_2012_2025.csv',parse_dates=['date'])
geo=json.loads((P/'districts.geojson').read_text())
assert len(f)==7811 and len(d)==26*25 and len(g)==8*25 and len(n)==25
assert f.duplicated().sum()==0
assert (f.acq_date.dt.year==f.year).all() and (f.acq_date.dt.month==f.month).all()
assert len(f[(f.year==2024)&(f.month==10)])==497
assert len(f[(f.year==2024)&(f.month==11)])==50
assert f.south_conflict_period.sum()==823
assert len(geo['features'])==26
assert not d.duplicated(['District_Code','Year']).any()
assert set(x['properties']['district'] for x in geo['features'])==set(d.District)
assert set(f.district_pcode.dropna())==set(d.District_Code)
assert len(f[f.district_pcode.isna()])==15
lk=d[['Governorate','District','District_Code']].drop_duplicates().set_index(['Governorate','District'])['District_Code']
for row in f[f.district_pcode.isna()].itertuples():assert (row.governorate,row.district) in lk.index
f['district_pcode']=f.apply(lambda r:lk.loc[(r.governorate,r.district)] if pd.isna(r.district_pcode) else r.district_pcode,axis=1)
assert f.district_pcode.notna().all()
for gov in d.Governorate.unique():
 codes=set(d.loc[d.Governorate==gov,'District_Code'])
 assert set(f.loc[f.governorate==gov,'district_pcode']).issubset(codes)
assert np.isclose(n.Forest_Loss_ha.sum(),3180.625)
assert np.isclose(n[n.Year.between(2012,2025)].Forest_Loss_ha.sum(),2670.5625)
assert np.isclose(d.Forest_Loss_ha.sum(),3180.375)
assert np.isclose(g.Forest_Loss_ha.sum(),d.Forest_Loss_ha.sum())
assert np.isclose(sub.Forest_Loss_ha.sum(),d.Forest_Loss_ha.sum())
assert w.site.nunique()==5 and w.groupby('site').size().nunique()==1
counts=f.groupby(['district_pcode','year']).size().rename('Fire detections').reset_index().rename(columns={'district_pcode':'District_Code','year':'Year'})
panel=d.merge(counts,on=['District_Code','Year'],how='left',validate='one_to_one')
assert int(panel['Fire detections'].fillna(0).sum())==len(f)
monthly=f.groupby(['year','month']).size().unstack(fill_value=0).reindex(index=range(2012,2026),columns=range(1,13),fill_value=0)
assert int(monthly.loc[2024,10])==497 and int(monthly.loc[2024,11])==50
assert int(monthly.to_numpy().sum())==len(f)
print('PASS: 7,811 fire records, 15 safely recovered district codes, all 26 districts, 8 governorates, 25 forest years, 5 weather sites')
print('PASS: 2024 October=497, November=50, all month/year cells sum to 7,811')
print('PASS: district-year joined fire counts sum to 7,811')
print('PASS: forest totals national 3180.625 ha; districts/governorates/subdivisions 3180.375 ha; source difference 0.25 ha')
