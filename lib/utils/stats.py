import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.stats import f
from scipy.stats import t
import matplotlib.pyplot as plt


class Stats:
    def __init__(self, x, y, dof, c):
        self.x                  = x
        self.y                  = y
        self.dof                = dof
        self.split_idx          = np.argmax(np.where(x < 0))+1
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
        k = self.dof  # 독립 변수 개수 (상수항 포함)
        n1, n2 = len(y1), len(y2)
        F_stat = ((RSS_full - (RSS_1 + RSS_2)) / k) / ((RSS_1 + RSS_2) / (n1 + n2 - 2 * k))
        p_value    = 1 - f.cdf(F_stat, k, n1 + n2 - 2 * k)

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
        mean_x = np.mean(x)
        dof = n - 2  # 자유도: 데이터 포인트 개수 - 2
        t_value = t.ppf((1 + confidence) / 2., dof)  # 자유도를 명시적으로 추가
        s_err = np.sqrt(np.sum((y - y_predict) ** 2) / dof)
        conf_interval = t_value * np.sqrt(
            s_err**2 * (1/n + (x - mean_x)**2 / np.sum((x - mean_x)**2))
        )

        return conf_interval