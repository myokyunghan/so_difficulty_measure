import pandas as pd
import numpy as np
from datetime import datetime
import os
import re
from setting_for_sdm.path_setting import path_list
from lib.utils.file_io import *
from setting_for_sdm.date_setting import Date_Setting

class Result_Prep: 
    def __init__(self, target_idx) : 

        self.src_dir = f'{path_list["data_root_dir"]}/result/code_complexity/cyclomatic_complexity/run_id_{target_idx}'

        self.option_dict = load_json(f"{self.src_dir}/data/option.json")
        self.std_date = Date_Setting[self.option_dict['year_range']]['std_date']

    
    def data_prep(self) : 
        origin_df = load_df(self.option_dict['data_dir'], ['id', 'creationdate', 'title','tags', 'body'])

        df = read_complexity_jsonl(self.option_dict)
        df['cyclomatic_complexity'] = np.log1p(df['cyclomatic_complexity'])

        viz_df = pd.merge(df, origin_df, on = 'id')[['id', 'creationdate', 'cyclomatic_complexity', 'nloc']]
        viz_df['rel_week'] = np.floor((pd.to_datetime(viz_df['creationdate'], format='mixed')- self.std_date).dt.days/7)
        viz_df = (viz_df.groupby('rel_week', as_index=False)['cyclomatic_complexity'].mean())

        return viz_df
    

    def data_prep_for_all(self, lang) : 
        origin_df = load_df(self.option_dict['data_dir'], ['id', 'creationdate', 'title','tags', 'body'])
        df = read_complexity_jsonl(self.option_dict)
   
        tot_viz_df = pd.merge(df, origin_df, on = 'id')[['id', 'creationdate', 'cyclomatic_complexity', 'nloc']]
        tot_viz_df['rel_week'] = np.floor((pd.to_datetime(tot_viz_df['creationdate'], format='mixed')- self.std_date).dt.days/7).astype(int)
        tot_viz_df['week'] = pd.to_datetime(tot_viz_df['creationdate'], format='mixed').dt.to_period('W').dt.start_time

        
        tot_viz_df['log_cc'] = np.log1p(tot_viz_df['cyclomatic_complexity'])
        tot_viz_df['language'] = lang
        

        return tot_viz_df

    def data_prep_for_its(self, tot_viz_df) : 
        valid = tot_viz_df['language'].value_counts()[lambda s: s >= 1000].index
        df = tot_viz_df[tot_viz_df['language'].isin(valid)].copy()
        
        weekly = df.groupby(['language', 'rel_week']).agg(
            log_cc_mean = ('log_cc', 'mean'),
            n_func      = ('cyclomatic_complexity', 'count'),
        ).reset_index()
        
        weekly = weekly[weekly['n_func'] >= 30].copy()

        return weekly
