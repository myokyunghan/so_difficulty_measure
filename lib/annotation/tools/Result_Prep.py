import pandas as pd
import numpy as np
from datetime import datetime
import os
import re

class Result_Prep: 
    
    def make_one_file(self, ver, path=f'/home/mghan/sopjt/git/stackoverflow_src/LLM/result/'):

        file_list = os.listdir(f'{path}/{ver}')
        df = pd.DataFrame()
        if len(file_list)>0 : 
            for f in file_list:
                if f'{path}/{ver}/{f}'.endswith('.csv'):
                    tmp = pd.read_csv(f'{path}/{ver}/{f}', index_col =0)
                    df = pd.concat([df, tmp], axis =0)

            df.sort_values(by = ['creationdate']).reset_index(drop=True)
            return df
        else :
            return np.nan

    def pp_df(self, df, sc_num):
        df_copy = df.copy()
        df_copy['creationdate'] = pd.to_datetime(df_copy['creationdate'])
        df_copy.sort_values(by = ['creationdate'], ascending = True, inplace=True)
        df_copy.loc[:, 'rel_day'] = df_copy.loc[:,  'creationdate'] - datetime(2022,11,30)
        df_copy.loc[:, 'rel_days'] = df_copy.loc[:, 'rel_day'].dt.days

        df_c = df.copy()
        df_c = df_c[~df_c['result'].isna()]
        df_c['o_result'] = df_c['result'].apply(lambda x : re.sub(r'[^0-9]', '', x))
        df_c = df_c[df_c['o_result'].isin(['1', '0', '2'])]
        
        df_c.loc[:, 'cnt'] = 1
        chk_cnt = df_c.groupby(['id', 'o_result']).count().reset_index()[['id', 'o_result', 'cnt']]
        chk_cnt = chk_cnt[chk_cnt['cnt'] == sc_num]


        m_chk_cnt = pd.merge(chk_cnt, df_copy, on = 'id')
            
        return m_chk_cnt
    

    def calc_rate(self, df):
        df_c = df.copy()
        df_c = df_c[['ver', 'creationdate', 'id', 'o_result', 'rel_days']].drop_duplicates()
        df_c.loc[:, 'r_cnt'] = 1
        
        df_c = df_c.groupby(['ver', 'creationdate', 'rel_days', 'o_result']).count().reset_index()[['ver', 'creationdate', 'rel_days'	,'o_result',	'r_cnt']]
        tot_df = df_c.groupby(['ver', 'creationdate', 'rel_days']).sum().reset_index()[['creationdate', 'r_cnt']].rename(columns = {'r_cnt':'tot_cnt'})

        return_df = pd.merge(df_c, tot_df, on = 'creationdate' )

        return_df['rate'] = return_df['r_cnt']/return_df['tot_cnt']*100
        return_df = return_df.sort_values(by = ['creationdate'])

        return return_df
    
    def calc_rate_byweek(self, df):
        df_c = df.copy()
        df_c = df_c[['ver', 'creationdate', 'id', 'o_result', 'rel_days']].drop_duplicates()
        
        df_c['rel_week'] = np.floor(df_c['rel_days']/7)
        df_c.loc[:, 'r_cnt'] = 1
        
        df_c = df_c.groupby(['rel_week' ,'o_result']).count().reset_index()[['rel_week', 'o_result',	'r_cnt']]
        tot_df = df_c.groupby(['rel_week']).sum().reset_index()[['rel_week', 'r_cnt']].rename(columns = {'r_cnt':'tot_cnt'})

        return_df = pd.merge(df_c, tot_df, on = 'rel_week' )

        return_df['rate'] = return_df['r_cnt']/return_df['tot_cnt']*100
        return_df = return_df.sort_values(by = ['rel_week'])

        return return_df
    
            
    def pp_date(self, df):
        df = df.sort_values(by = ['creationdate'])
        df_date = df[['creationdate']].drop_duplicates().reset_index(drop=True)
        return df_date
            

    

