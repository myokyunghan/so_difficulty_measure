import os 
import multiprocessing as mp
import pandas as pd
import numpy as np
from setting_for_sdm.constants import CONSTANTS
from lib.annotation.tools.VLLM import VLLM
from lib.annotation.tools.loghander import *
from tqdm import tqdm
from transformers import AutoTokenizer
import re
import random

def chk_max_length(message, tk):
    prompt = tk.apply_chat_template(
        message,
        tokenize=False,
        add_generation_prompt=True
    )
    prompt_tokens = len(tk.encode(prompt))

    MAX_CONTEXT = tk.model_max_length
    MAX_GENERATION = 256
    SAFETY_MARGIN = 128

    tot_promt_tk = prompt_tokens + MAX_GENERATION + SAFETY_MARGIN
    return (tot_promt_tk > MAX_CONTEXT)


def get_annotation_data(annotation_file_path):
    file_path = annotation_file_path
    return pd.read_csv(f'{file_path}')


def set_fewshot_example_for_exp(df, eval_q_id, few_shot_n): 
    diff_idx = {x : np.setdiff1d(list(df[df['answer']==x].id), [eval_q_id]) for x in list(CONSTANTS.DIFF_DICT.values())}

    fewshot_q_list = []
    for key, pool in diff_idx.items():
        samples = np.random.choice(pool, size=few_shot_n, replace=False)
        fewshot_q_list.extend(samples.tolist())

    random.shuffle(fewshot_q_list) 
    return fewshot_q_list

def set_fewshot_example_for_op(df, few_shot_n):
    diff_idx = {x : list(df[df['answer']==x].id) for x in list(CONSTANTS.DIFF_DICT.values())}
    
    fewshot_q_list = []
    for key, value in diff_idx.items():
        diff_population = value
        fewshot_q_list.append(np.random.choice(diff_population, size=few_shot_n, replace=False))
    return_ = np.concatenate(fewshot_q_list).tolist()
    random.shuffle(return_)
    return return_

def select_eval_q(df, test_n):
    # to evaluate self-consistency, pick eval target first
    # hard coding for test :  eval_q_id_list = [71389500]

    eval_q_id_list      = np.random.choice(list(df.id), size=test_n, replace=False)
    return eval_q_id_list


def select_fewshot_for_e(df, eval_q_id_list, few_shot_n, sc_num, test_n):

    diff_s_idx = {}
    for eval_q_id in eval_q_id_list:
        diff_s_idx[eval_q_id] = dict()
        for sf_idx in range(sc_num):
            fewshot_q_list = set_fewshot_example_for_exp(df, eval_q_id, few_shot_n)
            diff_s_idx[eval_q_id][sf_idx] = fewshot_q_list

    return diff_s_idx


def get_result_df(eval_df, q_id):
    if eval_df.empty:
        return False
    else : 
        # logger.info(f">>>>>>>>>>>>>>>get_result_df shape of dataset! {self.result_df[self.result_df['id'] == q_id].shape[0]}")
        return (np.where(eval_df[eval_df['id'] == q_id].shape[0]>0, True, False)) 


# def random_selection(df, few_shot_n, target_q, sc_num):
    
#     diff_s_idx = {}
#     diff_s_idx[target_q] = dict()
#     for sf_idx in range(sc_num):
#         diff_s_idx[target_q][sf_idx] = set_fewshot_example_for_exp(df, target_q, few_shot_n)
#     return diff_s_idx

def random_selection(df, few_shot_n, annoate_target, sc_num):

    diff_s_idx = {}
    target_q_list = annoate_target.id

    for target_q in target_q_list:
        diff_s_idx[target_q] = dict()
        for sf_idx in range(sc_num):
            diff_s_idx[target_q][sf_idx] = set_fewshot_example_for_op(df, few_shot_n)
    return diff_s_idx

def write_prompt_exp(golden_df, e_f_dict, few_shot_n, sys_prompt, tk):
    logger         = get_logger()
    message_list = []

    for eval_id, fewshot_dict in e_f_dict.items():
        for sc_idx, fewshot_id_list in fewshot_dict.items():

            while True:
                message = []
                message.append({"role": "system", "content": sys_prompt})

                for fewshot_id in fewshot_id_list:

                    q_string = golden_df.loc[golden_df['id']    == fewshot_id, 'question'].iloc[0]
                    a_string = golden_df.loc[golden_df['id']    == fewshot_id, 'answer'].iloc[0]
                    t_string = golden_df.loc[golden_df['id']    == eval_id, 'question'].iloc[0]

                    q_prompt = ("\nHere is the examples of question.\n" 
                                "\n<Example>\n"
                                + q_string + "\n</Example>\n"
                                )

                    message.append({"role": "user", "content": q_prompt})
                    message.append({"role": "assistant", "content": a_string})

                target_post = (
                    "\nHere is the target post. Answer the \"Difficulty Level\".\n"
                    "\n<Target_post>\n"
                    + t_string + "\n</Target_post>\n"
                )

                message.append({"role": "user", "content": target_post})

                if chk_max_length(message, tk):
                    # 다시 샘플링
                    fewshot_id_list = set_fewshot_example_for_exp(golden_df, eval_id, few_shot_n)
                else:
                    message_list.append({
                                                "eval_id": eval_id,
                                                "message": message
                                            })
                    break

    return message_list


def write_prompt_op(golden_df, annoate_target, e_f_dict, few_shot_n, sys_prompt, tk):
    logger         = get_logger()
    message_list = []

    for eval_id, fewshot_dict in e_f_dict.items():
        for sc_idx, fewshot_id_list in fewshot_dict.items():

            while True:
                message = []
                message.append({"role": "system", "content": sys_prompt})

                for fewshot_id in fewshot_id_list:

                    q_string = golden_df.loc[golden_df['id']    == fewshot_id, 'question'].iloc[0]
                    a_string = golden_df.loc[golden_df['id']    == fewshot_id, 'answer'].iloc[0]
                    t_string = annoate_target.loc[annoate_target['id']==eval_id, 'question'].iloc[0]

                    q_prompt = ("\nHere is the examples of question.\n" 
                                "\n<Example>\n"
                                + q_string + "\n</Example>\n"
                                )

                    message.append({"role": "user", "content": q_prompt})
                    message.append({"role": "assistant", "content": a_string})

                target_post = (
                    "\nHere is the target post. Answer the \"Difficulty Level\".\n"
                    "\n<Target_post>\n"
                    + t_string + "\n</Target_post>\n"
                )

                message.append({"role": "user", "content": target_post})

                if chk_max_length(message, tk):
                    # 다시 샘플링
                    fewshot_id_list = set_fewshot_example_for_op(golden_df, few_shot_n)
                else:
                    message_list.append({
                                                "eval_id": eval_id,
                                                "message": message
                                            })
                    break

    return message_list



def calc_acc_for_v(vllm, message_list):
    
    batch_size = 15
    result = []
    

    for i in tqdm(range(0, len(message_list), batch_size)):
        batch = message_list[i:i+batch_size]
        
        messages_batch = [item["message"] for item in batch]
        eval_ids = [item["eval_id"] for item in batch]

        
        responses = vllm.llm.chat(messages_batch, sampling_params=vllm.params)
        # self.logger.info(f'VLLM batch end!')

        for eval_id, response in zip(eval_ids, responses):
            result.append([eval_id, response.outputs[0].text])

    return pd.DataFrame(result, columns=['id', 'result_long'])


def chk_eval_df(r_df, q_id):
    r_df['result'] = r_df['result_long'].apply(lambda x: int(m.group(1)) if (m := re.search(r'<Difficulty Level>\s*(\d)\s*', x)) else None)
    unique_eval = r_df.loc[r_df['id'] == q_id, 'result'].unique()

    return True if len(unique_eval) == 1 else False
        
        
        # result_df = pd.merge(annoate_target[['ver', 'creationdate', 'id']], r_df, on='id')
        # result_df.to_csv(f'{self.save_dir}/{self.date}_{q_id}.csv')

def select_eval_q(df, test_n):
    # to evaluate self-consistency, pick eval target first
    # hard coding for test :  eval_q_id_list = [71389500]

    eval_q_id_list      = np.random.choice(list(df.id), size=test_n, replace=False)
    return eval_q_id_list