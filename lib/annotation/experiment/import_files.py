import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
import multiprocessing as mp

import logging
import numpy as np
import pandas as pd
import datetime
import itertools


import xml.etree.ElementTree as et 
import warnings
warnings.filterwarnings(action='ignore')
import numpy as np
import re



import psycopg2
import psycopg2.extras
import sqlalchemy as sa
from sqlalchemy import create_engine

import datetime
from time import time
from datetime import datetime


from config import config as conf



import warnings
import langchain
from langchain_ollama.llms import OllamaLLM
from langchain_core.prompts.few_shot import FewShotPromptTemplate
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
import pandas as pd
import numpy as np
from tqdm import tqdm
import time
from ollama import chat
from openai import OpenAI

warnings.filterwarnings("ignore", category=DeprecationWarning)
# https://wikidocs.net/233348
from itertools import chain

import pickle
import json

from lib.annotation.prompt import *
from lib.annotation.param import *
from lib.annotation.sequence import *

import lib.preprocess.preprocess as pp
import lib.preprocess.SectionExtractor as se
from lib.annotation.excel import *
from lib.annotation.loghander import *

import lib.annotation.D_Annotation as da
import lib.annotation.Self_Consistency as sc
import lib.annotation.Sample_Insert as si
import lib.annotation.Q_Extract as qe
import lib.annotation.SampleSelf_Consistency as ssc

import lib.database.DBConn as db_conn

import utils.file_io as file_io

from transformers import AutoTokenizer
