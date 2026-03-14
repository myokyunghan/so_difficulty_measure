import json
import os
import shutil
import pandas as pd
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from setting_for_sdm.constants import CONSTANTS
import tqdm

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


def save_src_as_file(to_save, path):
    """

    Args:
        to_save: a dict or a list of dict
        path: a str

    Returns:
        None
    """
    if CONSTANTS.verbose_loading:
        print(f"[Saving...] {path}")
    with open(path, 'wb') as file:
        file.write(to_save.encode())


def create_dir(path):
    """

    Args:
        to_save: a dict or a list of dict
        path: a str

    Returns:
        None
    """
    if os.path.exists(path):
        print(f"[Deleteing... ] {path}")
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
    files = [f for f in Path(path).glob("*.csv")]
    with ProcessPoolExecutor() as ex:
        df = pd.concat(ex.map(pd.read_csv, files), ignore_index=True)
    df.to_parquet(f'{save_file_path}/{save_file_name}.parquet')
    print(f'[Saved] All complexity files are saved in {save_file_path}/{save_file_name}.parquet')
