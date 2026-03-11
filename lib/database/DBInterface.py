import lib.database.DBConn as db_conn

class DBInterface:
    def __init__(self):
        self.db_conn = db_conn.DBConn()
        self.bind_query = None

    def execute_query(self, query, params=None):
        with self.db_conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchall()
    
    def execute_ddl(self, query, params=None):
        try:
            with self.db_conn.cursor() as cur:
                if params:
                    self.bind_query = cur.mogrify(query, params).decode()
                cur.execute(self.bind_query if self.bind_query else query)

                
            self.db_conn.commit()
            print("DDL executed successfully.")
        except Exception as e:
            self.db_conn.rollback()
            print(f"DDL execution failed: {e}")