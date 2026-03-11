from datetime import datetime
class CONSTANTS:
    verbose_loading = False
    color_list = [[ 
                        "#4575b4",  # deep blue
                        "#91bfdb",  # light blue
                        "#e0f3f8",  # pale blue
                        "#a6d96a",  # light green
                        "#1a9850",  # green
                        "#d9ef8b",  # lime yellow
                        "#fee08b",  # beige
                        "#fdae61",  # soft orange
                        "#f46d43",  # coral orange
                        "#d73027"   # muted red
                        ],
                    [
                        "#8c510a",  # dark brown
                        "#bf812d",  # brown-gold
                        "#dfc27d",  # sand yellow
                        "#f6e8c3",  # beige
                        "#c7eae5",  # light aqua
                        "#80cdc1",  # teal
                        "#35978f",  # muted teal
                        "#01665e",  # deep green
                        "#003c30",  # near-black green
                        # "#f5f5f5"   # pale gray (neutral base)
                        "#8f8f8f"
                    ]]
    color_map_str = ["cool", "viridis"]
    chatgpt_release_date = "2022.11.30"

    DATA_PATH_LAB = '/Users/cslab/code-server/Myokyung'

    DATA_PATH='/usr/share/d_ollama'

    ANNO_RESULT='/data/llm_annotation_result'

    SNAPSHOT_DIR = '/usr/share/d_ollama/data/snapshots_2/'

    start_date = '2022-11-30'
    end_date = '2024-12-01'
    std_date = '2023-11-30'

    
    year_range = {"21to23" : {
                                    "start_date"            : datetime(2021, 11, 30),
                                    "std_date"              : datetime(2022, 11, 30),
                                    "end_date"              : datetime(2023, 11, 30),
                                    "monthly_timestamps"    : [
                                                                "2021.11.30", "2021.12.31", 
                                                                "2022.01.31", "2022.02.28", "2022.03.31", "2022.04.30", "2022.05.31", 
                                                                "2022.06.30", "2022.07.31", "2022.08.31", "2022.09.30", "2022.10.31", 
                                                                "2022.11.30", "2022.12.31", 
                                                            
                                                                "2023.01.31", "2023.02.28", "2023.03.31", "2023.04.30", "2023.05.31", 
                                                                "2023.06.30", "2023.07.31", "2023.08.31", "2023.09.30", "2023.10.31", 
                                                                "2023.11.30"
                                                            ]

                                },
                "22to24" : {
                                    "start_date"            : datetime(2022, 11, 30),
                                    "std_date"              : datetime(2023, 11, 30),
                                    "end_date"              : datetime(2024, 11, 30),
                                    "monthly_timestamps"    : [
                                                                "2022.11.30", "2022.12.31", 
                                                            
                                                                "2023.01.31", "2023.02.28", "2023.03.31", "2023.04.30", "2023.05.31", 
                                                                "2023.06.30", "2023.07.31", "2023.08.31", "2023.09.30", "2023.10.31", 
                                                                "2023.11.30", "2023.12.31",

                                                                "2024.01.31", "2024.02.28", "2024.03.31", "2024.04.30", "2024.05.31", 
                                                                "2024.06.30", "2024.07.31", "2024.08.31", "2024.09.30", "2024.10.31", 
                                                                "2024.11.30"
                                                    ]
                },
                "21to24": {
                                    "start_date"    : datetime(2021, 11, 30),
                                    "std_date"      : datetime(2023, 11, 30),
                                    "end_date"      : datetime(2024, 11, 30),
                                    "monthly_timestamps": [
                                                            "2021.11.30", "2021.12.31", 
                                                            "2022.01.31", "2022.02.28", "2022.03.31", "2022.04.30", "2022.05.31", 
                                                            "2022.06.30", "2022.07.31", "2022.08.31", "2022.09.30", "2022.10.31", 
                                                            "2022.11.30", "2022.12.31", 
                                                            
                                                            "2023.01.31", "2023.02.28", "2023.03.31", "2023.04.30", "2023.05.31", 
                                                            "2023.06.30", "2023.07.31", "2023.08.31", "2023.09.30", "2023.10.31", 
                                                            "2023.11.30", "2023.12.31",

                                                            "2024.01.31", "2024.02.28", "2024.03.31", "2024.04.30", "2024.05.31", 
                                                            "2024.06.30", "2024.07.31", "2024.08.31", "2024.09.30", "2024.10.31", 
                                                            "2024.11.30"
                                                    ]

                }

    }
    

    data_root_dir = "/mnt/hdd/mghan/so_data_availability"

    ## topic modeling result dirs
    bert_monthly_data_dir = f"{data_root_dir}/result/bert_based/run_id_0/data"
    # 2021년 01 월부터의 데이터
    bert_monthly_data_dir_2 = f"{data_root_dir}/result/bert_based/run_id_2/data"
    # snapshot2 data
    bert_monthly_data_dir_3 = f"{data_root_dir}/result/bert_based/run_id_3/data"

    
    tag_monthly_data_dir    = f"{data_root_dir}/result/tag/run_id_0/data"
    #2021.11 ~ 2024.11
    tag_monthly_data_dir_2  = f"{data_root_dir}/result/tag/run_id_2/data"

    tag_monthly_data_dir_2_py  = f"{data_root_dir}/result/tag/run_id_2/python/data"
    tag_monthly_data_dir_2_cpp  = f"{data_root_dir}/result/tag/run_id_2/cpp/data"

    lda_monthly_data_dir = f"{data_root_dir}/result/lda/run_id_1/data"

    bert_difficulty_data_dir = f"{data_root_dir}/result/bert_based/difficulty_annotated/data"
    lda_difficulty_data_dir = f"{data_root_dir}/result/lda/difficulty_annotated/data"
    tag_difficulty_data_dir = f"{data_root_dir}/result/bert_based/difficulty_annotated/data"

    all_topics_list = list(range(0, 50))

    pyplot_color_palette = ["slategrey", "royalblue", "dodgerblue",
                            "seagreen", "forestgreen"]
    pyplot_blue_to_red = ["blue", "indigo", "darkmagenta",
                          "mediumvioletred", "crimson", "red"]
    codebert_languages = ["python", "java", "javascript", "php", "ruby", "go"]
    early_2010s_languages = ["dart", "kotlin", "julia", "typescript",
                             "elixir", "swift", "hacklang", "elm",
                             "red-lang", "crystal-lang"]
    late_2010s_languages = ["rust", "raku", "ring", "zig", "ballerina",
                            "vlang", "reason"]
    popular_10_languages = ["python", "c++", "java", "c", "c#",
                            "javascript", "vb.net", "go", "fortran", "delphi"]
    popular_10_languages_2023 = ["python", "c++", "java", "c", "c#",
                                 "javascript", "vb.net", "sql", "php",
                                 "assembly"]
    github_octoverse_2022_languages = ["javascript", "python", "java",
                                       "typescript", "c#", "c++", "php",
                                       "shell", "c", "ruby"]

    lang_tag_dict = {'python' : 'python',
                'cpp': 'c++',
                'java':'java',
                'vba':'vba'
                }
    

    tag_lang_dict = {'python' : 'python',
                'c++': 'cpp',
                'java':'java',
                'vba':'vba'
    }
    


