import os
import lib.tag_analysis.tag_sql as tag_sql
from lib.database.DBInterface import DBInterface
from setting_for_sdm.date_setting import Date_Setting
from setting_for_sdm.path_setting import path_list
from lib.utils.file_io import save_json, create_dir
from run_project.options import RunnerOptions

class ModelRunner:
    
    def __init__(self, runner_opt):
        self.db_interface = DBInterface()
        self.runner_opt = runner_opt

        self.save_length = 10000
        self.lang = self.runner_opt.user_opt['selected_tags']
        self.save_dir = self.runner_opt.user_opt['save_dir']

        self.startdate = Date_Setting[self.runner_opt.user_opt['year_range']]["start_date"]
        self.end_date = Date_Setting[self.runner_opt.user_opt['year_range']]["end_date"]

    def __call__(self):
        self.run()

    def run(self):
        create_dir(f'{self.save_dir}/data')
        self.create_view('create_v_tag_proportion', (self.startdate, self.end_date, f'%<{self.lang}>%', self.lang))
        rows = self.select_data('select_v_tag_proportion')
        self.save_data(rows)
        self.save_option()
        

    def create_view(self, sql_id, params=None):
        """
        Returns:
            None
        """
        self.db_interface.execute_ddl(tag_sql.sql_collection[sql_id.replace('create', 'drop')])
        print(f'[Drop view if exists...] SQL_ID : {sql_id.replace("create", "drop")} Done.')
        self.db_interface.execute_ddl(tag_sql.sql_collection[sql_id], params)
        print(f"View '{sql_id}' created successfully.")
        print(f'[Create view...] SQL_ID : {sql_id} Done.')
        
    def select_data(self, sql_id, params=None):
        """

        Returns:
            None
        """
        sql = tag_sql.sql_collection[sql_id]
        print(f"[Executing query...] SQL_ID : {sql_id} Done.")
        return self.db_interface.execute_query(sql, params)  

        

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
        save_json(self.runner_opt.user_opt, f'{self.save_dir}/option.json')
        print(f"[Saving data...] Saved to runner option to {self.save_dir}/option.json")

## for test
if __name__ == '__main__':
    runner = ModelRunner()
    runner()
