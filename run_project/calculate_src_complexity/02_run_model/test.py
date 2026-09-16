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



def call_cyclomatic_complexity(file, lang, save_dir_for_src):
    file_path = f'{save_dir_for_src}/{file}'
    name = os.path.basename(file_path)
    
    print(lizard.analyze( paths=[file_path], exclude_pattern=[], lans=[lang],))  
    


if __name__ == "__main__":


    # run_model(args.param1)
    call_cyclomatic_complexity(file, lang, save_dir_for_src)
    