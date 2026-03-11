import setting_for_sdm.config as conf
import psycopg2

class DBConn:

    def __init__(self):
        
        self._conn = psycopg2.connect(
                        host                =conf.database_info['host'],
                        dbname              =conf.database_info['dbname'],
                        user                =conf.database_info['user'],
                        password            =conf.database_info['password'],
                        connect_timeout     =10,
                        keepalives          =1,
                        keepalives_idle     =30,
                        keepalives_interval =10,
                        keepalives_count    =5
                    )
        with self._conn.cursor() as cur:
            cur.execute(f"SET search_path TO {conf.database_info['schema']}")

    def cursor(self):
        """"""
        return self._conn.cursor()

    def commit(self):
        self._conn.commit()
    
    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

