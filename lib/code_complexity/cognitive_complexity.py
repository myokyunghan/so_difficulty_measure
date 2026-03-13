import os
import glob
import shutil
import subprocess
import sys


def call_cognitive_complexity(file, save_dir_for_src, save_dir_for_csv):

    file_path = f'{save_dir_for_src}/{file}'

    name = os.path.basename(file_path)
    new_nm = os.path.splitext(name)[0]
    
    new_file = f"{new_nm}.csv"
    old_file = f"complexipy.csv"
    
    subprocess.run(["complexipy", file_path, "-l", "file", "-o"], cwd=save_dir_for_csv)
    
    if os.path.exists(f'{save_dir_for_csv}/{old_file}'):
        os.rename(f'{save_dir_for_csv}/{old_file}', f'{save_dir_for_csv}/{new_file}' )
