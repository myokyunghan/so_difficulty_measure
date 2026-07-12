import lib.database.DBInterface as db_interface
from setting_for_sdm.sequence import sequence

import pandas as pd
import numpy as np

class Sample_Insert: 
    def __init__(self, st_dt, end_dt, sample_num, seed, posttype, num_of_date):

        self.st_dt          = st_dt     
        self.end_dt         = end_dt    
        self.sample_num     = sample_num
        self.seed           = seed      
        self.posttype       = posttype  
        self.seq_nm         = sequence[num_of_date]
    
    def get_id_list(self, posttype, st_dt, end_dt):
        print("sample_insert> get_id_list") 
        if posttype == "1" : 
            db_if = db_interface.DBInterface()

            q_sql = """select to_char(a.creationdate, 'yyyy-mm-dd') as creationdate, 
                            a.id 
                        from posts a 
                where a.tags like %s
                and a.posttypeid = %s
                and a.creationdate between %s and %s
                and not exists (select 1 
                                    from tt_posts_difficulty_annotated x 
                                where a.id = x.id)
                """ 
            rows = db_if.execute_query(q_sql, (f"%<python>%",posttype, st_dt, end_dt))
            q_output = pd.DataFrame(rows, columns = ['creationdate','id'])
            return q_output

        else : 
            print("sample_insert> get_id_list> posttype==2") 
            posttype = "'2'"



    def insert_sample(self):
        print("sample_insert") 

        p_id_df = self.get_id_list(self.posttype, self.st_dt, self.end_dt)
        dt_list = list(p_id_df['creationdate'].unique())

        print("sample_insert > create connection")
        db_if = db_interface.DBInterface()

        c_sql = """select nextval(%s);""" 
        rows = db_if.execute_query(c_sql, (self.seq_nm,))
        var = rows[0]

        for dt in dt_list : 
            dt_p_id_list = p_id_df.loc[p_id_df['creationdate'] == dt, 'id'].values
            print("sample_insert > create connection> dt_p_id_list>", dt, len(dt_p_id_list))

            if len(dt_p_id_list) < self.sample_num : 
                first_ann_q_id = [[int(var[0]),dt , int(x)] for x in dt_p_id_list]
                print("sample_insert > create connection> dt_p_id_list> sample_num보다 작음>", dt, len(dt_p_id_list), self.sample_num)
            else :
                first_ann_q_id = [[int(var[0]),dt , int(x)] for x in np.random.choice(dt_p_id_list, size=self.sample_num, replace=False)]
                print("sample_insert > create connection> first_ann_q_id>", dt, first_ann_q_id)

            sql = f'INSERT INTO tt_posts_difficulty_target  VALUES %s'
            db_if.execute_bulk_values(sql, first_ann_q_id)     

    
    def insert_target(self, p_id_df):
        print("insert_target") 

        dt_list = list(p_id_df['creationdate'].unique())

        print("insert_target > create connection")
        db_if = db_interface.DBInterface()

        for dt in dt_list : 
            print(f"insert_target > start insert {dt}")

            c_sql = """select nextval(%s);""" 
            rows = db_if.execute_query(c_sql, (self.seq_nm,))
            var = rows[0]
            
            dt_p_id_list = p_id_df.loc[p_id_df['creationdate'] == dt, 'id'].values
            print("insert_target > create connection> dt_p_id_list>", dt, len(dt_p_id_list))

            first_ann_q_id = [[int(var[0]),dt , int(x)] for x in dt_p_id_list]
            sql = f'INSERT INTO tt_posts_difficulty_target  VALUES %s'
            db_if.execute_bulk_values(sql, first_ann_q_id)     
            print(f"insert_target > completed insert {dt}")
