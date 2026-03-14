from setting_for_sdm.path_setting import path_list
from setting_for_sdm.date_setting import Date_Setting
from setting_for_sdm.excel import excel
import pandas as pd
import os


class RunnerOptions:
    def __init__(self, mode, run_id, dict_): 
        self.user_opt       = None

        self.chk_opt(mode, run_id,  dict_)
        self.set_opt(mode, run_id, dict_)

    def chk_opt(self, mode, run_id, dict_) : 
        
        # year_range chk
        list_ = list(Date_Setting.keys())

        file_path = f"{path_list['data_root_dir']}/result/annotate_difficulty"    
        
        if dict_['q_src_yn'] == "Y":
            file_path = f'{file_path}/q_output_code_y'
        
        file_path = f'{file_path}{excel[dict_["excel_ver"]]}.csv'

        if not os.path.isfile(file_path):
            raise ValueError(f"There's no annotated file. Please save the annotated file to {file_path}")
        

        

    def set_opt(self, mode, run_id, dict_) : 
        if mode == "experiment":
            self.user_opt = {
                                    "run_id": run_id,
                                    "save_dir": f"{path_list['data_root_dir']}/result/annotate_difficulty/{mode}",    
                                    "selected_tags": None,
                                    "experiment_option" : dict_
                                    
                        }

        else :
            self.user_opt = {
                                    "run_id": run_id,
                                    "save_dir": f"{path_list['data_root_dir']}/result/annotate_difficulty/run_id_{run_id}",    
                                    "selected_tags": None,
                                    "experiment_option" : dict_
                        }
        