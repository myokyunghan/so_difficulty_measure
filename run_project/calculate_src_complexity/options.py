from setting_for_sdm.path_setting import path_list
from setting_for_sdm.date_setting import Date_Setting
class RunnerOptions:
    def __init__(self, mode, year_range, run_id, language, snapshot, metric='cognitive_complexity'): 
        self.user_opt       = None

        self.chk_opt(mode, year_range, run_id, language, snapshot, metric)
        self.set_opt(mode, year_range, run_id, language, snapshot, metric)

    def chk_opt(self, mode, year_range, run_id, language, snapshot, metric):
        
        # year_range chk
        list_ = list(Date_Setting.keys())
        if mode == "test":
            return
        if year_range not in (year_range):
            raise ValueError(f"We now offer only three options ({year_range}) for 'year_range' parameter.\n If you want to add options, please modify 'settings_for_sda.constants.py'")
        
        # snapshot chk
        print("snapshot", snapshot)
        if snapshot not in (["snapshot1", "snapshot2", "snapshot3", "public_for_260105"]):
            raise ValueError("We now offer only three options (snapshot1, snapshot2, snapshot3) for 'snapshot' parameter.\n If you want to add options, please modify 'settings_for_sda.constants.py'")
        
        # metric chk
        if metric not in (["cognitive_complexity", "cyclomatic_complexity", "rust_cognitive_complexity"]):
            raise ValueError("We now offer only three options (cognitive_complexity, cyclomatic_complexity, rust_cognitive_complexity) for 'metric' parameter.\n If you want to add options, please modify 'settings_for_sda.constants.py'")

    def set_opt(self, mode, year_range, run_id, language, snapshot, metric):
        if mode == "test":
            self.user_opt = {
                                    "run_id": run_id,
                                    "year_range" : year_range,
                                    "data_dir": f"{path_list['data_root_dir']}/data/{snapshot}/questions/test",    
                                    "save_dir": f"{path_list['data_root_dir']}/result/code_complexity/{metric}/test",    
                                    "selected_tags": language,
                                    "snapshot": f"{snapshot}",
                                    "metric": f"{metric}"
                        }

        else :
            self.user_opt = {
                                    "run_id": run_id,
                                    "year_range" : year_range,
                                    "data_dir": f"{path_list['data_root_dir']}/data/{snapshot}/questions/{language}/{year_range}",    
                                    "save_dir": f"{path_list['data_root_dir']}/result/code_complexity/{metric}/run_id_{run_id}",    
                                    "selected_tags": language,
                                    "snapshot": f"{snapshot}",
                                    "metric": f"{metric}"
                        }
        