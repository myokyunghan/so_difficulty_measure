import lib.database.DBConn as db_conn
import psycopg2.extras

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

    def execute_bulk_values(self, query, values, template=None, page_size=100):
        """
        psycopg2.extras.execute_values wrapper for bulk insert

        :param query: SQL query (e.g. INSERT INTO table (col1, col2) VALUES %s)
        :param values: list of tuples or lists
        :param template: optional value template
        :param page_size: batch size
        """
        try:
            with self.db_conn.cursor() as cur:
                psycopg2.extras.execute_values(
                    cur,
                    query,
                    values,
                    template=template,
                    page_size=page_size
                )
                self.db_conn.commit()
                print("Bulk insert executed successfully.")
        except Exception as e:
            self.db_conn.rollback()
            print(f"Bulk insert failed: {e}")