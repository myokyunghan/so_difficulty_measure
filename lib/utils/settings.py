import matplotlib as mpl
import os
import sys


def set_matplotlib():
    """

    Args:

    Returns:
        
    """
    # mpl.rcParams['font.family'] = 'serif'
    # mpl.rcParams['font.serif'] = ['Times New Roman']
    mpl.rcParams['axes.labelsize'] = 12
    mpl.rcParams['axes.titlesize'] = 14
    mpl.rcParams['xtick.labelsize'] = 10
    mpl.rcParams['ytick.labelsize'] = 10
    mpl.rcParams['legend.fontsize'] = 10



def set_os_path(path):
    """
    Set the os path to the given path.

    Args: str 
    """

    if os.path.exists(path):
        sys.path.append(path)
    else:
        raise FileNotFoundError(f"Path {path} does not exist.")
