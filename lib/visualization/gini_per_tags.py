from matplotlib import pyplot as plt
from tqdm import tqdm
import random
import numpy as np
from lib.utils.sublist import get_sublist_of_desired_date_range, \
    get_sublist_of_desired_tags
from lib.utils.statistics import calculate_gini, get_fractional_values_dict
from lib.utils.datetime_handler import *
from lib.utils.data_loader import DataLoader

data_dir = "../data/questions_with_statistics"
color_map = plt.get_cmap("brg")


def get_data_sublist_in_date_range(date_range):
    """

    Args:
        date_range: a couple of datetime strings

    Returns:
        a list of dict
    """
    file_list = get_related_files(date_range)
    to_return = []
    for i in file_list:
        file_path = f"{data_dir}/{i}.json"
        json_list = DataLoader.load_json(file_path)
        to_return += json_list
    to_return = get_sublist_of_desired_date_range(to_return, date_range)
    return to_return


def get_data_count_and_gini_coefficient_for_tag(list_, tag, key):
    """

    Args:
        list_: a list of dict which has key
        tag: a str
        key: a str, which is one of "viewcount", "commentcount", "answercount"

    Returns:
        a couple of
            total count of datapoints and a Gini coefficient
    """
    list_ = get_sublist_of_desired_tags(list_, [tag])
    if len(list_) == 0:
        return 0, 0
    else:
        to_calculate_gini = {dict_["id"]: int(dict_["commentcount"]) + int(
            dict_["answercount"]) for dict_ in list_}
        if sum(list(to_calculate_gini.values())) == 0:
            return len(list_), 0
        to_calculate_gini = get_fractional_values_dict(to_calculate_gini)
        gini = calculate_gini(list(to_calculate_gini.values()))
        return len(list_), gini


def collect_gini_coefficient_for_tag(window, tag, key):
    """

    Args:
        window: a window size (unit: date)
        tag: a str
        key: a str, which is one of "viewcount", "commentcount", "answercount"

    Returns:
        a list of Gini coefficients
    """
    date_str_list = get_datetime_strings_before_and_after_gpt(window)
    to_return = []
    for i in range(len(date_str_list)-1):
        date_range = (date_str_list[i], date_str_list[i+1])
        list_ = get_data_sublist_in_date_range(date_range)
        count, gini = get_data_count_and_gini_coefficient_for_tag(
            list_=list_, tag=tag, key=key
        )
        to_return.append(gini)
    return to_return


def moving_average(list_, window_size):
    to_return = []
    for i in range(len(list_)):
        if i - window_size < 0:
            start_idx = 0
        else:
            start_idx = i - window_size
        if i + window_size > len(list_):
            end_idx = len(list_)
        else:
            end_idx = i + window_size
        to_calc = list_[start_idx:end_idx]
        to_append = sum(to_calc)/len(to_calc)
        to_return.append(to_append)
    return to_return


if __name__ == "__main__":
    fig = plt.figure()
    keys = ["viewcount", "commentcount", "answercount"]
    tags_info = DataLoader.load_json("../data/tag_info/tag_info.json")
    tags = list(tags_info.keys())[:100]
    to_draw_line = random.sample(tags[1:50], 4)
    to_draw_line = [tags[0]] + to_draw_line
    colors = color_map(np.linspace(0, 1, len(to_draw_line)))
    key = keys[1]
    idx = 0
    for tag in tqdm(tags):
        y = collect_gini_coefficient_for_tag(7, tag, key)
        x = list(range(len(y)))
        plt.scatter(x, y, color="grey", alpha=0.3, s=5)
        if tag in to_draw_line:
            y_ma = moving_average(y, 5)
            plt.plot(x, y_ma, color=colors[idx], alpha=0.7, label=tag)
            idx += 1
    plt.ylim([0.15, 0.9])
    plt.legend()
    plt.savefig("./figs/gini_per_tags_comment_answer.png", dpi=300)
