import os
import pandas as pd
import pprint

from setting_for_sdm.date_setting import Date_Setting

from lib.utils.file_io import (save_json, create_dir, load_df, save_src_as_file, save_many_to_one)
from lib.preprocess.preprocess import (HTMLParser, CodeSectionParser)
from lib.code_complexity.cognitive_complexity import call_cognitive_complexity

from run_project.calculate_src_complexity.options import RunnerOptions
from tqdm import tqdm



class ModelRunner:
    
    def __init__(self, runner_opt):
        self.runner_opt = runner_opt

        self.save_length = 10000
        self.lang = self.runner_opt.user_opt['selected_tags']
        self.data_dir = f"{self.runner_opt.user_opt['data_dir']}"
        create_dir(f'{self.data_dir}')

        self.save_dir_for_src = f"{self.runner_opt.user_opt['save_dir']}/data/src"
        self.save_dir_for_csv = f"{self.runner_opt.user_opt['save_dir']}/data/csv"
        self.save_dir_for_one = f"{self.runner_opt.user_opt['save_dir']}/data"

        self.startdate = Date_Setting[self.runner_opt.user_opt['year_range']]["start_date"]
        self.end_date = Date_Setting[self.runner_opt.user_opt['year_range']]["end_date"]


    def __call__(self):
        self.run()

    def run(self):
        create_dir(f'{self.save_dir_for_src}')
        create_dir(f'{self.save_dir_for_csv}')

        # load data
        print(self.data_dir)
        df = load_df(self.data_dir, ['id' , 'creationdate' , 'title', 'tags', 'body'])
        # preprocess (extract src)
        src_list = self.extract_src_from_q(df[['id', 'body']].to_dict(orient='records'))
        self.save_file(src_list)

        not_conducted_list = self.calculate_complexity()
        self.save_option()
        save_json(not_conducted_list, f'{self.save_dir_for_one}/not_conducted.json')
        save_many_to_one(self.save_dir_for_csv, self.save_dir_for_one, "all_complexity")


    def calculate_complexity(self):
        list_ = os.listdir(self.save_dir_for_src)
        pbar = tqdm(list_)
        not_conducted_list = []

        for i in pbar:
            pbar.set_description(f"Processing: {i}")
            result = call_cognitive_complexity(i, self.lang, self.save_dir_for_src, self.save_dir_for_csv)

            if not result:
                not_conducted_list.append(self.save_dir_for_src)

        return not_conducted_list



        
            
        print(f'[Saved] complexity files are saved in {self.save_dir_for_csv}')

    def save_file(self, list_, params=None):
        df_src = pd.DataFrame(list_).explode('src', ignore_index=True)

        for index, row in df_src.iterrows():
            src = row['src']
            file_nm = f"{index}_{row['id']}"
            save_src_as_file(src, f'{self.save_dir_for_src}/{file_nm}', self.lang)

        print(f'[Saved] Src files are saved in {self.save_dir_for_src}')


    def extract_src_from_q(self, list_, params=None):
        """

        Returns:
            None
        """


        codep = CodeSectionParser()
        src_list = list_
        
        src_list = [{'id': d['id'], 'body': codep(d['body'])} for d in src_list]
        src_list = [{'id': d['id'], 'body': d['body']['code_sections']} for d in src_list if d['body']['code_sections']]
        src_list = [{'id': d['id'], 'src': [s_d['span_str'] for s_d in d['body']]} for d in src_list]        
        return src_list


        

    def save_data(self, rows):
        """

        Args:
            list_: a list of dict

        Returns:
            None
        """
        length = len(rows)
        iters = length // self.save_length
        print(f"[Saving data...] Chunks: {iters + (1 if length % self.save_length else 0)}")
        for i in range(iters):
            start_idx = i * self.save_length
            end_idx = (i + 1) * self.save_length
            to_save = rows[start_idx:end_idx]
            save_json(to_save, f"{self.save_dir}/data/{i}.json")
        if length - iters * self.save_length > 0:
            start_idx = iters * self.save_length
            to_save = rows[start_idx:]
            save_json(to_save, f"{self.save_dir}/data/{iters}.json")
        print(f"[Saving data...] Saved to {self.save_dir}")


    def save_option(self):
        """

        Returns:
            None
        """
        save_json(self.runner_opt.user_opt, f'{self.save_dir_for_one}/option.json')
        print(f"[Saving data...] Saved to runner option to {self.save_dir_for_one}/option.json")

## for test
if __name__ == '__main__':

    runner_opt = RunnerOptions( 
                            "test", # year_range (22to24, 21to23)
                            6, # run_id 
                            "test" # snapshot(snapshot1, snapshot2)
    )
    runner = ModelRunner(runner_opt)
    runner()
