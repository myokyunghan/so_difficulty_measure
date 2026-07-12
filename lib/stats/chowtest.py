import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import f
from scipy.stats import t
import matplotlib.pyplot as plt


class ChowTest:
    def __init__(self, x, y, c, cutoff):
        self.x                  = x
        self.y                  = y
        self.dof                = len(x)-2
        self.split_idx          = int(len(x)/2) if cutoff is None else cutoff
        self.c                  = c

        self.y_predict          = 0
        self.y1_predict         = 0
        self.y2_predict         = 0
        
        self.y1_conf_interval   = 0
        self.y2_conf_interval   = 0 


    def chow_test(self):
        """

        Args:

        Returns:
            a str with all tags removed
        """
        x1, y1 = self.x[:self.split_idx], self.y[:self.split_idx]
        x2, y2 = self.x[self.split_idx:], self.y[self.split_idx:]
        
        # 회귀 모델 생성
        x_const = sm.add_constant(self.x)
        x1_const = sm.add_constant(x1)
        x2_const = sm.add_constant(x2)

        model_full = sm.OLS(self.y, x_const).fit()
        model1 = sm.OLS(y1, x1_const).fit()
        model2 = sm.OLS(y2, x2_const).fit()

        # # 잔차 제곱합 계산
        RSS_full = np.sum(model_full.resid ** 2)
        RSS_1 = np.sum(model1.resid ** 2)
        RSS_2 = np.sum(model2.resid ** 2)

        # 자유도 계산
        self.dof = int(model_full.df_model) + 1
        n1, n2 = len(y1), len(y2)
        F_stat = ((RSS_full - (RSS_1 + RSS_2)) / self.dof) / ((RSS_1 + RSS_2) / (n1 + n2 - 2 * self.dof))
        p_value    = 1 - f.cdf(F_stat, self.dof, n1 + n2 - 2 * self.dof)

        self.y_predict  = model_full.predict(x_const)
        self.y1_predict = model1.predict(x1_const)
        self.y2_predict = model2.predict(x2_const)
        

        self.y1_conf_interval = self.calc_ci(x1, y1, self.y1_predict)
        self.y2_conf_interval = self.calc_ci(x2, y2, self.y2_predict)

        return F_stat, p_value




    def calc_ci(self, x, y, y_predict):
        """

        Args:
            cl: confidence level

        Returns:
            a list with confidence interval
        """
        # 신뢰구간 계산
        confidence = self.c
        n = len(x)
        dof = n -2  # 자유도: 데이터 포인트 개수 - 2

        mean_x = np.mean(x)
        
        t_value = t.ppf((1 + confidence) / 2., dof)
        s_err = np.sqrt(np.sum((y - y_predict) ** 2) / dof)
        
        Sxx = np.sum((x - mean_x)**2)
        
        conf_interval = t_value * s_err * np.sqrt(
            1/n + (x - mean_x)**2 / Sxx
        )
        
        return conf_interval