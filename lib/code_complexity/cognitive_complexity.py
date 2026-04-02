import os
import subprocess
from lib.code_complexity.cognitive_complexity_for_cpp import (
    create_parser as create_cpp_parser,
    calculate_file as calculate_file_for_cpp
)
from lib.code_complexity.cognitive_complexity_for_java import (
    create_parser as create_java_parser,
    calculate_file as calculate_file_for_java
)
from lib.code_complexity.cognitive_complexity_for_python import (
    create_parser as create_python_parser,
    calculate_file as calculate_file_for_python
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
        'c++': calculate_file_for_cpp,
        'java': calculate_file_for_java,

        'python': calculate_file_for_python,
        'rust': calculate_file_for_rust,
    }

    # if check_code(file_path, lang) : 
    results = calc_func[lang](file_path)
    total_complexity = sum(r['complexity'] for r in results)
    pd.DataFrame([[new_file, new_file, total_complexity]], columns=['Path', 'File Name', 'Cognitive Complexity'])\
        .to_csv(f'{save_dir_for_csv}/{new_file}')


    # if lang=='python' : 
    #     if check_code(file_path) : 
    #         results = calculate_file_for_python(file_path)
    #         total_complexity = sum(r['complexity'] for r in results)
    #         pd.DataFrame([[new_file, new_file, total_complexity]], columns=['Path', 'File Name', 'Cognitive Complexity'])\
    #             .to_csv(f'{save_dir_for_csv}/{new_file}')
    
    # elif lang == 'c++':
    #     results = calculate_file_for_cpp(file_path, is_file=True, threshold=0)
    #     total_complexity = sum(r['complexity'] for r in results)
    #     pd.DataFrame([[new_file, new_file, total_complexity]], columns=['Path', 'File Name', 'Cognitive Complexity'])\
    #         .to_csv(f'{save_dir_for_csv}/{new_file}')
        
    # elif lang == 'rust':
    #     results = calculate_file_for_rust(file_path)
    #     total_complexity = sum(r['complexity'] for r in results)
    #     pd.DataFrame([[new_file, new_file, total_complexity]], columns=['Path', 'File Name', 'Cognitive Complexity'])\
    #         .to_csv(f'{save_dir_for_csv}/{new_file}')
    
    # elif lang == 'java':
    #     if check_code(file_path) : 
    #         results = calculate_file_for_java(file_path)
    #         total_complexity = sum(r['complexity'] for r in results)
    #         pd.DataFrame([[new_file, new_file, total_complexity]], columns=['Path', 'File Name', 'Cognitive Complexity'])\
    #             .to_csv(f'{save_dir_for_csv}/{new_file}')
            


def check_code(file_path, lang):
    calc_parser = {
        'c++': create_cpp_parser,
        'java': create_java_parser,

        'python': create_python_parser,
        'rust': create_rust_parser,
    }
    code = open_src(file_path)
    parser = calc_parser[lang]()
    tree = parser.parse(bytes(code, "utf-8"))

    if tree.root_node.has_error:
        return False
    else : 
        return True

    # # 2. method 존재 체크
    # if not has_method(tree):
    #     return "INVALID"

    # # 3. 정상 코드 → complexity 계산
    # results = calculate_source(code)

    # 4. 진짜 0 vs 아닌 경우 구분
    # if results and all(r["complexity"] == 0 for r in results):
    #     return "VALID_ZERO"

    # return "VALID_NONZERO"


# parser = create_java_parser()
# tree = parser.parse(bytes("""@Bean
#     public WebServerFactoryCustomizer&lt;TomcatServletWebServerFactory&gt; webServerFactoryCustomizer() {
#         return webServerFactory -&gt; {
#             ErrorPage errorPage = new ErrorPage(HttpStatus.INTERNAL_SERVER_ERROR, &quot;/error&quot;);
#             webServerFactory.addErrorPages(errorPage);
#         };
#     }""", "utf-8"))

# # 1. 파싱 에러 체크
# if tree.root_node.has_error:
#     print("has error")
# else : 
#     print("no error")