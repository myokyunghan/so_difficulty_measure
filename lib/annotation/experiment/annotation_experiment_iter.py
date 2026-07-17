from transformers import AutoTokenizer
from openai import OpenAI
from ollama import chat
from transformers import AutoTokenizer

from lib.annotation.tools.VLLM import VLLM
from lib.annotation.tools.loghander import *

from setting_for_sdm.prompt import prompt
from setting_for_sdm.llm_setting import vllm_setting
from setting_for_sdm.excel import excel
from setting_for_sdm.constants import CONSTANTS
from setting_for_sdm.config import OEPN_AI_KEY

from lib.annotation.annotation_func import * 


from run_project.annotate_difficulty.options import RunnerOptions
import lib.utils.file_io as file_io


import logging
import pandas as pd
import numpy as np
from tqdm import tqdm
import os
import multiprocessing as mp
import re
# https://github.com/meta-llama/llama-recipes/blob/main/recipes/quickstart/Prompt_Engineering_with_Llama_3.ipynb
class Annotation_Experiment_Iter:

    def __init__(self, user_option):  

        # init variables
        self.golden_df      = pd.DataFrame()
        self.eval_df        = pd.DataFrame()

        self.eval_prompt    = []
        self.result         = []
        self.message_list   = []
        self.eval_q_list    = []

        # param
        experiment_option   = user_option['experiment_option']
        self.annotation_file_path = user_option['annotation_file_path']
        self.llm_model   = experiment_option['llm_model']
        self.model_name  = experiment_option['model_ver']
        self.app_model   = None
        self.few_shot_n  = experiment_option['few_shot_n']
        self.test_n      = experiment_option['test_n']
        self.q_src_yn    = experiment_option['q_src_yn']
        self.sys_prompt  = prompt[experiment_option['prompt_ver']]
        self.p_ver       = experiment_option['prompt_ver']
        self.sc_num      = experiment_option['sc_num']
        self.temperature = experiment_option['temperature']
        self.excel_ver   = experiment_option['excel_ver']
        self.loop_i      = experiment_option['loop_num']
        
        

        self.tk             = AutoTokenizer.from_pretrained(vllm_setting[self.llm_model][self.model_name]['model'], use_fast=True)
        
        self.logger         = get_logger()
        
        
        self.logger.info(
            f'param: {self.llm_model} | {self.model_name} | '
            f'{self.few_shot_n} | {self.q_src_yn} | '
            f'{self.p_ver} | {self.sc_num} | '
            f'{self.temperature} | {self.excel_ver}'
        )
        
        self.save_dir = f'{user_option["save_dir"]}/run_id_{user_option["run_id"]}'
        self.save_file = (f'sc_{self.llm_model}_result_{self.few_shot_n}_'
                          f'{self.test_n}_{self.q_src_yn}_{self.test_n}_'
                          f'{self.p_ver}_{self.sc_num}_{self.temperature}_'
                          f'{self.excel_ver}_{self.loop_i}')
        
        os.makedirs(self.save_dir, exist_ok=True)

        self.logger.info(f'save file to     : {self.save_dir}/{self.save_file}.csv')
        

    def __call__(self):
        self.run()

    def run(self):
        self.set_environment()
        self.golden_df = get_annotation_data(self.annotation_file_path)
        eval_q_id_list = select_eval_q(self.golden_df, self.test_n)
        
        for q_id in eval_q_id_list : 
            while not get_result_df(self.eval_df, q_id) :
                self.logger.info(f'===================================================')
                self.logger.info(f'start random_selection for q_id: {q_id}')
                e_f_dict = random_selection(self.golden_df, self.few_shot_n,  q_id, self.sc_num)
                self.logger.info(f'end random_selection for q_id: {q_id}')

                self.logger.info(f'start write_prompt for q_id: {q_id}')
                message_list = write_prompt(self.golden_df, e_f_dict, self.few_shot_n, self.sys_prompt, self.tk)
                self.logger.info(f'end write_prompt for q_id: {q_id}')

                self.logger.info(f'start calc_acc for q_id: {q_id}')
                r_df = self.calc_acc(message_list)
                self.logger.info(f'end calc_acc for q_id: {q_id}')

                self.logger.info(f'start chk_eval_df for q_id: {q_id}')
                self.logger.info(f"""in the r_df: {r_df[['id', 'result_long']].head()}""")
                if chk_eval_df(r_df, q_id):
                    self.logger.info(f'If r_df is great')
                    self.set_eval_df(r_df)
                    break

                self.logger.info(f'end set_eval_df for q_id: {q_id}')      
                self.logger.info(f'===================================================')
      
        self.save_eval_df()
        # e_f_dict       = self.select_fewshot_for_e(eval_q_id_list, self.few_shot_n, self.test_n)
        # self.write_prompt(e_f_dict, self.few_shot_n)
        # self.calc_acc()


    def calc_acc(self, message_list):
        if self.llm_model == 'l':
            self.ollama = 'llama-3.1-70b-instruct-lorablated.Q4_K_M:latest'
            self.calc_acc_for_l()

        elif self.llm_model == 'c':
            self.chatgpt = OpenAI(api_key=OEPN_AI_KEY)
            self.calc_acc_for_c()

        elif self.llm_model in ('vl', 'vq'):
            self.logger.info('start calc_acc_for_v')
            r_df =calc_acc_for_v(self.app_model, message_list)
            self.logger.info('end calc_acc_for_v')
        
        return r_df
    

    def set_environment(self):
        # os.environ["VLLM_USE_CUDA_GRAPH"] = "0"
        # os.environ["NCCL_P2P_DISABLE"] = "1"
        # os.environ["NCCL_IB_DISABLE"] = "1"

        mp.set_start_method("spawn", force=True)
        
        if self.llm_model in ('vl', 'vq'):
            self.app_model = VLLM(self.llm_model, self.model_name)

 
    def set_eval_df(self, r_df):
        tmp = pd.merge(self.golden_df, r_df, on='id')
        self.eval_df = pd.concat([self.eval_df, tmp], axis = 0)

    def save_eval_df(self):
        self.logger.info(f'>>>>>>>>>>>>>>>calc_acc_for_c savefile! {self.save_dir}/{self.save_file}.csv')
        self.eval_df.to_csv(f'{self.save_dir}/{self.save_file}.csv')
        file_io.save_json(vllm_setting[self.llm_model], f'{self.save_dir}/{self.save_file}_llm_config.json')

        