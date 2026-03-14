from lib.annotation.import_files import *
from lib.annotation.VLLM import VLLM
# https://github.com/meta-llama/llama-recipes/blob/main/recipes/quickstart/Prompt_Engineering_with_Llama_3.ipynb
class SampleSelf_Consistency_re:
    def __init__(self, annoate_target):  
        self.ollama         = 'llama-3.1-70b-instruct-lorablated.Q4_K_M:latest'
        self.chatgpt        = OpenAI(api_key= conf.OEPN_AI_KEY)

        self.df             = pd.DataFrame()
        self.eval_prompt    = []
        self.result         = []
        self.message_list   = []
        self.eval_q_list    = []

        # init param
        self.annoate_target = annoate_target.reset_index(drop=True)
        self.annoate_target['creationdate'] = pd.to_datetime(self.annoate_target['creationdate']).dt.date
        self.date           = annoate_target.iloc[0,1]
        self.ver            = int(annoate_target.iloc[0,0])

        # predefined param
        self.llm_model      = param['llm_model']
        self.model_ver      = param['model_ver']
        self.few_shot_n     = param['few_shot_n']
        self.q_src_yn       = param['q_src_yn']
        self.sys_prompt     = param['p_ver'] 
        self.sf_num         = param['sf_num']
        self.temperature    = param['temperature']
        self.excel_ver      = param['excel_ver']
        self.tk             = AutoTokenizer.from_pretrained(conf.VLLM_CONF[self.llm_model]['model'], use_fast=True)
        self.save_dir       = f'{conf.DATA_PATH}{conf.ANNO_RESULT}/{self.model_ver}/{self.ver}'
        
        # log setting
        self.logger         = get_userlogger()
        self.logger.setLevel(logging.INFO)
        
        self.logger.info(f'param for sample self consistency : {self.llm_model} | {self.few_shot_n} | {self.q_src_yn} | {self.sys_prompt} | {self.sf_num} | {self.temperature} | {self.excel_ver}' )
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)  

    def chk_max_length(self, message):
        self.tk             = AutoTokenizer.from_pretrained(conf.VLLM_CONF[self.llm_model]['model'], use_fast=True)
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
        q_src_yn = param['q_src_yn']
        file_path = f'{conf.DATA_PATH}/data/q_output'
        
        if q_src_yn == "Y":
            file_path = f'{file_path}_code_y'
        
        file_path = f'{file_path}{excel[self.excel_ver]}'
        self.df = pd.read_csv(f'{file_path}.csv')

    def set_fewshot_example(self, few_shot_n):
        diff_idx = {x : list(self.df[self.df['answer']==x].id) for x in list(conf.DIFF_DICT.values())}
        
        fewshot_q_list = []
        for key, value in diff_idx.items():
            diff_population = value
            fewshot_q_list.append(np.random.choice(diff_population, size=few_shot_n, replace=True))
        return np.concatenate(fewshot_q_list)


    def random_selection(self):
        few_shot_n = param['few_shot_n']

        diff_s_idx = {}
        target_q_list = self.annoate_target.id

        for target_q in target_q_list:
            diff_s_idx[target_q] = dict()
            for sf_idx in range(self.sf_num):
                diff_s_idx[target_q][sf_idx] = self.set_fewshot_example(few_shot_n)
        return diff_s_idx
            

    def write_prompt(self, e_f_dict) : 
        few_shot_n = param['few_shot_n']
        
        # write system prompt & examples
        for eval_id, fewshot_dict in e_f_dict.items() : 
        
            for sc_idx, fewshot_id_list in fewshot_dict.items() : 
                message = []
                message.append({"role": "system", "content": self.sys_prompt})
                self.eval_q_list.append(eval_id)

                for fewshot_id in fewshot_id_list : 

                    q_string = self.df.loc[self.df['id'] == fewshot_id, 'question'].iloc[0]
                    a_string = self.df.loc[self.df['id'] == fewshot_id, 'answer'].iloc[0]
                    t_string = self.annoate_target.loc[self.annoate_target['id']==eval_id, 'question'].iloc[0]
                    
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
                    e_f_dict[eval_id][sc_idx] = self.set_fewshot_example(few_shot_n)
                    self.write_prompt(e_f_dict, few_shot_n)
                else :
                    self.message_list.append(message)

    def insert_result(self, result_df):
        db = db_conn.DBConn()
        result_df = result_df[['ver', 'creationdate', 'id']].drop_duplicates()

        data_list = [[int(x[1]), x[2], int(x[3])] for x in result_df.to_records()]
        sql = 'INSERT INTO tt_posts_difficulty_done  VALUES %s'

        with db.cursor() as cur:
            psycopg2.extras.execute_values(cur, sql, data_list, template=None, page_size=100)
            db.commit()     

    def calc_acc_for_v(self, llm_model, few_shot_n, q_src_yn):
        self.logger.info(f'>>>>>>>>>>>>>>>calc_acc_for_v start!')
        
        for idx, message in tqdm(enumerate(self.message_list)):
            tmp = []
            self.logger.info(f'>>>>>>>>>>>>>>>calc_acc_for_v, ask VLLM start!')
            response = self.vllm.llm.chat(message, sampling_params=self.vllm.params) 
            self.logger.info(f'>>>>>>>>>>>>>>>calc_acc_for_v, ask VLLM end!')
            tmp.append(self.eval_q_list[idx])
            tmp.append(response[0].outputs[0].text)
            self.result.append(tmp)
        result_df = pd.DataFrame(self.result, columns = ['id', 'result'])
        result_df = pd.merge(self.annoate_target[['ver', 'creationdate', 'id']], result_df,on = 'id')
        self.logger.info(f'>>>>>>>>>>>>>>>calc_acc_for_v, save result! {self.save_dir}/{self.date}.csv')
        result_df.to_csv(f'{self.save_dir}/{self.date}.csv')
        file_io.save_json(param,                    f'{self.save_dir}/param.json')
        file_io.save_json(conf.VLLM_CONF[llm_model], f'{self.save_dir}/llm_config.json')

        self.insert_result(result_df)
        return result_df
        # /home/mghan/sopjt/git/venv_stackoverflow_src/bin/python /home/mghan/sopjt/git/stackoverflow_src_2425/difficulty/automate_annotation/main.py ver50000
 
    def calc_acc_for_l(self):           
        for idx, message in tqdm(enumerate(self.message_list)):
            data = []
            response = chat( model      = self.ollama,
                            messages    = message,
                            )
            data.append(self.eval_q_list[idx])
            data.append(response['message']['content'])
            self.result.append(data)
        
        result_df = pd.DataFrame(self.result, columns = ['id', 'result'])
        result_df = pd.merge(self.annoate_target[['ver', 'creationdate', 'id']], result_df,on = 'id')
        
        result_df.to_csv(f'{self.save_dir}/{self.date}.csv')
        print(f'{self.save_dir}/{self.date}.csv')

        self.insert_result(result_df)
        return result_df

    def calc_acc_for_c(self):
        for idx, message in tqdm(enumerate(self.message_list)):
            data = []
            MODEL = "gpt-4o"
            response = self.chatgpt.chat.completions.create(
                model=MODEL,
                messages=message,
                temperature= self.temperature,
            )
            data.append(self.eval_q_list[idx])
            data.append(response['message']['content'])
            self.result.append(data)
        result_df = pd.DataFrame(self.result, columns = ['id', 'result'])
        result_df = pd.merge(self.annoate_target[['ver', 'creationdate', 'id']], result_df,on = 'id')
        
        result_df.to_csv(f'{self.save_dir}/{self.date}.csv')
        print(f'{self.save_dir}/{self.date}.csv')

        self.insert_result(result_df)



    def calc_acc(self) :
        llm_model, few_shot_n, q_src_yn =  self.llm_model, self.few_shot_n, self.q_src_yn
        if llm_model == 'l' : # ollama 
            # print(self.eval_prompt)
            self.calc_acc_for_l(llm_model, few_shot_n, q_src_yn)
            

        elif llm_model == 'c' : # chatgpt 
            # print(self.eval_prompt)
            self.calc_acc_for_c(llm_model, few_shot_n, q_src_yn)

        elif llm_model == 'vl' : # vLLM + llama
            print("VLLM")
            self.vllm = VLLM(llm_model)
            self.calc_acc_for_v(llm_model, few_shot_n, q_src_yn)

        
        elif llm_model == 'vq' : # vLLM + qwen
            print("VLLM")
            self.vllm = VLLM(llm_model)
            self.calc_acc_for_v(llm_model, few_shot_n, q_src_yn)