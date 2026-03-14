
from lib.annotation.tools.VLLM import VLLM
from setting_for_sdm.prompt import prompt
from run_project.annotate_difficulty.options import RunnerOptions
import logging
import pandas as pd
from tqdm import tqdm
import os
# https://github.com/meta-llama/llama-recipes/blob/main/recipes/quickstart/Prompt_Engineering_with_Llama_3.ipynb
class Annotation_Experiment:

    def __init__(self, experiment_option):  

        # init variables
        self.df             = pd.DataFrame()
        self.eval_prompt    = []
        self.result         = []
        self.message_list   = []
        self.eval_q_list    = []

        # param
        self.test_n         = experiment_option['test_n']
        self.sys_prompt     = prompt[experiment_option['prompt_ver']] 
        self.p_ver          = experiment_option['prompt_ver']
        self.iternum        = experiment_option['test_n']
        self.sc_num         = experiment_option['sc_num']
        self.temperature    = experiment_option['temperature']
        self.excel_ver      = experiment_option['excel_ver']
        self.loop_i         = experiment_option['loop_num']
        self.tk             = AutoTokenizer.from_pretrained(conf.VLLM_CONF[llm_model][model_name]['model'], use_fast=True)
        
        self.logger         = get_userlogger()
        self.logger.setLevel(logging.INFO)
        
        self.logger.info(f'param for sample self consistency : {llm_model} | {model_name} | {few_shot_n} | {q_src_yn} | {p_ver} | {sc_num} | {temperature} | {excel_ver}' )
        
        self.save_dir = f'{conf.DATA_PATH}{conf.ANNO_RESULT}/{model_name}'
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)  

        self.save_file = f'sc_{llm_model}_result_{few_shot_n}_{self.test_n}_{q_src_yn}_{self.iternum}_{self.p_ver}_{self.sc_num}_{self.temperature}_{self.excel_ver}_{self.loop_i}'
        self.logger.info(f'save file to     : {self.save_dir}/{self.save_file}.csv')
        self.logger.info(f'save config to   : {self.save_dir}/{self.save_file}_llm_config.json')

        self.init_process(q_src_yn, test_n, few_shot_n, llm_model, model_name)

  

    def init_process(self, q_src_yn, test_n, few_shot_n, llm_model, model_name):
        # init the process
        self.set_environment()
        self.get_annotation_data(q_src_yn)

        eval_q_id_list = self.select_eval_q(test_n)
        e_f_dict = self.select_fewshot_for_e(eval_q_id_list, few_shot_n, test_n)

        self.write_prompt(e_f_dict, few_shot_n)
        
        self.calc_acc(llm_model, few_shot_n, q_src_yn, model_name)


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
        # self.logger.info(f'>>>>>>>>>>>>>>>! Self_Consistency re chk_max_length : {tot_promt_tk} / {MAX_CONTEXT}')
        return (tot_promt_tk > MAX_CONTEXT)

            
    def get_annotation_data(self, q_src_yn):
        file_path = f'{conf.DATA_PATH}/data/q_output'
        
        if q_src_yn == "Y":
            file_path = f'{file_path}_code_y'
        
        file_path = f'{file_path}{excel[self.excel_ver]}'
        self.df = pd.read_csv(f'{file_path}.csv')

    def chg_fewshot_example(self, few_shot_n, pool, eval_q_id):
        list_ = []
        adv_n = few_shot_n - conf.FEWSHOT_BOUNDARY_N
        adv_samples = np.random.choice(pool, size=adv_n, replace=False)
        boundary_pool = np.setdiff1d(conf.BOUND_POOL, adv_samples)
        boundary_pool = np.setdiff1d(conf.BOUND_POOL, [eval_q_id])

        if len(boundary_pool) < conf.FEWSHOT_BOUNDARY_N :
            self.logger.info(f'>>>>>>>>>>>>>>>! Self_Consistency re boundary_pool len is less than {conf.FEWSHOT_BOUNDARY_N}!! check boundary_pool {boundary_pool}')
            samples = np.random.choice(pool, size=few_shot_n, replace=False)
            list_.extend(samples.tolist())
        else : 
            
            boundary_samples = np.random.choice(
                boundary_pool,
                size=conf.FEWSHOT_BOUNDARY_N,
                replace=False
            )
            list_.extend(adv_samples.tolist())
            list_.extend(boundary_samples.tolist())
        return list_

    def set_fewshot_example(self, eval_q_id, few_shot_n): 
        diff_idx = {x : np.setdiff1d(list(self.df[self.df['answer']==x].id), [eval_q_id]) for x in list(conf.DIFF_DICT.values())}

        fewshot_q_list = []
        for key, pool in diff_idx.items():
            # if key == conf.BOUND_KEY :
            #     samples = self.chg_fewshot_example(few_shot_n, pool, eval_q_id)
            #     fewshot_q_list.extend(samples)
                
            # else : 
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

    def chk_leftover(self, result_df):
        self.logger.info(f'>>>>>>>>>>>>>>>chk_leftover start!')
        tmp = result_df.copy()
        tmp['gold'] = tmp['answer'].apply(lambda x : re.sub(r'[^012]', '', x))
        tmp['o_result'] = tmp['result'].apply(lambda x : re.sub(r'[^012]', '', x))
        tmp = tmp[tmp['o_result'].isin(['1', '0', '2'])]

        
        gold_df = tmp[['id', 'gold']].drop_duplicates()
        chk_cnt = tmp.groupby(['id', 'o_result']).count().reset_index()[['id', 'o_result', 'question']]
        chk_cnt = chk_cnt.rename(columns = {'question': 'sc_cnt'})
        leftover_list = list(chk_cnt.loc[chk_cnt['sc_cnt'] != sc_num, 'id'])
        
        return leftover_list


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
        file_io.save_json(conf.VLLM_CONF[llm_model], f'{self.save_dir}/{self.save_file}_llm_config.json')
        self.logger.info(f'>>>>>>>>>>>>>>>calc_acc_for_v end!')
        return self.chk_leftover(result_df)



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
        file_io.save_json(conf.VLLM_CONF[llm_model], f'{self.save_dir}/{self.save_file}_llm_config.json')

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
        file_io.save_json(conf.VLLM_CONF[llm_model], f'{self.save_dir}/{self.save_file}_llm_config.json')

        


    def calc_acc(self, llm_model, few_shot_n, q_src_yn, model_name) :
        if llm_model == 'l' : # ollama 
            # print(self.eval_prompt)
            self.ollama         = 'llama-3.1-70b-instruct-lorablated.Q4_K_M:latest'
            self.calc_acc_for_l(llm_model, few_shot_n, q_src_yn)
            

        elif llm_model == 'c' : # chatgpt 
            # print(self.eval_prompt)
            self.chatgpt        = OpenAI(api_key= conf.OEPN_AI_KEY)
            self.calc_acc_for_c(llm_model, few_shot_n, q_src_yn)

        elif llm_model == 'vl' : # vLLM + llama
            print("VLLM")
            self.vllm = VLLM(llm_model, model_name)
            self.calc_acc_for_v(llm_model, few_shot_n, q_src_yn)

        
        elif llm_model == 'vq' : # vLLM + qwen
            print("VLLM")
            self.vllm = VLLM(llm_model, model_name)

            leftover_list = self.calc_acc_for_v(llm_model, few_shot_n, q_src_yn)
            return leftover_list

# def test(llm_model, model_ver, few_shot_n, test_n, q_src_yn, ver, p_ver, sc_num, temperature, excel_ver):
#     print(f"Test {llm_model}_{few_shot_n}_{test_n}_{q_src_yn}_{p_ver}_{sc_num} 시작")
#     for i in range(ver):
#         print(f"Test {llm_model}_{model_ver}_{few_shot_n}_{test_n}_{q_src_yn}_{p_ver}_{sc_num} 실행 중: {i}")
#         Self_Consistency_re(   llm_model
#                             , model_ver
#                             , few_shot_n
#                             , test_n
#                             , q_src_yn
#                             , ver
#                             , p_ver
#                             , sc_num
#                             , temperature
#                             , excel_ver
#                             , i)
    
#     print(f"Task {llm_model}_{model_ver}_{few_shot_n}_{test_n}_{q_src_yn}_{p_ver}_{sc_num} 완료")

# if __name__ == "__main__":


    # test ('vl',              # llm_model
    #     'models--kosbu--Llama-3.3-70B-Instruct-AWQ',         # model_ver
    #     4,                # few_shot_n
    #     30,                # test_n(# of question for test)
    #     'Y',              # q_src_yn 
    #     10,                # iteration num
    #     'sys_prompt13',   # prompt ver
    #     5,                # self-consistency number
    #     0.01,             # temperature
    #     'ver7'            # excel_verion
    #     )



    # test ('vq',              # llm_model
    #     'models--cyankiwi--Qwen3-30B-A3B-Instruct-2507-AWQ-4bit',         # model_ver
    #     4,                # few_shot_n
    #     50,                # test_n(# of question for test)
    #     'Y',              # q_src_yn 
    #     10,                # iteration num
    #     'sys_prompt10',   # prompt ver
    #     5,                # self-consistency number
    #     0.01,             # temperature
    #     'ver7'            # excel_verion
    #     )


#    test ('vq',              # llm_model
#         'models--cyankiwi--Qwen3-30B-A3B-Instruct-2507-AWQ-4bit',         # model_ver
#         4,                # few_shot_n
#         30,                # test_n(# of question for test)
#         'Y',              # q_src_yn 
#         10,                # iteration num
#         'sys_prompt10',   # prompt ver
#         5,                # self-consistency number
#         0.01,             # temperature
#         'ver7'            # excel_verion
#         )



    # test ('vl',              # llm_model
    #     3,                # few_shot_n
    #     100,                # test_n(# of question for test)
    #     'Y',              # q_src_yn 
    #     50,                # iteration num
    #     'sys_prompt10',   # prompt ver
    #     5,                # self-consistency number
    #     0.01,             # temperature
    #     'ver7'            # excel_verion
    #     )

    # test ('vl',              # llm_model
    #         1,                # few_shot_n
    #         1,                # test_n(# of question for test)
    #         'Y',              # q_src_yn 
    #         1,                # iteration num
    #         'sys_prompt10',   # prompt ver
    #         1,                # self-consistency number
    #         0.01,             # temperature
    #         'ver7'            # excel_verion
    #         )
