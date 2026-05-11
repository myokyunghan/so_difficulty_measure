import os

import pandas as pd
import numpy as np
from lib.utils.file_io import open_src
import lib.code_complexity.parser_loader as ps
from setting_for_sdm.constants import CONSTANTS
import lizard

from lib.utils.file_io import open_src, save_jsonl
import lib.code_complexity.parser_loader as ps
CALC_PARSER     = ps.CALC_PARSER


def call_cyclomatic_complexity(file, lang, save_dir_for_src, save_dir_for_jsonl):
    file_path = f'{save_dir_for_src}/{file}'
    name = os.path.basename(file_path)
    new_nm = os.path.splitext(name)[0]
    new_file = f"{new_nm}.jsonl"

    if check_code(file_path, lang):
        rows = [] 
        for result in lizard.analyze( paths=[file_path], exclude_pattern=[], lans=[lang],):  
            for func in result.function_list:
                rows.append({  
                    'path': file_path,
                    'file_name': name,
                    'language': lang,
                    'function_name': func.name,
                    'cyclomatic_complexity': func.cyclomatic_complexity,
                    'nloc': func.nloc,
                    'token_count': func.token_count,
                    'parameter_count': func.parameter_count,
                    'start_line': func.start_line,
                    'end_line': func.end_line,
                })
        if rows:
            save_jsonl(rows, f'{save_dir_for_jsonl}/{new_file}')
    

def calculate_cyclomatic_complexity(df, option_str):

    df['cyclomatic_complexity'] = np.log(df['cyclomatic_complexity']+1)

    if option_str == 'mean':
        return df.groupby('id', as_index=False)['cyclomatic_complexity'].mean()
    elif option_str == 'max':
        return df.groupby('id', as_index=False)['cyclomatic_complexity'].max()
    elif option_str == 'std':
        return df.groupby('id', as_index=False)['cyclomatic_complexity'].std()
    elif option_str == 'sum':
        return df.groupby('id', as_index=False)['cyclomatic_complexity'].sum()
    else:
        raise ValueError(f"Invalid option_str: {option_str}")


def check_code(file_path, lang):

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
    
    return not tree.root_node.has_error
    