from lib.annotation.experiment.main import ModelRunner
from run_project.annotate_difficulty.options import RunnerOptions


## for test
if __name__ == '__main__':

    runner_opt = RunnerOptions( "experiment", 
                            111, # run_id 
                            {
                                "llm_model"         : 'vq',              # llm_model
                                # "model_ver"         : 'models--cyankiwi--Qwen3-30B-A3B-Instruct-2507-AWQ-4bit',         # model_ver
                                "model_ver"         : 'models--Qwen--Qwen3-4B-Instruct-2507',         # model_ver
                                "few_shot_n"        : 4,                # few_shot_n
                                "test_n"            : 50,                # test_n(# of question for test)
                                "q_src_yn"          : 'Y',              # q_src_yn 
                                "iteration_num"     : 50,                # iteration num
                                "prompt_ver"        : 'sys_prompt10',   # prompt_ver
                                "sc_num"            : 5,                # sc_num
                                "temperature"       : 0.01,             # temperature
                                "excel_ver"         : 'ver8'            # excel_verion)
                            }
                            
    )
    runner = ModelRunner(runner_opt)
    runner()


# CUDA_VISIBLE_DEVICES=2,3 /home/mghan/sopjt/git/so_difficulty_measure/venv_so_difficulty_measure/bin/python /home/mghan/sopjt/git/so_difficulty_measure/run_project/annotate_difficulty/02_run_model/02_0_validation/validation.py