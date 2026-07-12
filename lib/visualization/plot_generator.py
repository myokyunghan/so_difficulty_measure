import os.path
import numpy as np
from matplotlib import pyplot as plt
import seaborn as sns
from setting_for_sdm.color_setting import Color_Setting
from lib.utils.statistics import *
import lib.stats.chowtest as st
import lib.visualization.figure_setting as figure_setting
from setting_for_sdm.path_setting import path_list
from setting_for_sdm.date_setting import Date_Setting


class PlotGen:
    def __init__(self, save_dir_root=None):
        if save_dir_root is not None:
            self.save_dir_root = save_dir_root
        else:
            self.save_dir_root = "./fig"
        if not os.path.exists(self.save_dir_root):
            os.makedirs(self.save_dir_root)        

    def draw_errorbar(self, ax, pos, coef, yerr, color=None, sig=True):
        ax.errorbar(pos, coef,
                    yerr=yerr,
                    fmt='o', 
                    color=color, 
                    markersize=8, capsize=4,
                    capthick=1.3, lw=1.3,
                    markerfacecolor=color if sig else 'white',
                    markeredgecolor=color, markeredgewidth=1.5,
                    zorder=3)

    def draw_scatter_plot(self, ax, x, y):
        ax.scatter(x, y, s=1.5, color=figure_setting.PALETTE['neutral'],
        alpha=0.50, lw=0, zorder=2, clip_on=False)

    def draw_line_plot(self, ax, x, y, label=None, color=None, opt=None):
        if color is None:
            color = figure_setting.PALETTE['neutral']
        if opt == 'overall':
            ax.plot(x, y,
            color=color, lw=0.9, ls='--',
            alpha=0.65, zorder=4, label=label)    
        else :
            ax.plot(x, y,
            color=color, lw=2.0,
            zorder=5, label=label)
    
    
    def fill_confidence_interval(self, ax, x, ci_low, ci_high, label=None, color = None):
        if color is None:
            color = figure_setting.PALETTE['primary']
        ax.fill_between(x,
                            ci_low,
                            ci_high,
                            color=color, alpha=0.25, lw=0, zorder=4)
    
    def draw_vertical_line(self, ax, x, label=None):
        ax.axvline(x=0, color=figure_setting.PALETTE['event'],
               linestyle='--', linewidth=0.9, zorder=1)
    
    def set_title(self, ax, prefix=None, title_text=None, p_value=None):
        if p_value is not None:
            p_txt = '($p$ < 0.001)' if p_value < 0.001 else ( 'n.s.' if p_value >= 0.05 else f'$p$ = {p_value:.3f}')
        else:
            p_txt = None

        full_title = ''
        if prefix:
            full_title += f'{prefix}.  '
        if title_text:
            full_title += title_text
        if p_txt:
            full_title += f'  ({p_txt})'

        ax.set_title(full_title,
                    fontsize=figure_setting.FONT['title'],
                    loc='left', pad=6, color='#222',
                    fontweight='normal')
        
    def set_spines(self, ax):
        ax.tick_params(width=0.6, length=2.5, pad=2) 

        for s in ['top', 'right']:
            ax.spines[s].set_visible(False)
        ax.spines['left'].set_linewidth(0.6)
        ax.spines['bottom'].set_linewidth(0.6)
        ax.spines['left'].set_position(('outward', 3))
        ax.spines['bottom'].set_position(('outward', 3))

        ax.grid(False)

            

    def set_lims(self, ax, x, y):
        # ── set x lim
        ax.set_xlim(x.min(), x.max())
        ax.margins(x=0.02, y=0.05)

    def set_xticks(self, ax, x_tick_list):
        # ── set x lim
        ax.set_xticks(x_tick_list)


    def set_title_two_lines(self, ax, prefix=None, title_text=None, p_value=None, gap=0.04):
        if p_value is not None:
            p_txt = '($p$ < 0.001)' if p_value < 0.001 else ( '(n.s.)' if p_value >= 0.05 else f'($p$ < 0.05)')
        else:
            p_txt = None

        ax.text(0.0, 1.0 + gap + 0.08, title_text,
                transform=ax.transAxes,
                fontsize=figure_setting.FONT['title'],
                ha='left', va='bottom',
                color='#222', fontweight='normal')
        
        # 둘째 줄 (아래, 조금 작게)
        if p_txt:
            ax.text(0.0, 1.0 + gap, f'{p_txt}',
                    transform=ax.transAxes,
                    fontsize=figure_setting.FONT['title'] - 2,
                    ha='left', va='bottom',
                    color='#555', fontweight='normal')
