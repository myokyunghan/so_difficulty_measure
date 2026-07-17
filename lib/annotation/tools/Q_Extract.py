import re
import pandas as pd
import lib.database.DBConn as db_conn
import lib.preprocess.preprocess as pp
import lib.preprocess.SectionExtractor as se

import lib.database.DBInterface as db_interface


class Q_Extract: 
    def __init__(self, ver):

        self.htmlp = pp.HTMLParser()
        self.codep = pp.CodeSectionParser()
        self.ts = se.SectionExtractor()

        self.ver = ver

    def chk_left(self):
        db_if = db_interface.DBInterface()

        q_sql = """
                    select count(*) as cnt, min(to_char(aa.creationdate, 'yyyy-mm-dd')) as date
                    from tt_posts_difficulty_target aa
                        , (select ver, to_char(creationdate, 'yyyy-mm-dd') as std_date
                            from tt_posts_difficulty_target a
                            where not exists (select 1
                                                from tt_posts_difficulty_done x
                                            where a.id = x.id
                                              and a.ver = x.ver)
                              and (ver/10000) = %s/10000
                            order by a.ver, a.creationdate
                            limit 1
                    ) bb
                    where aa.ver = bb.ver
                    and to_char(aa.creationdate, 'yyyy-mm-dd') = bb.std_date
                ;  
        """
        return db_if.execute_query(q_sql, (self.ver,))
    

    def chk_left_for_full_target(self):
        db_if = db_interface.DBInterface()

        q_sql = """
                select count(*) as cnt, min(to_char(aa.creationdate, 'yyyy-mm-dd')) as date
                from tt_post_python_difficulty_target aa
                    , (select ver, to_char(creationdate, 'yyyy-mm-dd') as std_date
                        from tt_post_python_difficulty_target a
                        where not exists (select 1
                                            from tt_post_python_difficulty_done x
                                        where a.id = x.id
                                        and a.ver = x.ver)
                        order by a.ver, a.creationdate
                        limit 1
                ) bb
                where aa.ver = bb.ver
                and to_char(aa.creationdate, 'yyyy-mm-dd') = bb.std_date
                ;  
        """
        return db_if.execute_query(q_sql, (self.ver,))
        
    def chg_tag(self, code):
        st_pattern = r'<pre(?: class="[^"]*")?><code>'
        st_dst = "```python\n"
        code = re.sub(st_pattern, st_dst, code, count=0, flags=0)
        
        end_dst = "```"
        end_pattern =r'</code></pre>'
        code = re.sub(end_pattern, end_dst, code, count=0, flags=0)
        return code
                                                
    
    def db_extract(self):
        db_if = db_interface.DBInterface()
        q_sql = """
                    select aa.ver, aa.creationdate, aa.id, cc.title, dd.body
                    from tt_posts_difficulty_target aa
                        , (select ver, to_char(creationdate, 'yyyy-mm-dd') as std_date 
                            from tt_posts_difficulty_target a 
                            where not exists (select 1 
                                                from tt_posts_difficulty_done x 
                                            where a.id = x.id
                                              and a.ver = x.ver)
                              and (ver/10000) = %s/10000
                            order by a.ver, a.creationdate
                            limit 1
                    ) bb ,
                    posts cc,
                    postsbody dd 
                    where aa.ver = bb.ver
                    and to_char(aa.creationdate, 'yyyy-mm-dd') = std_date
                    and aa.id = cc.id 
                    and aa.id  = dd.id
                ;  
        """

        rows = db_if.execute_query(q_sql, (self.ver,))
        
        q_output = pd.DataFrame(rows, columns = [
                'ver',
                'creationdate',
                'id',
                'title',
                'body'
                ])
        return q_output

    def db_extract_for_full_target(self):
        db_if = db_interface.DBInterface()
        q_sql = """
                    select aa.ver, aa.creationdate, aa.id, cc.title, dd.body
                    from tt_post_python_difficulty_target aa
                        , (select ver, to_char(creationdate, 'yyyy-mm-dd') as std_date 
                            from tt_post_python_difficulty_target a 
                            where not exists (select 1 
                                                from tt_post_python_difficulty_done x 
                                            where a.id = x.id
                                              and a.ver = x.ver)
                            order by a.ver, a.creationdate
                            limit 1
                    ) bb ,
                    posts cc,
                    postsbody dd 
                    where aa.ver = bb.ver
                    and to_char(aa.creationdate, 'yyyy-mm-dd') = std_date
                    and aa.id = cc.id 
                    and aa.id  = dd.id
                ;  
        """

        rows = db_if.execute_query(q_sql, (self.ver,))
        
        q_output = pd.DataFrame(rows, columns = [
                'ver',
                'creationdate',
                'id',
                'title',
                'body'
                ])
        return q_output  


    def tb_extract(self, q_output):
        # print(self.src_yn)
        # if self.src_yn =='Y':
        q_output['t_body'] = q_output['body'].apply(lambda x : self.chg_tag(x))
        q_output['clean_body'] = q_output['t_body'].apply(lambda x : self.htmlp.clean_html_str(x))
        q_output['clean_body'] = q_output['clean_body'].apply(lambda x:  re.sub(r";(?=\S)", "", x))
        q_output['question'] = """<Title>"""+q_output['title'].map(str)+"""</Title>. <Question>"""+q_output['clean_body'].map(str)+"""</Question> Let's think through the difficulty of question carefully, step by step. """
        # else : 
        #     q_output['c_body'] = q_output['body'].apply(lambda x : self.codep(x))
        #     q_output['t_body'] = q_output[['c_body', 'body']].apply(lambda row: self.ts.get_text_section({'body': row['body'], 'code_sections': row['c_body']['code_sections']}), axis=1)
        #     q_output['clean_body'] = q_output['t_body'].apply(lambda x : self.htmlp.get_html_cleaned_str(x))
        #     q_output['clean_body'] = q_output['clean_body'].apply(lambda x:  re.sub(r";(?=\S)", "", x))

        #     q_output['question'] = """<Title>"""+q_output['title'].map(str)+"""</Title>. <Question>"""+q_output['clean_body'].map(str)+"""</Question>  Let's think through the difficulty of question carefully, step by step."""


        return q_output