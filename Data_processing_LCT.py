#!/usr/bin/env python
# coding: utf-8

# In[1]:


import pandas as pd
import geopandas as gpd
import numpy as np
import openpyxl
import ast
from shapely import geometry
import h3
import folium
from numpy.random import randint, uniform
import json


# # Предобработка исходных данных 

# ### Переход от зидов к сотам

# In[2]:


# Данные по местам жительства, работы и перемещения населения
matr_zid = pd.read_csv('D:/ЛЦТ/исходные данные/04_CMatrix_Home_Work_July.csv')
matr_adm = pd.read_csv('D:/ЛЦТ/исходные данные/04_Matrix_Home_Work_July.csv')
zids = gpd.read_file('D:/ЛЦТ/исходные данные/fishnet2021/fishnet2021/fishnet2021.shp')
admin = gpd.read_file('D:/ЛЦТ/исходные данные/admzones2021/admzones2021/admzones2021.shp')
popul_zid = pd.read_csv('D:/ЛЦТ/исходные данные/01_CLocation_July.csv')
popul_adm = pd.read_csv('D:/ЛЦТ/исходные данные/01_Location_July.csv')


# In[15]:


# Получение границ территории исследования - новая Москва + старая Москва
admin_msc1 = admin.loc[admin.sub_ter == 'Старая Москва']
admin_msc1 = admin_msc1.reset_index(drop=True)
admin_msc2 = admin.loc[admin.sub_ter == 'Новая Москва']
admin_msc2 = admin_msc2.reset_index(drop=True)
admin_msc = pd.concat([admin_msc1, admin_msc2], axis = 0)
admin_msc = admin_msc.reset_index(drop=True)
admin_msc['dis'] = 1
admin_msc = admin_msc.dissolve(by = 'dis')
admin_msc = admin_msc.reset_index(drop=True)
admin_msc['buf'] = admin_msc.buffer(0.001)
admin_msc_l = []
admin_msc_l.append(admin_msc)
admin_msc = pd.DataFrame({'geometry':admin_msc_l})
admin_msc = gpd.GeoDataFrame(admin_msc, geometry = admin_msc.buf, crs = {'init':'epsg:32637'})
city = geometry.Polygon([(admin_msc.bounds.minx[0], admin_msc.bounds.miny[0]),
                          (admin_msc.bounds.minx[0], admin_msc.bounds.maxy[0]), 
                          (admin_msc.bounds.maxx[0], admin_msc.bounds.maxy[0]), 
                          (admin_msc.bounds.maxx[0], admin_msc.bounds.miny[0])])
city_l = []
city_l.append(city)
city = gpd.GeoDataFrame({'geometry':city_l})


# In[14]:


# Получение жилых домов с OSM
houses = gpd.read_file('D:/ЛЦТ/исходные данные/shape/buildings.shp')
houses_sel = gpd.sjoin(houses, admin_msc, op = 'within')
houses_sel = houses_sel.reset_index(drop=True)
houses_sel = gpd.GeoDataFrame(houses_sel,  crs = {'init':'epsg:4326'})
houses_sel = houses_sel.to_crs('epsg:32637')
houses_sel['area'] = houses_sel.geometry.area
houses_sel = houses_sel.to_crs('epsg:4326')
houses_sel = houses_sel[['geometry', 'area']]
liv = houses.loc[houses['type'] == 'apartments']
liv = liv.reset_index(drop=True)


# In[190]:


# Выборка зидов по границе города
zids_sel = gpd.sjoin(zids, admin_msc, op = 'within')
zids_sel = zids_sel.reset_index(drop=True)
zids_sel = gpd.GeoDataFrame(zids_sel)
zids_sel = zids_sel.join(popul_zid.set_index('zid'), on = 'cell_zid')
zids_sel = zids_sel.reset_index(drop=True)
zids_sel = zids_sel.dropna()
zids_sel = zids_sel.reset_index(drop=True)
zids_sel = zids_sel[['cell_zid', 'geometry', 'customers_cnt_home', 'customers_cnt_job', 'customers_cnt_day', 'customers_cnt_move']]


# In[69]:


# Получение сот h3 на город
city_j = ast.literal_eval(city.to_json())
h3_hexes = h3.polyfill_geojson(city_j['features'][0]['geometry'], 9) 

h3_cells = []
for h3_hex in h3_hexes:
    h3_cells.append(geometry.Polygon(h3.h3_to_geo_boundary(h3_hex,geo_json=True)))

h3_cells_id = []
for i in range(0,len(h3_cells)):
    h3_cells_id.append(i)
h3_cells = pd.DataFrame({'cell_id':h3_cells_id, 'geometry':h3_cells})

h3_cells = gpd.GeoDataFrame(h3_cells, geometry = h3_cells.geometry, crs = {'init':'epsg:4326'})
h3_cells_sel = gpd.sjoin(h3_cells, admin_msc, op = 'within')
h3_cells_sel = h3_cells_sel.reset_index(drop=True)
h3_cells_sel = gpd.GeoDataFrame(h3_cells_sel)
h3_cells_sel = h3_cells_sel[['cell_id', 'geometry']]


# In[226]:


# Преобразование домов OSM из полигонов в точки
x = []
y = []
for i in range(0, len(houses_sel)):
    x.append(houses_sel.geometry[i].centroid.x)
    y.append(houses_sel.geometry[i].centroid.y)
xy = pd.DataFrame({'x':x,'y':y})
houses_sel = pd.concat([houses_sel, xy], axis = 1)
houses_sel = houses_sel.drop(columns = ['geometry'])
houses_sel = gpd.GeoDataFrame(houses_sel, crs = {'init': 'epsg:4326'}, geometry=gpd.points_from_xy(houses_sel['x'], houses_sel['y']))


# In[229]:


# Переход от зидов к сотам пропорционально площади домов 
h3_cells_sel_house = gpd.sjoin(h3_cells_sel, houses_sel, op = 'contains')
h3_cells_sel_house = h3_cells_sel_house.groupby('cell_id', as_index = False).agg({'area': 'sum', 
                                                                    'geometry': 'first'})
h3_cells_sel_house = gpd.GeoDataFrame(h3_cells_sel_house, geometry = h3_cells_sel_house.geometry, crs = {'init':'epsg:4326'})
x = []
y = []

for i in range(0, len(h3_cells_sel_house)):
    x.append(h3_cells_sel_house.geometry[i].centroid.x)
    y.append(h3_cells_sel_house.geometry[i].centroid.y)
xy = pd.DataFrame({'x':x,'y':y})
h3_cells_sel_house_poi = pd.concat([h3_cells_sel_house, xy], axis = 1)
h3_cells_sel_house_poi = h3_cells_sel_house_poi.drop(columns = ['geometry'])
h3_cells_sel_house_poi = gpd.GeoDataFrame(h3_cells_sel_house_poi, crs = {'init': 'epsg:4326'}, geometry=gpd.points_from_xy(h3_cells_sel_house_poi['x'], h3_cells_sel_house_poi['y']))

sj = gpd.sjoin(h3_cells_sel_house_poi, zids_sel, op='within')
sj = sj.reset_index(drop=True)
home = []
job = []
cell_id = []
for i in list(set(sj.cell_zid)):
    sj_sel = sj.loc[sj.cell_zid == i]
    sj_sel = sj_sel.reset_index(drop=True)
    for k in range(0, len(sj_sel)):
        h = sj_sel.customers_[k]*(sj_sel['area'][k]/sum(sj_sel['area'])) + sj_sel.customer_2[k]*(sj_sel.customers_[k]/(sj_sel.customers_[k]+sj_sel.customer_1[k]))/len(sj_sel)
        home.append(h)
        j = sj_sel.customer_1[k]*(sj_sel['area'][k]/sum(sj_sel['area'])) + sj_sel.customer_2[k]*(sj_sel.customer_1[k]/(sj_sel.customers_[k]+sj_sel.customer_1[k]))/len(sj_sel)
        job.append(j)
        cell_id.append(sj_sel.cell_id[k])
df = pd.DataFrame({'cell_id':cell_id, 'home':home})
h3_cells_sel = df.join(h3_cells_sel.set_index('cell_id'), on='cell_id')
h3_cells_sel = h3_cells_sel.reset_index(drop=True)
h3_cells_sel = gpd.GeoDataFrame(h3_cells_sel, geometry = df.geometry, crs = {'init':'epsg:4326'})


# ### Получение итогового датафрейма школ

# In[2]:


# Загрузка данных по образовательным учреждениям с портала data.mos
edu = pd.read_excel('D:/ЛЦТ/исходные данные/datamos/Объекты образования.xlsx')


# In[64]:


# Предобработка школ с портала data.mos
schools = edu.loc[edu.OrgType == 'общеобразовательная организация']
schools = schools.reset_index(drop=True)
ShortName_cor = []
PublicPhone_cor = []
email_cor = []
NumberofStudentsInOO_cor = []
X = []
Y = []
for i in range(0, len(schools)):
    if pd.isna(schools.TheContingentOfPreschoolersStudyingOO[i]) == False:
        ShortName_cor.append(schools.ShortName[i]+' (c дошкольным отделением)')
    else:
        ShortName_cor.append(schools.ShortName[i])
    if pd.isna(schools.PublicPhone[i]) == False:
        PublicPhone_cor.append(schools.PublicPhone[i][12:len(schools.PublicPhone[i])-2]) 
    else:
        PublicPhone_cor.append('-') 
    if pd.isna(schools.Email[i]) == False:
        email_cor.append(schools.Email[i][6:len(schools.Email[i])-2]) 
    else:
        email_cor.append('-') 
    if pd.isna(schools.NumberofStudentsInOO[i]) == False:
        NumberofStudentsInOO_cor.append(int(schools.NumberofStudentsInOO[i][15:len(schools.NumberofStudentsInOO[i])-18]))
    else:
        NumberofStudentsInOO_cor.append('-') 
    coords = schools.geodata_center[i][16:len(schools.geodata_center[i])-17]
    coords = coords.split(',')
    X.append(float(coords[0]))
    Y.append(float(coords[1]))
    
schools = schools.drop(columns = ['ShortName', 'PublicPhone', 'Email', 'NumberofStudentsInOO', 'TheContingentOfPreschoolersStudyingOO', 'geodata_center'])
fields_cor = pd.DataFrame({'ShortName':ShortName_cor, 'PublicPhone':PublicPhone_cor, 'Email':email_cor, 
                           'NumberofStudentsInOO':NumberofStudentsInOO_cor, 'X':X, 'Y':Y})
schools = pd.concat([schools, fields_cor], axis = 1)
schools = gpd.GeoDataFrame(schools, crs = {'init': 'epsg:4326'}, geometry=gpd.points_from_xy(schools['X'], schools['Y']))
schools.to_excel('D:/ЛЦТ/предобработанные данные/schools.xlsx', index = False)


# In[31]:


# Связь с данными по школам с Яндекс.Недвижимость и получение итогового датафрейма
school_yan = school_yan[['name', 'address', 'latitude', 'longitude', 'ratingPlace']]
schools_num = []
for i in range(0, len(schools)):
    num = ''
    for j in range(0, len(schools.ShortName[i])):
        try: 
            num = num+str(int(schools.ShortName[i][j]))
        except ValueError:
            num = num
    schools_num.append(num)
schools_num = pd.DataFrame({'school_num':schools_num})
schools = pd.concat([schools, schools_num], axis = 1)
school_yan_num = []
for i in range(0, len(school_yan)):
    num = ''
    for j in range(0, len(school_yan.name[i])):
        try: 
            num = num+str(int(school_yan.name[i][j]))
        except ValueError:
            num = num
    school_yan_num.append(num)
school_yan_num = pd.DataFrame({'school_num':school_yan_num})
school_yan = pd.concat([school_yan, school_yan_num], axis = 1)
schools_final = school_yan.join(schools.set_index('school_num'), on = 'school_num')
schools_final = schools_final.reset_index(drop=True)
schools_final = schools_final[['name', 'address', 'latitude', 'longitude', 'ratingPlace', 'ChiefName', 'WebSite',
                              'PublicPhone', 'Email', 'NumberofStudentsInOO']]
school_yan = school_yan.replace({'':'0'})
pupils_cnt = []
name = []
for i in list(set(schools_final['name'])):
    schools_final_sel = schools_final.loc[schools_final['name'] == i]
    schools_final_sel = schools_final_sel.reset_index(drop=True)
    for j in range(0, len(schools_final_sel)):
        name.append(i)
        pupils_cnt.append(schools_final_sel.NumberofStudentsInOO[0]/len(schools_final_sel))
df = pd.DataFrame({'name':name, 'pupils_cnt':pupils_cnt})
df2 = df.fillna(675)
df2 = df2.reset_index(drop=True)
schools_final = schools_final.join(df2.set_index('name'), on = 'name')
schools_final = schools_final.reset_index(drop=True)
df2 = df2.groupby('name', as_index = False).agg({'pupils_cnt': 'first'})
df2 = df2.reset_index(drop=True)
schools_final = schools_final.drop(columns = ['NumberofStudentsInOO'])


# # Проведение исследования

# ### Алгоритм 1 - Вычисление потенциала размещения

# #### Оценка нагрузки на школы

# In[ ]:


schools = pd.read_excel('D:/ЛЦТ/schools.xlsx')
schools = gpd.GeoDataFrame(schools, crs = {'init': 'epsg:4326'}, geometry=gpd.points_from_xy(schools['longitude'], schools['latitude']))
schools_id = []
for i in range(0, len(schools)):
    schools_id.append(i)
schools_id = pd.DataFrame({'id':schools_id})
schools = pd.concat([schools, schools_id], axis = 1)
school_id = []
people_cnt = []
for i in range(0, len(cells)):
    buf = cells.geometry[i].centroid.buffer(800)    
    b = schools.within(buf)
    n = b.to_numpy()
    schools_sel = schools.iloc[n]
    schools_sel = schools_sel.reset_index(drop=True)
    dists = []
    for j in range(0, len(schools_sel)):
        dists.append(cells.geometry[i].centroid.distance(schools_sel.geometry[j]))
        school_id.append(schools_sel.id[j])
    xs = []
    for j in dists:
        xs.append((800 - j)/(800 - max(dists)))
    x = cells.home_5year[i]/sum(xs)
    popul_distrib = x*np.asarray(xs)
    for k in list(popul_distrib):
        people_cnt.append(k)
        
schools_nagr = pd.DataFrame({'school_id':school_id, 'people_cnt':people_cnt})
schools_nagr = schools_nagr.groupby('school_id', as_index = False).agg({'people_cnt': 'sum'})
schools_nagr = schools_nagr.reset_index(drop=True)

schools = schools.join(schools_nagr.set_index('school_id'), on = 'id')
schools = schools.reset_index(drop=True)
schools['spros'] = schools['people_cnt']/10
schools['nagruzka'] = schools['spros']/schools['pupils_cnt'] 


# #### Вычисление потребности населения в дополнительных местах

# In[ ]:


dop_mesta = []
for i in range(0, len(schools)):
    if schools.nagruzka[i] > 1:
        dop_mesta.append((schools.nagruzka[i] - 1)*schools.pupils_cnt[i])
    else:
        dop_mesta.append(0)
dop_mesta = pd.DataFrame({'dop_mesta':dop_mesta})
schools = pd.concat([schools, dop_mesta], axis = 1)

cell_id = []
dop_potreb = []
for i in range(0,len(schools)):    
    b = cells.geometry.centroid.within(schools.geometry[i].buffer(800))
    n = b.to_numpy()
    cells_sel = cells.iloc[n]
    cells_sel = cells_sel.reset_index(drop=True)
    for j in range(0, len(cells_sel)):
        cell_id.append(cells_sel.cell_id[j])
        dop_potreb.append(schools.dop_mesta[i]/len(cells_sel))
df = pd.DataFrame({'cell_id':cell_id, 'dop_potreb':dop_potreb})

df = df.groupby('cell_id', as_index = False).agg({'dop_potreb': 'sum'})
df = df.reset_index(drop=True)

cells = cells.join(df.set_index('cell_id'), on = 'cell_id')
cells = cells.reset_index(drop=True)

potreb = []
for i in range(0, len(cells)):
    if pd.isna(cells.dop_potreb[i]) == True:
        potreb.append(cells.home[i]/10)
    else:
        potreb.append(cells.dop_potreb[i])
potreb = pd.DataFrame({'potreb':potreb})
cells = pd.concat([cells, potreb], axis = 1)


# #### Определение потенциала

# In[ ]:


new_school_nagr = []
for i in range(0,len(cells)):
    b = cells.geometry.within(cells.geometry.centroid[i].buffer(800))
    n = b.to_numpy()
    cells_sel = cells.iloc[n]
    cells_sel = cells_sel.reset_index(drop=True) 
    new_school_nagr.append(sum(cells_sel.potreb_5ye))
    
new_school_nagr = pd.DataFrame({'potential':new_school_nagr})
cells = pd.concat([cells, new_school_nagr], axis = 1)


# ### Алгоритм 2 - Моделирование спроса будущего

# #### Рост за счет новостроек

# In[ ]:


novostroy_msc = novostroy_msc[['Name','lat', 'lng', 'Квартир', 'Класс', 'Этажность','Сдача']]
num_flats = []
end = []
floors = []
for i in range(0, len(novostroy_msc)):
    end.append(int(novostroy_msc['Сдача'][i][0]))
    try:
        num_str = novostroy_msc['Квартир'][i][0].split(sep='+', maxsplit=-1)
        num_int = []
        for j in range(0, len(num_str)):
            try:
                num_int.append(int(num_str[j]))
            except ValueError:
                num_int.append(235)
        num_flats.append(sum(num_int))    
    except TypeError:
        num_flats.append(novostroy_msc['Квартир'][i])


# In[ ]:


num_flats = pd.DataFrame({'num_flats':num_flats, 'end':end})
novostroy_msc = pd.concat([novostroy_msc, num_flats], axis = 1)
novostroy_msc = novostroy_msc.fillna(760)


# In[ ]:


cells_novostroy = gpd.sjoin(cells, novostroy, op = 'contains')
cells_novostroy = cells_novostroy.reset_index(drop=True)
cells_novostroy = cells_novostroy.groupby('cell_id', as_index = False).agg({'num_flats': 'sum'})
cells_novostroy['popul'] = cells_novostroy['num_flats']*2.6
cells_novostroy = cells_novostroy[['cell_id', 'popul']]
cells = cells.join(cells_novostroy.set_index('cell_id'), on = 'cell_id')
cells = cells.reset_index(drop=True)


# #### Рост за счет реновации

# In[ ]:


renov2 = gpd.GeoDataFrame(renov2_df, crs = {'init': 'epsg:4326'}, geometry=gpd.points_from_xy(renov2_df['lng'], renov2_df['lat'])) 
living = gpd.read_file('J:/everpoint/2GIS_data/living/Москва.shp')
ren_num = []
total_num = []
for i in range(0, len(cells)):
    b = renov2['geometry'].within(cells1['geometry'][i])
    n = b.to_numpy()
    renov2_sel = renov2.iloc[n]
    renov2_sel = renov2_sel.reset_index(drop=True) 
    ren_num.append(len(renov2_sel))
    
    b = living['geometry'].within(cells1['geometry'][i])
    n = b.to_numpy()
    living_sel = living.iloc[n]
    living_sel = living_sel.reset_index(drop=True) 
    total_num.append(len(living_sel))
    
df = pd.DataFrame({'ren_num':ren_num, 'total_num':total_num})
cells = pd.concat([cells, df], axis = 1)

popul_add = []
for i in range(0, len(cells)):
    if cells.total_num[i] > 0:
        popul_add.append(((cells.ren_num[i]/cells.total_num[i]*cells.home[i]/2)*1.5-(cells.ren_num[i]/cells.total_num[i]*cells.home[i])/2)*0.9)
    else:
        popul_add.append(0)
        
popul_add = pd.DataFrame({'popul_add':popul_add})
cells = pd.concat([cells, popul_add], axis = 1)
cells=cells.drop(columns = ['popul_add'])
cells['home_5year'] = cells['home_5year'] + cells['popul_add']

