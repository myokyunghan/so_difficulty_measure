import os
import subprocess

from lib.code_complexity.cognitive_complexity_for_c import (
    create_parser as create_c_parser,
    calculate_file as calculate_file_for_c
)

from lib.code_complexity.cognitive_complexity_for_cpp import (
    create_parser as create_cpp_parser,
    calculate_file as calculate_file_for_cpp
)

from lib.code_complexity.cognitive_complexity_for_csharp import (
    create_parser as create_csharp_parser,
    calculate_file as calculate_file_for_csharp
)

from lib.code_complexity.cognitive_complexity_for_fortran import (
    create_parser as create_fortran_parser,
    calculate_file as calculate_file_for_fortran
)

from lib.code_complexity.cognitive_complexity_for_java import (
    create_parser as create_java_parser,
    calculate_file as calculate_file_for_java
)

from lib.code_complexity.cognitive_complexity_for_javascript import (
    create_parser as create_javascript_parser,
    calculate_file as calculate_file_for_javascript
)
from lib.code_complexity.cognitive_complexity_for_python import (
    create_parser as create_python_parser,
    calculate_file as calculate_file_for_python
)

from lib.code_complexity.cognitive_complexity_for_r import (
    create_parser as create_r_parser,
    calculate_file as calculate_file_for_r
)

from lib.code_complexity.cognitive_complexity_for_rust import (
    create_parser as create_rust_parser,
    calculate_file as calculate_file_for_rust
)

import pandas as pd
from lib.utils.file_io import open_src



def call_cognitive_complexity(file, lang, save_dir_for_src, save_dir_for_csv):
    file_path = f'{save_dir_for_src}/{file}'
    name = os.path.basename(file_path)
    new_nm = os.path.splitext(name)[0]

    new_file = f"{new_nm}.csv"
    # old_file = f"complexipy.csv"

    # if lang == 'python' :         
    #     subprocess.run(["complexipy", file_path, "-l", "file", "-o"], cwd=save_dir_for_csv)
        
    #     if os.path.exists(f'{save_dir_for_csv}/{old_file}'):
    #         os.rename(f'{save_dir_for_csv}/{old_file}', f'{save_dir_for_csv}/{new_file}' )
    calc_func = {
        'c': calculate_file_for_c,
        'c++': calculate_file_for_cpp,
        'c#': calculate_file_for_csharp,
        'fortran': calculate_file_for_fortran,
        'java': calculate_file_for_java,
        'javascript': calculate_file_for_javascript,
        'python': calculate_file_for_python,
        'r': calculate_file_for_r,
        'rust': calculate_file_for_rust,
    }

    # if check_code(file_path, lang) : 
    results = calc_func[lang](file_path)
    total_complexity = sum(r['complexity'] for r in results)
    pd.DataFrame([[new_file, new_file, total_complexity]], columns=['Path', 'File Name', 'Cognitive Complexity'])\
        .to_csv(f'{save_dir_for_csv}/{new_file}')


def check_code(file_path, lang):

    calc_parser = {
        'c': create_c_parser,
        'c++': create_cpp_parser,
        'c#': create_csharp_parser,
        'fortran': create_fortran_parser,
        'java': create_java_parser,
        'javascript': create_javascript_parser,
        'python': create_python_parser,
        'rust': create_rust_parser,
        'r': create_r_parser,
    }
    code = open_src(file_path)
    parser = calc_parser[lang]()
    tree = parser.parse(bytes(code, "utf-8"))

    if tree.root_node.has_error:
        return False
    else : 
        return True

