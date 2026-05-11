import json
import os
import shutil
import pandas as pd
from pathlib import Path
from setting_for_sdm.constants import CONSTANTS
import tqdm
from glob import glob
import sys

class Tee:
    def __init__(self, *streams):
        self.streams = streams
    def write(self, msg):
        for s in self.streams:
            s.write(msg)
            s.flush()
    def flush(self):
        for s in self.streams:
            s.flush()
            
def load_all_files(data_dir):
    """

    Returns:
        a list of dict
    """
    file_list = glob(f'{data_dir}/*.json')
    to_return = []
    for file in file_list:
        loaded = load_json(file)
        to_return += loaded
    return to_return

def load_json(path):
    """

    Args:
        path: a str

    Returns:
        a dict or a list of dict
    """
    if CONSTANTS.verbose_loading:
        print(f"[Loading...] {path}")
    with open(path, "r") as file_:
        to_return = json.load(file_)
    return to_return


def save_json(to_save, path):
    """

    Args:
        to_save: a dict or a list of dict
        path: a str

    Returns:
        None
    """
    if CONSTANTS.verbose_loading:
        print(f"[Saving...] {path}")
    with open(path, 'w') as file:
        json.dump(to_save, file, ensure_ascii=False, indent=4)

def save_jsonl(to_save, path):
    """

    Args:
        to_save: a dict or a list of dict
        path: a str

    Returns:
        None
    """
    if CONSTANTS.verbose_loading:
        print(f"[Saving...] {path}")
    with open(path, 'w', encoding='utf-8') as file:
        for row in to_save:
            file.write(json.dumps(row, ensure_ascii=False) + '\n')


def save_src_as_file(to_save, path, lang):
    """

    Args:
        to_save: a dict or a list of dict
        path: a str

    Returns:
        None
    """
    if CONSTANTS.verbose_loading:
        print(f"[Saving...] {path}")
    with open(f'{path}.{CONSTANTS.LANG_INFO[lang][0]}', 'wb') as file:
        file.write(to_save.encode())


def create_dir(path, deleting=False):
    """

    Args:
        to_save: a dict or a list of dict
        path: a str

    Returns:
        None
    """
    if deleting and os.path.exists(path):
        print(f"[Deleting... ] {path}")
        shutil.rmtree(path)
    if CONSTANTS.verbose_loading:
        print(f"[Creating... ] {path}")   
    os.makedirs(path, exist_ok=True)
    return path


def load_df(path, col_list):
    """

    Args:
        path: a str

    Returns:
        dataframe
    """
    if CONSTANTS.verbose_loading:
        print(f"[Loading Dataframe... ] {path}")
    lst = os.listdir(path)
    dfs = []
    for i in tqdm.tqdm(lst):
        if i.endswith('.json'):
            rows = load_json(f'{path}/{i}')
            if len(rows) >0 : 
                if isinstance(rows[0], list): 
                    tmp = pd.DataFrame(
                        [dict(zip(col_list, row)) for row in rows]
                    )
                    dfs.append(tmp)
                elif isinstance(rows[0], dict):
                    tmp = pd.DataFrame(rows)
                    dfs.append(tmp)
        elif i.endswith('.csv'):
            tmp = pd.read_csv(f'{path}/{i}', usecols=col_list, engine="pyarrow")
            dfs.append(tmp)

    df = pd.concat(dfs, ignore_index=True)         
    return df

def save_many_to_one(path, save_file_path, save_file_name):
    print(f'[src path] {path}')
    print(f'[target path] {save_file_path}')
    files = sorted(glob(f'{path}/*.jsonl'))

    with open(f'{save_file_path}/{save_file_name}.jsonl', 'wb') as out:
        for p in files:
            with open(p, 'rb') as inp:
                shutil.copyfileobj(inp, out)

    print(f'[Saved] {save_file_path}/{save_file_name}.jsonl')

    

def open_src(filepath: str):
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()
    
def read_complexity_parquet(option_dict):
    df = pd.read_parquet(f'{option_dict["save_dir"]}/data/all_complexity.parquet')
    df['id'] = df['path'].apply(lambda x : x.split('_')[1].split('.')[0])
    df[['id', 'cognitive_complexity']] = df[['id', 'cognitive_complexity']].astype(int)
    return df

def read_complexity_jsonl(option_dict):
    df = pd.read_json(f'{option_dict["save_dir"]}/data/all_complexity.jsonl', lines=True)
    df['id'] = df['file_name'].apply(lambda x : x.split('_')[1].split('.')[0])
    df[['id', 'cyclomatic_complexity']] = df[['id', 'cyclomatic_complexity']].astype(int)
    return df

def open_log(filepath):
    log_file = open(filepath, "w", encoding="utf-8")
    tee = Tee(sys.stdout, log_file)
    sys.stdout = tee          # print 출력을 가로챔
    return log_file

def close_log(log_file):
    sys.stdout = sys.__stdout__  # 원래 stdout 복원
    log_file.close()
