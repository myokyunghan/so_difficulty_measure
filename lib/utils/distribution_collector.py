from lib.utils.datetime_handler import *
from lib.utils.statistics import (get_monthly_topics_counts, get_topics_counts,
                              get_tags_counts, get_fractional_values_dict)
from lib.utils.file_io import *
from lib.utils.sublist import get_sublist_of_desired_date_range, \
    get_sublist_of_desired_difficulties
import sys, os


import pickle

def get_top_and_bottom_topics(data_dir):
    """

    Args:
        data_dir: a str

    Returns:
        a couple of
            index of top 10 topics,
            index of bottom 10 topics
    """
    monthly_count = get_monthly_topics_counts(data_dir, list(range(0, 50)))
    before_gpt_count = {topic: sum(monthly_count[topic][:12]) for topic in
                        monthly_count}
    sorted_topics = [k for k, v in sorted(before_gpt_count.items(),
                                          key=lambda item: item[1],
                                          reverse=True)]
    return sorted_topics[:10], sorted_topics[-10:]


def get_topic_distribution_in_date_range(date_range, data_dir, topics, weekday_list, options):
    """

    Args:
        date_range: a couple of datetime strings
        data_dir: a str
        topics: a list of int

    Returns:
        a topic distribution in given date range
    """
    
    if options is None:
        options = {}
    if weekday_list is None:
        weekday_list = []
    file_list = get_related_files(date_range, data_dir)
    list_ = []

    for i in file_list:
        file_path = f"{data_dir}/{i}"
        json_list = load_json(file_path)
        list_ += json_list
    list_ = get_sublist_of_desired_date_range(list_, date_range, weekday_list)

    if 'difficulties' in options:
        list_ = get_sublist_of_desired_difficulties(
            list_, options['difficulties']
        )
    to_return = get_topics_counts(list_, topics)
    to_return = get_fractional_values_dict(to_return)
    return to_return


def collect_topic_distributions(window, data_dir, weekday_list = None, options=None):
    """

    Args:
        window: a window size (unit: date)
        data_dir: a str

    Returns:
        a list of dict
    """
    all_topics = CONSTANTS.all_topics_list
    date_str_list = get_datetime_strings_before_and_after_gpt(window)
    to_return = []
    for i in range(len(date_str_list)-1):
        date_range = (date_str_list[i], date_str_list[i+1])
        print(f"date_range: {date_range}")
        topic_distribution = get_topic_distribution_in_date_range(
            date_range, data_dir, all_topics, weekday_list, options)
        if len(topic_distribution) != 0 :
            to_return.append(topic_distribution)
        
    return to_return


def extract_specific_topics(dict_, topics):
    """

    Args:
        dict_: a topic distribution dict
        topics: a list of int

    Returns:
        a topic distribution dict (only containing desired topics)
    """
    to_return = {topic: dict_[topic] for topic in topics}
    return to_return


def get_tag_distribution_in_date_range(date_range, data_dir, tags, weekday_list, options):
    """

    Args:
        date_range: a couple of datetime strings
        data_dir: a str
        tags: a list of str

    Returns:
        a topic distribution in given date range
    """
    if options is None:
        options = {}
    if weekday_list is None:
        weekday_list = []
    file_list = get_related_files(date_range, data_dir)
    list_ = []
    for i in file_list:
        file_path = f"{data_dir}/{i}.json"
        json_list = load_json(file_path)
        list_ += json_list
    list_ = get_sublist_of_desired_date_range(list_, date_range, weekday_list)
    # print(f">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>options chk : {options}")
    if 'difficulties' in options:
        list_ = get_sublist_of_desired_difficulties(
            list_, options['difficulties']
        )

    to_return = get_tags_counts(list_, tags)
    to_return = get_fractional_values_dict(to_return)
    return to_return

def collect_tag_distributions(window, tag_info, data_dir, week_day_list=None, options=None):
    """

    Args:
        window: a window size (unit: date)
        data_dir: a str

    Returns:
        a list of dict
    """
    tag_info = load_json(tag_info)
    print(type(tag_info))
    all_tags = list(tag_info.keys())
    date_str_list = get_datetime_strings_before_and_after_gpt(window)
    to_return = []
    for i in range(len(date_str_list)-1):
        date_range = (date_str_list[i], date_str_list[i+1])
        topic_distribution = get_tag_distribution_in_date_range(
            date_range, data_dir, all_tags, week_day_list, options)
        if len(topic_distribution) != 0 :
                to_return.append(topic_distribution)
    return to_return
