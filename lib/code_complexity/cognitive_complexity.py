import os

import pandas as pd
from lib.utils.file_io import open_src
import lib.code_complexity.parser_loader as ps


# ── 30개 언어 매핑 ──

CALC_FUNC       = ps.CALC_FUNC
CALC_PARSER     = ps.CALC_PARSER

def call_cognitive_complexity(file, lang, save_dir_for_src, save_dir_for_csv):
    file_path = f'{save_dir_for_src}/{file}'
    name = os.path.basename(file_path)
    new_nm = os.path.splitext(name)[0]
    new_file = f"{new_nm}.csv"

    if check_code(file_path, lang):
        results = CALC_FUNC[lang](file_path)
        complexities = [r['complexity'] for r in results]

        if not complexities:
            return False

        pd.DataFrame(
            [[new_file, new_file, c] for c in complexities],
            columns=['Path', 'File Name', 'Cognitive Complexity']
        ).to_csv(f'{save_dir_for_csv}/{new_file}')


        # total_complexity = sum(complexities)
        # max_complexity = max(complexities) if complexities else 0
        # n_functions = len(complexities)
        # avg_complexity = total_complexity / n_functions if complexities else 0
        # pd.DataFrame([[new_file, new_file, dict(total=total_complexity, max=max_complexity, avg=avg_complexity, raw_complexities=complexities)]], columns=['Path', 'File Name', 'Cognitive Complexity'])\
        #     .to_csv(f'{save_dir_for_csv}/{new_file}')
        return True
    else :
        return False
    

    



def check_code(file_path, lang):
    if lang == "assembly":
        return True
    code = open_src(file_path)
    parser = CALC_PARSER[lang]()
    
    # 잘못된 입력에서 parser가 hang하는 것을 방지
    try:
        parser.timeout_micros = 5_000_000  # 5 seconds
    except (AttributeError, TypeError):
        pass  # 구버전 tree-sitter 미지원
    
    try:
        tree = parser.parse(bytes(code, "utf-8"))
        return not tree.root_node.has_error
    except ValueError:
        # parser timeout = 잘못된 입력
        return False