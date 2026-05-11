from setting_for_sdm.constants import CONSTANTS
from lib.code_complexity.main import ModelRunner
from run_project.calculate_src_complexity.options import RunnerOptions

def run_model(lang, gap) : 
    run_id_start = 20000
    lang_list = list(CONSTANTS.LANG_INFO.keys())
    lang_index = lang_list.index(lang)
    print('Running for language: ', lang)
    print(run_id_start + lang_index)
    runner_opt = RunnerOptions( "real",
                                "2020to2025", # year_range (22to24, 21to23)
                                run_id_start +lang_index, # run_id 
                                lang,
                                "public_for_260105", # snapshot(snapshot1, snapshot2)
                                "cyclomatic_complexity"
    )
    runner = ModelRunner(runner_opt)
    runner()
    print('End Running for language: ', lang)


def run_model(gap) : 
    run_id_start = 20000
    lang_list = list(CONSTANTS.LANG_INFO.keys())

    for lang_index, lang in enumerate(lang_list):
        print('Running for language: ', lang)
        print(run_id_start + lang_index)
        runner_opt = RunnerOptions( "real",
                                    "2020to2025", # year_range (22to24, 21to23)
                                    run_id_start +lang_index, # run_id 
                                    lang,
                                    "public_for_260105", # snapshot(snapshot1, snapshot2)
                                    "cyclomatic_complexity"
        )
        runner = ModelRunner(runner_opt)
        runner()
        print('End Running for language: ', lang)
     
if __name__ == "__main__":

    # run_model(args.param1)
    run_model(gap=0)
    