from setting_for_sdm.constants import CONSTANTS
from lib.code_complexity.main import ModelRunner
from run_project.calculate_src_complexity.options import RunnerOptions

import argparse



def run_model(lang) : 
    run_id = 1000 + list(CONSTANTS.src_extend.keys()).index(lang)
    
    print('Running for language: ', lang)
    runner_opt = RunnerOptions( "real",
                                "2020to2025", # year_range (22to24, 21to23)
                                run_id, # run_id 
                                lang,
                                "public_for_260105" # snapshot(snapshot1, snapshot2),
    )
    runner = ModelRunner(runner_opt)
    runner()
    print('End Running for language: ', lang)


# def run_model(gap) : 
#     run_id_start = 1000+gap
#     lang_list = list(CONSTANTS.src_extend.keys())
#     for idx, lang in enumerate(lang_list[3:]):    
#         print('Running for language: ', lang)
#         runner_opt = RunnerOptions( "real",
#                                     "2020to2025", # year_range (22to24, 21to23)
#                                     run_id_start+idx, # run_id 
#                                     lang,
#                                     "public_for_260105" # snapshot(snapshot1, snapshot2),
#         )
#         runner = ModelRunner(runner_opt)
#         runner()
#         print('End Running for language: ', lang)




if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="이 프로그램은 파라미터를 처리합니다.")
    parser.add_argument("param1", type=str, help="")
    args = parser.parse_args()


    run_model(args.param1)
    # run_model(gap=3)
    