import statsmodels.api as sm

class LS:
    def __init__(self, x, y):
        
        self.x                  = x
        self.y                  = y
        self.model              = None


    def conduct_ols(self):
        X = sm.add_constant(self.x )
        self.model = sm.OLS(self.y , X).fit()


    def conduct_wls(self, weight):
        X = sm.add_constant(self.x )
        self.model = sm.WLS(self.y , X, weights = weight).fit()

    def get_prediction(self, xx):
        X_pred = sm.add_constant(xx)
        pred = self.model.get_prediction(X_pred)
        pred_summary = pred.summary_frame(alpha=0.05)

        return {'yy'        : pred_summary['mean'].values,
                'ci_low'    : pred_summary['mean_ci_lower'].values,
                'ci_high'   : pred_summary['mean_ci_upper'].values
                }
    
    def get_ls_result(self):
        return {
            'slope_fit':     self.model.params.iloc[1],   # const 다음이 x
            'intercept_fit': self.model.params.iloc[0],
            'p_val':         self.model.pvalues.iloc[1],
            'r_squared':     self.model.rsquared,
        }