import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import f
from scipy.stats import t
import matplotlib.pyplot as plt
import lib.visualization.figure_setting as figure_setting

class ITS:
    def __init__(self, y_col, data):
        
        self.y_col                  = y_col
        self.data                   = data
        self.model                  = None

        self.set_param()



    def set_param(self) : 

        self.data['t'] = self.data['rel_week']
        self.data['post'] = (self.data['t'] >= 0).astype(int)
        self.data['post_t'] = self.data['post'] * self.data['t']

    def set_tot_its_model(self):
        """

        Args:

        Returns:
            a ITS model 
        """
        self.model = smf.ols(f'{self.y_col} ~ t + post + post_t + C(language)', data=self.data).fit(
            cov_type='cluster', cov_kwds={'groups': self.data['language']}
        )

    def set_indi_its_model(self):
        """

        Args:

        Returns:
            a ITS model 
        """
        self.model = smf.ols(f'{self.y_col} ~ t + post + post_t', data=self.data).fit(
            cov_type='HAC', cov_kwds={'maxlags': 4}
        )
    
    def get_indi_its_result(self, language, WEEKS_PER_YEAR = 52):

        return {
        'language':         language,
        'n_func':           self.data['n_func'].sum(),
        'n_obs':            len(self.data),
        
        # Pre-trend
        'pre_trend':        self.model.params['t'],
        'pre_trend_p':      self.model.pvalues['t'],
        
        # Level change
        'level_change':     self.model.params['post'],
        'level_change_se':  self.model.bse['post'],
        'level_change_p':   self.model.pvalues['post'],
        'level_change_pct': self.beta_to_pct(self.model.params['post']),
        

        'slope':     self.model.params['post_t'],
        'se':  self.model.bse['post_t'],

        'slope_yr' : self.model.params["post_t"] * WEEKS_PER_YEAR,
        'se_yr'   : self.model.bse['post_t']    * WEEKS_PER_YEAR,
        'pct'     : (np.exp(self.model.params["post_t"] * WEEKS_PER_YEAR) - 1) * 100,
        'ci_low'  : (np.exp(self.model.params["post_t"] * WEEKS_PER_YEAR - 1.96*self.model.bse['post_t']    * WEEKS_PER_YEAR) - 1) * 100,
        'ci_high' : (np.exp(self.model.params["post_t"] * WEEKS_PER_YEAR + 1.96*self.model.bse['post_t']    * WEEKS_PER_YEAR) - 1) * 100,
        'p_value' : self.model.pvalues['post_t'],
        'significant' : self.model.pvalues['post_t'] < 0.05,

        'color_slope' : self.get_color(self.model.pvalues['post_t'] < 0.05, (np.exp(self.model.params["post_t"] * WEEKS_PER_YEAR) - 1) * 100),
        'alpha' : 1.0 if self.model.pvalues['post_t'] < 0.05 else 0.5


    }




    def get_tot_model_coef(self, weight_yn = False, weight_col = None):
        coef = self.data.copy()
        coef['post'] = 0; coef['post_t'] = 0
        coef['y_cf'] = self.model.predict(coef)
        coef['eff_pct'] = (np.exp(coef[self.y_col] - coef['y_cf']) - 1) * 100

        if weight_yn :  
            t_obs = coef.groupby('t').apply(
                lambda g: pd.Series({'eff': np.average(g['eff_pct'], weights=g[weight_col])}), include_groups=False
            ).reset_index()
        else : 
            t_obs = coef.groupby('t').apply(
                lambda g: pd.Series({'eff': np.average(g['eff_pct'])}),
                include_groups=False
            ).reset_index()

        return t_obs
    
    def get_tot_model_coef_se(self, week_range):
        """ITS 효과 = β_post + β_post_t × t, 시점별 SE는 delta method"""
        
        β_p, β_pt = self.model.params['post'], self.model.params['post_t']
        cov = self.model.cov_params()
        v_p, v_pt = cov.loc['post','post'], cov.loc['post_t','post_t']
        c_p_pt    = cov.loc['post','post_t']
    
        eff = np.where(week_range >= 0, β_p + β_pt * week_range, 0.0)
        var = np.where(week_range >= 0,
                    v_p + (week_range**2)*v_pt + 2*week_range*c_p_pt, 0.0)
        se  = np.sqrt(np.maximum(var, 0))

        return pd.DataFrame({
            't':          week_range,
            'effect_pct': (np.exp(eff)      - 1) * 100,
            'ci_low_pct': (np.exp(eff-1.96*se) - 1) * 100,
            'ci_high_pct':(np.exp(eff+1.96*se) - 1) * 100,
        })  
    
    def beta_to_pct(self, b): return (np.exp(b) - 1) * 100


    def get_color(self, significant, pct):
        if not significant:
            return figure_setting.PALETTE['neutral']
        elif pct > 0:
            return figure_setting.PALETTE['accent']
        else:
            return figure_setting.PALETTE['primary']