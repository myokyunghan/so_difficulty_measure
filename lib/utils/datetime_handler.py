from setting_for_sdm.constants import CONSTANTS
from datetime import datetime, timedelta
from lib.utils.file_io import *
import os


def get_datetime_strings_before_and_after_gpt(window=7):
    """

    Returns:
        list of str, where each str are weekly datetime strings
    """
    chatgpt_release_date \
        = datetime.strptime(CONSTANTS.chatgpt_release_date, '%Y.%m.%d')
    start_date = datetime.strptime(CONSTANTS.start_date, '%Y.%m.%d')
    end_date = datetime.strptime(CONSTANTS.end_date, '%Y.%m.%d')
    to_return = []
    range_num = (chatgpt_release_date-start_date).days // window
    for i in range(-window*range_num, 0, window):
        to_append = chatgpt_release_date + timedelta(days=i)
        to_return.append(str(to_append))
    range_num = (end_date-chatgpt_release_date).days // window + 1
    for i in range(0, window*range_num, window):
        to_append = chatgpt_release_date + timedelta(days=i)
        to_return.append(str(to_append))
    print(to_return)
    return to_return


def get_monthly_datetime_str():
    """

    Returns:
        a list of str
    """
    timestamps = CONSTANTS.monthly_timestamps
    to_return = []
    for timestamp in timestamps:
        time_str = str(datetime.strptime(timestamp, '%Y.%m.%d'))
        to_return.append(time_str)
    return to_return

def get_const_to_date(const_date):
    """

    Args:
        const_date: date in const("2021.11.30")

    Returns:
        a datetime
    """
    return datetime.strptime(const_date, "%Y-%m-%d %H:%M:%S")

def get_creationdate_to_date(creationdate):
    """

    Args:
        creationdate: creationdate in question("2021-11-30T00:16:44.513000")

    Returns:
        a datetime
    """
    return datetime.fromisoformat(creationdate)

def get_related_files(date_range, data_dir):
    """

    Args:
        date_range: a couple of string

    Returns:
        a list of string
    """
    monthly_datetime_str = get_monthly_datetime_str()
    start_date = date_range[0]
    end_date = date_range[1]
    to_return = []
    
    lst = os.listdir(data_dir)
    for i in range(len(lst)):
        
        loaded = load_json(f'{data_dir}/{lst[i]}')
        
        # print(f">>>>>>>>>>>>>>>>>get_related_files> f'{data_dir}/9.json")
        min_dt = get_creationdate_to_date(min([x['creationdate'] for x in loaded]))
        max_dt = get_creationdate_to_date(max([x['creationdate'] for x in loaded]))

        # print(f">>>>>>>>>>>>>>>>>get_related_files> min_dt>'{min_dt}")
        # print(f">>>>>>>>>>>>>>>>>get_related_files> max_dt>'{max_dt}")
        st_dt = get_const_to_date(start_date)
        end_dt = get_const_to_date(end_date)

        # print(f">>>>>>>>>>>>>>>>>get_related_files> st_dt>'{st_dt}")
        # print(f">>>>>>>>>>>>>>>>>get_related_files> end_dt>'{end_dt}")

        intersection_start = max(min_dt, st_dt)
        intersection_end = min(max_dt, end_dt)

        # print(f">>>>>>>>>>>>>>>>>get_related_files> intersection_start>'{intersection_start}")
        # print(f">>>>>>>>>>>>>>>>>get_related_files> intersection_end>'{intersection_end}")

        if intersection_start <= intersection_end:
            to_return.append(lst[i])
    return to_return

def is_weekday(date_str):
    """

    Returns:
        Boolean
    """
    return datetime.strptime(date_str[:10], '%Y-%m-%d').weekday() < 5

def is_target_weekday(date_str, weekday):
    """
    Returns:
        Boolean
    """
    return datetime.strptime(date_str[:10], '%Y-%m-%d').weekday() == weekday





if __name__ == '__main__':
    print(get_datetime_strings_before_and_after_gpt(1))
    print(len(get_datetime_strings_before_and_after_gpt(1)))
