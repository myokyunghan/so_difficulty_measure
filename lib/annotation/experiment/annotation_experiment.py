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
class Annotation_Experiment:

    def __init__(self, user_option):  

        # init variables
        self.df             = pd.DataFrame()
        self.eval_prompt    = []
        self.result         = []
        self.message_list   = []
        self.eval_q_list    = []

        # param
        experiment_option   = user_option['experiment_option']
        self.annotation_file_path = user_option['annotation_file_path']
        self.llm_model   = experiment_option['llm_model']
        self.model_name  = experiment_option['model_ver']
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
        
        self.logger         = get_userlogger(user_option['log_dir'])
        self.logger.setLevel(logging.INFO)
        
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
        self.get_annotation_data()
        eval_q_id_list = self.select_eval_q(self.test_n)
        e_f_dict       = self.select_fewshot_for_e(eval_q_id_list, self.few_shot_n, self.test_n)
        self.write_prompt(e_f_dict, self.few_shot_n)
        self.calc_acc()


    def set_environment(self):
        os.environ["VLLM_USE_CUDA_GRAPH"] = "0"
        os.environ["NCCL_P2P_DISABLE"] = "1"
        os.environ["NCCL_IB_DISABLE"] = "1"

        mp.set_start_method("spawn", force=True)

    def chk_max_length(self, message):
        prompt = self.tk.apply_chat_template(
            message,
            tokenize=False,
            add_generation_prompt=True
        )
        prompt_tokens = len(self.tk.encode(prompt))

        MAX_CONTEXT = self.tk.model_max_length
        MAX_GENERATION = 256
        SAFETY_MARGIN = 128

        tot_promt_tk = prompt_tokens + MAX_GENERATION + SAFETY_MARGIN
        return (tot_promt_tk > MAX_CONTEXT)

            
    def get_annotation_data(self):
        file_path = self.annotation_file_path
        self.df = pd.read_csv(f'{file_path}')


    def set_fewshot_example(self, eval_q_id, few_shot_n): 
        diff_idx = {x : np.setdiff1d(list(self.df[self.df['answer']==x].id), [eval_q_id]) for x in list(CONSTANTS.DIFF_DICT.values())}

        fewshot_q_list = []
        for key, pool in diff_idx.items():
            samples = np.random.choice(pool, size=few_shot_n, replace=False)
            fewshot_q_list.extend(samples.tolist())


        self.logger.info(f'>>>>>>>>>>>>>>>! Self_Consistency re set_fewshot_example {fewshot_q_list}')
        return fewshot_q_list


    def select_eval_q(self, test_n):
        # to evaluate self-consistency, pick eval target first
        # hard coding for test :  eval_q_id_list = [71389500]

        eval_q_id_list      = np.random.choice(list(self.df.id), size=test_n, replace=False)
        return eval_q_id_list

    def select_fewshot_for_e(self, eval_q_id_list, few_shot_n, test_n):

        diff_s_idx = {}
        for eval_q_id in eval_q_id_list:
            diff_s_idx[eval_q_id] = dict()
            for sf_idx in range(self.sc_num):
                fewshot_q_list = self.set_fewshot_example(eval_q_id, few_shot_n)
                diff_s_idx[eval_q_id][sf_idx] = fewshot_q_list

        return diff_s_idx
            

    def write_prompt(self, e_f_dict, few_shot_n) : 
        
        # write system prompt & examples
        for eval_id, fewshot_dict in e_f_dict.items() : 
    
            for sc_idx, fewshot_id_list in fewshot_dict.items() : 
                message = []
                message.append({"role": "system", "content": self.sys_prompt})
                self.eval_q_list.append(eval_id)

                for fewshot_id in fewshot_id_list : 
                    

                    q_string = self.df.loc[self.df['id'] == fewshot_id, 'question'].iloc[0]
                    a_string = self.df.loc[self.df['id'] == fewshot_id, 'answer'].iloc[0]
                    t_string = self.df.loc[self.df['id'] == eval_id,    'question'].iloc[0]

                    q_prompt = """\nHere is the examples of question\n"""
                    q_prompt = q_prompt + q_string
                    
                    message.append({"role": "user", "content": q_prompt})
                    message.append({"role": "assistant", "content": a_string})
                
                target_post="""\nHere is the target post. Answer the "Difficulty Level".\n"""
                target_post = target_post+"""\n<target_post>\n"""
                target_post = target_post+t_string+'\n'
                target_post = target_post+"""</target_post>\n"""
    
                message.append({"role": "user", "content": target_post})
                
                if self.chk_max_length(message) :
                    e_f_dict[eval_id][sc_idx] = self.set_fewshot_example(eval_id, few_shot_n)
                    self.write_prompt(e_f_dict, few_shot_n)
                else :
                    self.message_list.append(message)


    def calc_acc_for_v(self, llm_model, few_shot_n, q_src_yn):
        self.logger.info(f'>>>>>>>>>>>>>>>calc_acc_for_v start!')
        self.logger.info(f'>>>>>>>>>>>>>>>calc_acc_for_v, load VLLM!')
        for idx, message in tqdm(enumerate(self.message_list)):
            tmp = []
            response = self.vllm.llm.chat(message, sampling_params=self.vllm.params) 

            tmp.append(self.eval_q_list[idx])
            tmp.append(response[0].outputs[0].text)
            self.result.append(tmp)
        result_df = pd.DataFrame(self.result, columns = ['id', 'result'])
        result_df = pd.merge(self.df, result_df, on = 'id')
        
        self.logger.info(f'>>>>>>>>>>>>>>>calc_acc_for_v savefile! {self.save_dir}/{self.save_file}.csv')
        result_df.to_csv(f'{self.save_dir}/{self.save_file}.csv')
        file_io.save_json(vllm_setting[llm_model], f'{self.save_dir}/{self.save_file}_llm_config.json')
        self.logger.info(f'>>>>>>>>>>>>>>>calc_acc_for_v end!')



    def calc_acc_for_l(self, llm_model, few_shot_n, q_src_yn):           
        for idx, message in tqdm(enumerate(self.message_list)):
            tmp = []
            response = chat( model      = self.ollama,
                            messages    = message,
                            )
            tmp.append(self.eval_q_list[idx])
            tmp.append(message)
            tmp.append(response['message']['content'])
            self.result.append(tmp)
        result_df = pd.DataFrame(self.result, columns = ['id', 'message', 'result'])
        result_df = pd.merge(self.df, result_df, on = 'id')

        self.logger.info(f'>>>>>>>>>>>>>>>calc_acc_for_l savefile! {self.save_dir}/{self.save_file}.csv')
        result_df.to_csv(f'{self.save_dir}/{self.save_file}.csv')
        file_io.save_json(vllm_setting[llm_model], f'{self.save_dir}/{self.save_file}_llm_config.json')

    def calc_acc_for_c(self, llm_model, few_shot_n, q_src_yn):
        for idx, message in tqdm(enumerate(self.message_list)):
            tmp = []
            MODEL = "gpt-4o"
            response = self.chatgpt.chat.completions.create(
                model=MODEL,
                messages=message,
                temperature= self.temperature,
            )
            tmp.append(self.eval_q_list[idx])
            tmp.append(message)
            tmp.append([response.choices[0].message.content])
            self.result.append(tmp)
        result_df = pd.DataFrame(self.result, columns = ['id', 'message', 'result'])
        result_df = pd.merge(self.df, result_df, on = 'id')
        self.logger.info(f'>>>>>>>>>>>>>>>calc_acc_for_c savefile! {self.save_dir}/{self.save_file}.csv')
        result_df.to_csv(f'{self.save_dir}/{self.save_file}.csv')
        file_io.save_json(vllm_setting[llm_model], f'{self.save_dir}/{self.save_file}_llm_config.json')

        

    def calc_acc(self):
        if self.llm_model == 'l':
            self.ollama = 'llama-3.1-70b-instruct-lorablated.Q4_K_M:latest'
            self.calc_acc_for_l()

        elif self.llm_model == 'c':
            self.chatgpt = OpenAI(api_key=OEPN_AI_KEY)
            self.calc_acc_for_c()

        elif self.llm_model in ('vl', 'vq'):
            self.vllm = VLLM(self.llm_model, self.model_name)
            self.calc_acc_for_v()
           