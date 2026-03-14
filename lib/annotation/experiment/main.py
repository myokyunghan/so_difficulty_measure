import os
from lib.database.DBInterface import DBInterface
from setting_for_sdm.date_setting import Date_Setting
from setting_for_sdm.path_setting import path_list
from lib.utils.file_io import save_json, create_dir
from run_project.annotate_difficulty.options import RunnerOptions
from lib.annotation.experiment.annotation_experiment import Annotation_Experiment

class ModelRunner:

    def __init__(self, runner_opt):
        self.db_interface = DBInterface()
        self.runner_opt = runner_opt

        self.save_length = 10000
        self.lang = self.runner_opt.user_opt['selected_tags']
        self.save_dir = self.runner_opt.user_opt['save_dir']



    def __call__(self):
        self.run()

    def run(self):
        self.run_experiment(self.runner_opt.user_opt)
        self.save_option()
        
    def run_experiment(self, user_opt) :
        experiment_option = user_opt['experiment_option']
        print(f">>>>>>>Experiment Start<<<<<<<<{experiment_option['llm_model']}_{experiment_option['few_shot_n']}_{experiment_option['test_n']}_{experiment_option['q_src_yn']}_{experiment_option['prompt_ver']}_{experiment_option['sc_num']}")
        for i in range(experiment_option['iteration_num']):
            print(f"Test {i} Running: ")
            user_opt['experiment_option']['loop_num'] = i
            exp = Annotation_Experiment(user_opt)
            exp()
        
        print(f">>>>>>>Experiment Start<<<<<<<<{experiment_option['llm_model']}_{experiment_option['few_shot_n']}_{experiment_option['test_n']}_{experiment_option['q_src_yn']}_{experiment_option['prompt_ver']}_{experiment_option['sc_num']}")


    def save_option(self):
        """

        Returns:
            None
        """
        save_json(self.runner_opt.user_opt, f'{self.save_dir}/option.json')
        print(f"[Saving data...] Saved to runner option to {self.save_dir}/option.json")

## for test
if __name__ == '__main__':
    runner = ModelRunner()
    runner()
