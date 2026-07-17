import lib.database.DBInterface as db_interface
from setting_for_sdm.sequence import sequence

import pandas as pd
import numpy as np

class Target_Insert: 
    def __init__(self, seq_key):

        self.seq_nm         = sequence[seq_key]
    
    def get_specific_target(self, q_sql, tag, posttype, st_dt, end_dt):    
        db_if = db_interface.DBInterface()

        rows = db_if.execute_query(q_sql, (f"%<{tag}>%",posttype, st_dt, end_dt))
        q_output = pd.DataFrame(rows, columns = ['creationdate','id'])
        return q_output

    def insert_target(self, q_sql, target_table, tag, posttype, st_dt, end_dt):
        print("target_insert") 

        p_id_df = self.get_specific_target(q_sql, tag, posttype, st_dt, end_dt)
        dt_list = list(p_id_df['creationdate'].unique())

        print("sample_insert > create connection")
        db_if = db_interface.DBInterface()

        c_sql = """select nextval(%s);""" 
        rows = db_if.execute_query(c_sql, (self.seq_nm,))
        var = rows[0]

        for dt in dt_list : 
            print(f"insert_target > start insert {dt}")

            c_sql = """select nextval(%s);""" 
            rows = db_if.execute_query(c_sql, (self.seq_nm,))
            var = rows[0]
            
            dt_p_id_list = p_id_df.loc[p_id_df['creationdate'] == dt, 'id'].values
            print("insert_target > create connection> dt_p_id_list>", dt, len(dt_p_id_list))

            first_ann_q_id = [[int(var[0]),dt , int(x)] for x in dt_p_id_list]
            sql = f'INSERT INTO {target_table}  VALUES %s'
            db_if.execute_bulk_values(sql, first_ann_q_id)     
            print(f"insert_target > completed insert {dt}")

    

    
