import os

import pandas as pd
import numpy as np
from lib.utils.file_io import open_src
import lib.code_complexity.parser_loader as ps



CALC_FUNC       = ps.CALC_FUNC
CALC_PARSER     = ps.CALC_PARSER
CALC_CLASS      = ps.CALC_CLASS

HAS_ERROR_UNRELIABLE = {"groovy", "fsharp", "vbnet"}

def call_cognitive_complexity(file, lang, save_dir_for_src, save_dir_for_csv):
    file_path = f'{save_dir_for_src}/{file}'
    name = os.path.basename(file_path)
    new_nm = os.path.splitext(name)[0]
    new_file = f"{new_nm}.csv"

    if check_code(file_path, lang):
        results = CALC_FUNC[lang](file_path)
        complexities = [r['complexity'] for r in results]

        if not complexities:
            top_level_complexities = call_cognitive_complexity_from_top(file_path, lang)
            if not top_level_complexities:
                return False
            complexities = top_level_complexities

        pd.DataFrame(
            [[new_file, new_file, c] for c in complexities],
            columns=['path', 'file_name', 'cognitive_complexity']
        ).to_csv(f'{save_dir_for_csv}/{new_file}')
        return True
    else :
        return False

def call_cognitive_complexity_from_top(file_path, lang):
    try:
        code = open_src(file_path)
        calc = CALC_CLASS[lang](code)
        calc.details = []
        if calc.tree and not calc._parse_failed:
            top_c = calc._visit_children(calc.tree.root_node, 0)
            if top_c > 0:
                return [top_c]
            else:
                return False  # top-level에도 control flow 없음
        else:
            return False
    except Exception:
        return False

def check_code(file_path, lang):
    if lang == "assembly":
        return True
    code = open_src(file_path)
    parser = CALC_PARSER[lang]()
    try:
        parser.timeout_micros = 5_000_000
    except (AttributeError, TypeError):
        pass
    try:
        tree = parser.parse(bytes(code, "utf-8"))
    except ValueError:
        return False
    
    if lang in HAS_ERROR_UNRELIABLE:
        return True
    
    return not tree.root_node.has_error
    

    
def calculate_cognitive_complexity(df, option_str):

    df['cognitive_complexity'] = np.log(df['cognitive_complexity']+1)

    if option_str == 'mean':
        return df.groupby('id', as_index=False)['cognitive_complexity'].mean()
    elif option_str == 'max':
        return df.groupby('id', as_index=False)['cognitive_complexity'].max()
    elif option_str == 'std':
        return df.groupby('id', as_index=False)['cognitive_complexity'].std()
    elif option_str == 'sum':
        return df.groupby('id', as_index=False)['cognitive_complexity'].sum()
    else:
        raise ValueError(f"Invalid option_str: {option_str}")

