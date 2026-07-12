import pandas as pd
import numpy as np
from datetime import datetime
import os
import re
from setting_for_sdm.path_setting import path_list
from lib.utils.file_io import *

class Result_Prep: 
    def __init__(self, target_idx) : 

        self.viz_dir = f'{path_list["data_root_dir"]}/result/annotate_difficulty/run_id_{target_idx}'
        self.data_dir = f"{self.viz_dir}/data/csv"

        self.option_dict = load_json(f"{self.viz_dir}/option.json")
        self.output_dir = create_dir('./fig/')
        self.date_range = 'Weekly'

        self.path = f"{self.viz_dir}/{self.option_dict['operation_option']['llm_model']}"
        self.file_list = os.listdir(self.path)
        self.ver_list = sorted([y for y in [x for x in self.file_list if x.isdigit()]])

    
    def data_prep(self) : 
        tot_calc = pd.DataFrame()
        for listid in self.ver_list:
            df = self.make_one_file(listid, self.path)
            if isinstance(df, pd.core.frame.DataFrame):
                df = self.pp_df(df, 5)
                if df.shape[0] >0 :  
                    tot_calc = pd.concat([tot_calc, df], axis = 0)
        
        return_ = self.calc_rate_byweek(tot_calc)
        
        return return_
    

    def data_concat(self) : 
        tot_calc = pd.DataFrame()
        for listid in self.ver_list:
            df = self.make_one_file(listid, self.path)
            if isinstance(df, pd.core.frame.DataFrame):
                tot_calc = pd.concat([tot_calc, df], axis = 0)
        return tot_calc

    
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
            

    

