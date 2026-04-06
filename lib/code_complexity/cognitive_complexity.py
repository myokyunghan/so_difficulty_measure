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

    results = CALC_FUNC[lang](file_path)
    total_complexity = sum(r['complexity'] for r in results)
    pd.DataFrame([[new_file, new_file, total_complexity]], columns=['Path', 'File Name', 'Cognitive Complexity'])\
        .to_csv(f'{save_dir_for_csv}/{new_file}')


def check_code(file_path, lang):
    code = open_src(file_path)
    parser = CALC_PARSER[lang]()
    tree = parser.parse(bytes(code, "utf-8"))
    return not tree.root_node.has_error