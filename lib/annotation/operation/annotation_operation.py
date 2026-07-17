from transformers import AutoTokenizer
from openai import OpenAI
from ollama import chat
from transformers import AutoTokenizer

from lib.annotation.tools.VLLM import VLLM
from lib.annotation.tools.loghander import *
from lib.annotation.annotation_func import * 

from setting_for_sdm.prompt import prompt
from setting_for_sdm.llm_setting import (vllm_setting, ollama_setting)
from setting_for_sdm.excel import excel
from setting_for_sdm.constants import CONSTANTS
from setting_for_sdm.config import OEPN_AI_KEY


from run_project.annotate_difficulty.options import RunnerOptions
import lib.utils.file_io as file_io
import lib.database.DBInterface as db_interface



import logging
import pandas as pd
import numpy as np
from tqdm import tqdm
import os
import multiprocessing as mp
import re
# https://github.com/meta-llama/llama-recipes/blob/main/recipes/quickstart/Prompt_Engineering_with_Llama_3.ipynb
class Annotation_Operation:
    def __init__(self, annoate_target, user_option, vllm=None):  
        self.ollama         = ollama_setting['version']
        self.chatgpt        = OpenAI(api_key= OEPN_AI_KEY)
        self.vllm           = VLLM(self.llm_model, self.model_name) if vllm is None else vllm

        self.df             = pd.DataFrame()
        self.eval_prompt    = []
        self.result         = []
        self.message_list   = []

        # init param
        self.annoate_target = annoate_target.reset_index(drop=True)
        self.annoate_target['creationdate'] = pd.to_datetime(self.annoate_target['creationdate']).dt.date
        self.date           = annoate_target.iloc[0,1]
        self.ver            = int(annoate_target.iloc[0,0])

        # predefined param
        operation_option            = user_option['operation_option']
        self.annotation_file_path   = user_option['annotation_file_path']
        self.llm_model              = operation_option['llm_model']
        self.model_name             = operation_option['model_ver']
        self.few_shot_n             = operation_option['few_shot_n']
        self.q_src_yn               = operation_option['q_src_yn']
        self.sys_prompt             = prompt[operation_option['prompt_ver']]
        self.p_ver                  = operation_option['prompt_ver']
        self.sc_num                 = operation_option['sc_num']
        self.temperature            = operation_option['temperature']
        self.excel_ver              = operation_option['excel_ver']
        self.operation_option       = operation_option   # param.json 저장용

        self.tk                 = AutoTokenizer.from_pretrained(vllm_setting[self.llm_model][self.model_name]['model'], use_fast=True)
        self.save_dir           = f'{user_option["save_dir"]}/{self.llm_model}/{self.ver}'

        # log setting
        self.logger         = get_logger()
        
        self.logger.info(f'param for sample self consistency : {self.llm_model} | {self.few_shot_n} | {self.q_src_yn} | {self.sys_prompt} | {self.sc_num} | {self.temperature} | {self.excel_ver}' )
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)  

    def __call__(self):
        self.run()

    def run(self):
        self.logger.info('start get_annotation_data')
        self.golden_df  = get_annotation_data(self.annotation_file_path)
        self.logger.info(f'end get_annotation_data : {self.golden_df.shape}')

        self.logger.info('start random_selection')
        e_f_dict = random_selection(self.golden_df, self.few_shot_n, self.annoate_target, self.sc_num)
        self.logger.info('end random_selection')

        self.logger.info('start write_prompt')
        message_list = write_prompt_op(self.golden_df,self.annoate_target, e_f_dict, self.few_shot_n, self.sys_prompt, self.tk)
        self.logger.info('end write_prompt')

        self.logger.info('start calc_acc')
        r_df = self.calc_acc(message_list)
        self.logger.info('end calc_acc')

        self.logger.info(f'>>>>>>>>>>>>>>>! start set_eval_df/save_eval_df')
        self.save_result(r_df)
        self.logger.info(f'>>>>>>>>>>>>>>>! end set_eval_df/save_eval_df : {r_df.shape}')
        
    def chk_max_length(self, message):
        self.tk             = AutoTokenizer.from_pretrained(vllm_setting[self.llm_model][self.model_name]['model'], use_fast=True)
        prompt = self.tk.apply_chat_template(
            message,
            tokenize=False,
            add_generation_prompt=True
        )
        prompt_tokens = len(self.tk.encode(prompt))

        # MAX_CONTEXT = self.tk.model_max_length
        MAX_CONTEXT = self.tk.model_max_length if vllm_setting[self.llm_model][self.model_name]['max_model_len'] is None else vllm_setting[self.llm_model][self.model_name]['max_model_len']
        MAX_GENERATION = 256
        SAFETY_MARGIN = 128

        tot_prompt_tk = prompt_tokens + MAX_GENERATION + SAFETY_MARGIN

        if tot_prompt_tk > MAX_CONTEXT:
            return True
        else:
            return False


    def save_result(self, r_df):
        db_if = db_interface.DBInterface()
        
        result_df = pd.merge(self.annoate_target[['ver', 'creationdate', 'id']], r_df, on='id')

        # self.logger.info(f'save result! {self.save_dir}/{self.date}.csv')
        # result_df.to_csv(f'{self.save_dir}/{self.date}.csv')

        # result_df = result_df[['ver', 'creationdate', 'id']].drop_duplicates()

        data_list = [[int(x[1]), x[2], int(x[3]), x[4]] for x in result_df.to_records()]
        sql = 'INSERT INTO tt_post_python_difficulty_done  VALUES %s'
        db_if.execute_bulk_values(sql, data_list)  
           

    def calc_acc(self, message_list):
        if self.llm_model == 'l':
            self.ollama = 'llama-3.1-70b-instruct-lorablated.Q4_K_M:latest'
            self.calc_acc_for_l()

        elif self.llm_model == 'c':
            self.chatgpt = OpenAI(api_key=OEPN_AI_KEY)
            self.calc_acc_for_c()

        elif self.llm_model in ('vl', 'vq'):
            self.logger.info('start calc_acc_for_v')
            r_df =calc_acc_for_v(self.vllm, message_list)
            self.logger.info('end calc_acc_for_v')
        
        return r_df