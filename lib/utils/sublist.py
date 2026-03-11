import re
from lib.utils.datetime_handler import (is_weekday, is_target_weekday, get_const_to_date, get_creationdate_to_date)


def get_sublist_of_desired_date_range(list_, date_range, weekday_list):
    """

    Args:
        list_: a list of dict, where each dict has the key "creationdate"
        date_range: a tuple (str, str)

    Returns:
        a list of dict
    """
    to_return = []

    start_date = get_const_to_date(date_range[0])
    end_date = get_const_to_date(date_range[1])
    

    for dict_ in list_:
        date_ = get_creationdate_to_date(dict_["creationdate"])
        if start_date <= date_ < end_date:
            if len(weekday_list)>0 : 
                for weekday in weekday_list : 
                    if is_target_weekday(date_, weekday):
                        to_return.append(dict_)
            else : 
                to_return.append(dict_)
    return to_return


def get_sublist_of_desired_topics(list_, topics):
    """

    Args:
        list_: a list of dict, where each dict has the key "Topic"
        topics: a list of int

    Returns:
        a list of dict
    """
    to_return = []
    for dict_ in list_:
        topic = dict_["Topic"]
        if topic in topics:
            to_return.append(dict_)
    return to_return


def get_sublist_of_desired_tags(list_, tags):
    """

    Args:
        list_: a list of dict, where each dict has the key "tags"
        tags: a list of str

    Returns:
        a list of dict
    """
    to_return = []
    for dict_ in list_:
        dict_tags = re.findall(
            pattern='<(.*?)>',
            string=dict_["tags"]
        )
        if len(set(dict_tags) & set(tags)) > 0:
            to_return.append(dict_)
    return to_return



def get_sublist_of_desired_difficulties(list_, difficulties):
    """

    Args:
        list_: a list of dict, where each dict has the key "tags"
        difficulties: a list of str

    Returns:
        a list of dict
    """
    to_return = []
    for dict_ in list_:
        if dict_["difficulty"] in difficulties:
            to_return.append(dict_)
    return to_return
