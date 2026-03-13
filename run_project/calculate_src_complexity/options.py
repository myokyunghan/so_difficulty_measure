from setting_for_sdm.path_setting import path_list
from setting_for_sdm.date_setting import Date_Setting
class RunnerOptions:
    def __init__(self, mode, year_range, run_id, snapshot): 
        self.user_opt       = None

        self.chk_opt(mode, year_range, run_id, snapshot)
        self.set_opt(mode, year_range, run_id, snapshot)

    def chk_opt(self, mode, year_range, run_id, snapshot):
        
        # year_range chk
        list_ = list(Date_Setting.keys())
        if mode == "test":
            return
        if year_range not in (year_range):
            raise ValueError(f"We now offer only three options ({year_range}) for 'year_range' parameter.\n If you want to add options, please modify 'settings_for_sda.constants.py'")
        
        # snapshot chk
        if snapshot not in (["snapshot1", "snapshot2", "snapshot3", "public_for_260105"]):
            raise ValueError("We now offer only three options (snapshot1, snapshot2, snapshot3) for 'snapshot' parameter.\n If you want to add options, please modify 'settings_for_sda.constants.py'")
        

    def set_opt(self, mode, year_range, run_id, snapshot):
        if mode == "test":
            self.user_opt = {
                                    "run_id": run_id,
                                    "year_range" : year_range,
                                    "data_dir": f"{path_list['data_root_dir']}/data/{snapshot}/questions",    
                                    "save_dir": f"{path_list['data_root_dir']}/result/code_complexity/test",    
                                    "selected_tags": None,
                                    "snapshot": f"{snapshot}",
                                    
                        }

        else :
            self.user_opt = {
                                    "run_id": run_id,
                                    "year_range" : year_range,
                                    "data_dir": f"{path_list['data_root_dir']}/data/{snapshot}/questions/python/{year_range}",    
                                    "save_dir": f"{path_list['data_root_dir']}/result/code_complexity/run_id_{run_id}",    
                                    "selected_tags": None,
                                    "snapshot": f"{snapshot}",
                                    
                        }
        