import json
import os
import shutil
import pandas as pd
from setting_for_sdm.constants import CONSTANTS

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
    for i in lst:
        rows = load_json(f'{path}/{i}')

        if isinstance(rows[0], list):
            tmp = pd.DataFrame(
                [dict(zip(col_list, row)) for row in rows]
            )
            dfs.append(tmp)
        elif isinstance(rows[0], dict):
            tmp = pd.DataFrame(rows)  
            dfs.append(tmp)

    df = pd.concat(dfs, ignore_index=True)         
    return df


