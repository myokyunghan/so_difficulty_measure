import os.path
import numpy as np
from matplotlib import pyplot as plt
import seaborn as sns
from setting_for_sdm.color_setting import Color_Setting
from lib.utils.statistics import *
import lib.stats.stats as st
from lib.visualization.font_setting import font_setting


class PlotGen:
    def __init__(self, save_dir_root=None):
        if save_dir_root is not None:
            self.save_dir_root = save_dir_root
        else:
            self.save_dir_root = "./figs"
        if not os.path.exists(self.save_dir_root):
            os.makedirs(self.save_dir_root)
        self.colors = Color_Setting.color_list

    @staticmethod
    def save_figure(path, fig):
        """

        Args:
            path: a str
            fig: a matplotlib figure

        Returns:
            None
        """
        print(f"[Saving] {path}")
        fig.savefig(path, dpi=600)

    @staticmethod
    def set_title_and_labels(title, x_label, y_label):
        """

        Args:
            title: a str
            x_label: a str
            y_label: a str

        Returns:
            None
        """
        plt.title(title, fontsize=font_setting['title'])
        if x_label is not None:
            plt.xlabel(x_label, fontsize=font_setting['label'])
        if y_label is not None:
            plt.ylabel(y_label, fontsize=font_setting['label'])

    def draw_trend_line_and_get_rho(self, x, y, deg=1):
        """

        Args:
            x: a list of numbers
            y: a list of numbers
            deg: a positive int

        Returns:
            a float
        """
        z = np.polyfit(x, y, deg)
        p = np.poly1d(z)
        plt.plot(x, p(x), color="black", linewidth=2)
        rho = np.corrcoef(x, y)[0, 1]
        return rho

    # def draw_scatter_plot(self, x, y, title, x_label=None, y_label=None):
    #     """

    #     Args:
    #         x: a list of int
    #         y: a list of numbers (int or float)
    #         title: a str
    #         x_label: a str
    #         y_label: a str

    #     Returns:
    #         None
    #     """
    #     fig = plt.figure()
    #     x_bef, y_bef = x[:52], y[:52]
    #     x_aft, y_aft = x[52:], y[52:]
    #     plt.scatter(x_bef, y_bef, s=20, alpha=0.5, c="blue")
    #     self.draw_trend_line_and_get_rho(x_bef, y_bef, deg=1)
    #     plt.scatter(x_aft, y_aft, s=20, alpha=0.5, c="red")
    #     self.draw_trend_line_and_get_rho(x_aft, y_aft, deg=1)
    #     self.set_title_and_labels(title, x_label, y_label)
    #     self.save_figure(f"{self.save_dir_root}/{title}.png", fig)
    #     plt.close(fig)

    def draw_scatter_plot_with_trend_line(self, x, y, title, x_label=None,
                                          y_label=None):
        """

        Args:
            x: a list of int
            y: a list of numbers (int or float)
            title: a str
            x_label: a str
            y_label: a str

        Returns:
            a float (pearson correlation)
        """
        fig = plt.figure()
        plt.scatter(x, y, c="orange", s=5, alpha=0.2)
        rho = self.draw_trend_line_and_get_rho(x, y, deg=1)
        self.set_title_and_labels(title, x_label, y_label)
        plt.ylim([-1, 1])
        self.save_figure(f"{self.save_dir_root}/{title}.png", fig)
        plt.close(fig)
        return rho

    def draw_bar_plot(self, x, y, title, x_label=None, y_label=None):
        """

        Args:
            x: a list of int
            y: a list of numbers (int or float)
            title: a str
            x_label: a str
            y_label: a str

        Returns:
            None
        """
        fig = plt.figure()
        plt.bar(x, y, c=self.colors[0])
        self.set_title_and_labels(title, x_label, y_label)
        self.save_figure(f"{self.save_dir_root}/{title}.png", fig)
        plt.close(fig)

    def draw_stacked_bar_plot(self, x, y_dict, title, x_label=None,
                              y_label=None):
        """

        Args:
            x: a list of int
            y_dict: a dict where values are list of numbers, e.g.,
                    {
                        "python": [0.3, 0.4, 0.4, ...],
                        "java": [0.3, 0.3, 0.2, ...],
                    }
            title: a str
            x_label: a str
            y_label: a str

        Returns:
            None
        """
        fig, ax = plt.subplots()
        y_length = len(list(y_dict.values())[0])
        bottom = np.array([0.0]*y_length)
        for topic, count in y_dict.items():
            p = ax.bar(x, count, bottom=bottom, label=topic)
            bottom += count
        box = ax.get_position()
        ax.set_position([box.x0, box.y0, box.width * 0.8, box.height])
        ax.legend(loc='center left', bbox_to_anchor=(1, 0.5))
        self.set_title_and_labels(title, x_label, y_label)
        self.save_figure(f"{self.save_dir_root}/{title}.png", fig)

    def draw_scatter_plot_with_confidence_interval(self, x, y, title,
                                                   x_label=None, y_label=None):
        """

        Args:
            x: a list of int
            y: a list of numbers (int or float)
            title: a str
            x_label: a str
            y_label: a str

        Returns:
            None
        """
        fig = plt.figure()
        sns.regplot(x=x, y=y, scatter_kws={"alpha": 0.5,
                                           "color": self.colors[0]})
        self.set_title_and_labels(title, x_label, y_label)
        self.save_figure(f"{self.save_dir_root}/{title}.png", fig)
        plt.close(fig)

    def draw_regression(self, ax, title, series, panel_label=''):
        x_rel, divider = get_dist_x_div(series)

        reg_bf = calc_regression_with_ci(x_rel[:divider], series[:divider])
        reg_af = calc_regression_with_ci(x_rel[divider:], series[divider:])

        bf = reg_bf["pred_summary"]
        af = reg_af["pred_summary"]

        ax.scatter(x_rel, series, color='darkgray', alpha=0.7, s=10, marker='x')

        ax.plot(x_rel[:divider], bf["mean"], linewidth=1.5, label='Before ChatGPT')
        ax.plot(x_rel[divider:], af["mean"], linewidth=1.5, label='After ChatGPT')

        ax.fill_between(x_rel[:divider], bf["mean_ci_lower"], bf["mean_ci_upper"], alpha=0.15)
        ax.fill_between(x_rel[divider:], af["mean_ci_lower"], af["mean_ci_upper"], alpha=0.15)

        ax.axvline(x=0, color='#CC3333', linestyle='--', linewidth=1.2, zorder=5)

        # Chow test
        st_0 = st.Stats(np.arange(-52, 52), series, 2, 0.95)
        F_stat, p_value = st_0.chow_test()
        p_txt = '$p < 0.001$' if p_value < 0.001 else f'$p = {p_value:.3f}$'

        # 제목 — 폰트 크기 통일
        # ax.set_title(f'Changes in {title} (topic)', fontsize=font_setting['title'], pad=22)
        ax.text(0.5, 1.08, f'Changes in {title} (topic)',
            transform=ax.transAxes,
            fontsize=font_setting['title'], ha='center', va='bottom')

        # p-value — 제목 아래 별도 텍스트 (유의 여부에 따라 색상 구분)
        p_color = '#CC3333' if p_value < 0.05 else 'gray'
        ax.text(0.5, 1.02, p_txt,
                ha='center', fontsize=font_setting['p-value'], color=p_color,
                transform=ax.transAxes)
                    
        # 패널 레이블
        if panel_label:
            ax.text(-0.08, 1.08, panel_label,
                    transform=ax.transAxes,
                    fontsize=font_setting['panel'], fontweight='bold',
                    va='bottom', ha='left')

        # X축 레이블
        # ax.set_xlabel('Week relative to ChatGPT release', fontsize=9)

        # 축 폰트
        ax.tick_params(axis='both', labelsize=font_setting['tick'])

        # spine 정리
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        # 그리드
        ax.yaxis.grid(True, linestyle=':', linewidth=0.5, color='gray', alpha=0.5, zorder=0)
        ax.set_axisbelow(True)

        # 범례 (첫 번째 regression 패널에만 표시하고 싶으면 조건 추가)
        ax.legend(fontsize=font_setting['legend'], frameon=False)

        
    # def draw_regression(self, ax, title, series): 
    #     x_rel, divider = get_dist_x_div(series)

    #     reg_bf = calc_regression_with_ci(x_rel[:divider], series[:divider])
    #     reg_af = calc_regression_with_ci(x_rel[divider:], series[divider:])

    #     bf = reg_bf["pred_summary"]
    #     af = reg_af["pred_summary"]

    #     ax.scatter(x_rel, series, color='darkgray', alpha=0.7, s=10, marker='x')

    #     ax.plot(x_rel[:divider], bf["mean"], linewidth=2)
    #     ax.plot(x_rel[divider:], af["mean"], linewidth=2)

    #     ax.fill_between(x_rel[:divider], bf["mean_ci_lower"], bf["mean_ci_upper"], alpha=0.1)
    #     ax.fill_between(x_rel[divider:], af["mean_ci_lower"], af["mean_ci_upper"], alpha=0.1)

    #     ax.axvline(x=0, color='tab:red', linestyle='-.', linewidth=1)

    #     # chow test
    #     st_0 = st.Stats(np.arange(-52, 52), series, 2, 0.95)
    #     F_stat, p_value = st_0.chow_test()

    #     p_txt = '($p < 0.001$)' if p_value < 0.001 else f'($p = {p_value:.3f}$)'

    #     ax.text(
    #         0.5, 1.05,
    #         f"Changes in {title} (topic)",
    #         ha='center',
    #         fontsize=22,
    #         transform=ax.transAxes
    #     )

    #     ax.text(
    #         0.5, 1.00,
    #         p_txt,
    #         ha='center',
    #         fontsize=15,
    #         transform=ax.transAxes
    #     )

    #     ax.tick_params(axis='both', labelsize=16)

    def draw_topic_stack(self, ax, title, panel_label, proportion, order_list, colors, alpha=0.9):
        rel_week = sorted(proportion['rel_week'].unique())
        bottom = np.zeros(len(rel_week))

        for idx, topic in enumerate(order_list):
            t_p = proportion[proportion['Topic'] == topic]

            count_full = np.zeros(len(rel_week))
            for i, rw in enumerate(t_p['rel_week']):
                if rw in rel_week:
                    rw_idx = rel_week.index(rw)
                    count_full[rw_idx] = t_p.loc[t_p['rel_week'] == rw, 'proportion'].values[0]

            ax.bar(
                rel_week,
                count_full,
                bottom=bottom,
                label=topic,
                color=colors[idx],
                width=1.0,
                align='center',
                alpha=alpha,
                linewidth=0,         
            )
            bottom += count_full


        ax.set_ylim(0, bottom.max() * 1.05)


        ax.axvline(x=0, color='#CC3333', linestyle='--', linewidth=1.2, zorder=5)


        ax.text(-0.08, 1.08, panel_label,
                transform=ax.transAxes,
                fontsize=font_setting['panel'], fontweight='bold',
                va='bottom', ha='left')


        ax.text(0.5, 1.08, f'{title}',
            transform=ax.transAxes,
            fontsize=font_setting['title'], ha='center', va='bottom')


        # 축 폰트 통일 (7–9pt 권장, Nature/Science 기준)
        ax.tick_params(axis='both', labelsize=font_setting['tick'])





        # 불필요한 테두리 제거 (top, right spine)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        # 가로 그리드 (옅게)
        ax.yaxis.grid(True, linestyle=':', linewidth=0.5, color='gray', alpha=0.5, zorder=0)
        ax.set_axisbelow(True)

    def draw_regression(self, ax, title, series, panel_label=''):
        x_rel, divider = get_dist_x_div(series)

        reg_bf = calc_regression_with_ci(x_rel[:divider], series[:divider])
        reg_af = calc_regression_with_ci(x_rel[divider:], series[divider:])

        bf = reg_bf["pred_summary"]
        af = reg_af["pred_summary"]

        ax.scatter(x_rel, series, color='darkgray', alpha=0.7, s=10, marker='x')

        ax.plot(x_rel[:divider], bf["mean"], linewidth=1.5, label='Before ChatGPT')
        ax.plot(x_rel[divider:], af["mean"], linewidth=1.5, label='After ChatGPT')

        ax.fill_between(x_rel[:divider], bf["mean_ci_lower"], bf["mean_ci_upper"], alpha=0.15)
        ax.fill_between(x_rel[divider:], af["mean_ci_lower"], af["mean_ci_upper"], alpha=0.15)

        ax.axvline(x=0, color='#CC3333', linestyle='--', linewidth=1.2, zorder=5)

        # Chow test
        st_0 = st.Stats(np.arange(-52, 52), series, 2, 0.95)
        F_stat, p_value = st_0.chow_test()
        p_txt = '$p < 0.001$' if p_value < 0.001 else f'$p = {p_value:.3f}$'

        # 제목 — 폰트 크기 통일
        # ax.set_title(f'Changes in {title} (topic)', fontsize=font_setting['title'], pad=22)
        ax.text(0.5, 1.08, f'Changes in {title} (topic)',
            transform=ax.transAxes,
            fontsize=font_setting['title'], ha='center', va='bottom')

        # p-value — 제목 아래 별도 텍스트 (유의 여부에 따라 색상 구분)
        p_color = '#CC3333' if p_value < 0.05 else 'gray'
        ax.text(0.5, 1.02, p_txt,
                ha='center', fontsize=font_setting['p-value'], color=p_color,
                transform=ax.transAxes)
                    
        # 패널 레이블
        if panel_label:
            ax.text(-0.08, 1.08, panel_label,
                    transform=ax.transAxes,
                    fontsize=font_setting['panel'], fontweight='bold',
                    va='bottom', ha='left')

        # X축 레이블
        # ax.set_xlabel('Week relative to ChatGPT release', fontsize=9)

        # 축 폰트
        ax.tick_params(axis='both', labelsize=font_setting['tick'])

        # spine 정리
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        # 그리드
        ax.yaxis.grid(True, linestyle=':', linewidth=0.5, color='gray', alpha=0.5, zorder=0)
        ax.set_axisbelow(True)

        # 범례 (첫 번째 regression 패널에만 표시하고 싶으면 조건 추가)
        ax.legend(fontsize=font_setting['legend'], frameon=False)

        
    def draw_topic_stack(self, ax, title, proportion, order_list, c, alpha=0.9, panel_label = ''):
        
        x = sorted(list(proportion['rel_week'].unique()))
        bottom = np.zeros(len(x))
        
        for idx, topic in enumerate(order_list):
            t_p = proportion[proportion['Topic'] == topic].copy()

            count_full = np.zeros(len(x))
            for i, rw in enumerate(t_p['rel_week']):
                if rw in x:
                    rw_idx = x.index(rw)
                    count_full[rw_idx] = t_p.loc[t_p['rel_week'] == rw, 'proportion'].values[0]
            ax.bar(
                x,
                count_full,
                bottom=bottom,
                label=topic,
                color=c[idx],
                width=1.0,
                align='center',
                alpha=alpha,
                linewidth=0,         
            )
            
            bottom += count_full

        # draw chatgpt line
        self.draw_chatgpt_line(ax)
        
        
        # set panel label
        self.set_panel_label(ax, panel_label)
        
        # set title
        self.set_title(ax, title)

        # set tick size
        self.set_tick_size(ax)
        
        # set_spine_visible 
        self.set_spine_visible(ax, False)

        # set_grid_visible
        self.set_grid_visible(ax, True)

        # Y축 범위
        ax.set_ylim(0, bottom.max() * 1.05)

    
    def draw_chatgpt_line(self, ax, linestype = '--', linewidth = 1.2, zorder=5):
        ax.axvline(x=0, color='tab:red', linestyle=linestype, linewidth=linewidth, zorder = zorder)
    
    def set_ylim_range(self, ax, x, y, gap = 0.001, bin = 0.025):
        y_min = min(y)
        y_max = max(y)

        bot = np.floor((y_min - gap) * 100) / 100
        top = np.ceil((y_max + gap) * 100) / 100

        bot = max(0, bot)
        top = min(1, top)

        ax.set_ylim(bot-gap, top+gap)

        bot_tick = np.floor(bot * 10) / 10
        top_tick = np.ceil(top * 10) / 10
        bin = ((top_tick-bot_tick)/4*100)/100
        ax.set_yticks(np.arange(bot_tick, top_tick+0.000000001, bin))

    
    def set_panel_label(self, ax, panel_label):
        ax.text(-0.08, 1.08, panel_label,
                transform=ax.transAxes,
                fontsize=font_setting['panel'], fontweight='bold',
                va='bottom', ha='left')
    
    def set_title(self, ax, title):
        ax.text(0.5, 1.08, f'{title}',
            transform=ax.transAxes,
            fontsize=font_setting['title'], ha='center', va='bottom')
        
    def set_tick_size(self, ax):
        ax.tick_params(axis='both', labelsize=font_setting['tick'])

    def set_spine_visible(self, ax, is_visible=True):
        ax.spines['top'].set_visible(is_visible)
        ax.spines['right'].set_visible(is_visible)

    
    def set_grid_visible(self, ax, is_visible=True):
        ax.yaxis.grid(is_visible, linestyle=':', linewidth=0.5, color='gray', alpha=0.5, zorder=0)
        ax.set_axisbelow(is_visible)

    def set_legend(self, ax, is_visible=True):
        if is_visible:
            ax.legend(fontsize=font_setting['legend'], frameon=False)

    def draw_tag_bar(self, ax, title, x, y, c, alpha=0.9, panel_label = '', set_ylim = True):
        
        # draw bar plot
        ax.bar(x, y, width=1.0, align='center', alpha=alpha, linewidth=0, color = c)
        
        # draw chatgpt line
        self.draw_chatgpt_line(ax)
        
        # set ylim
        if set_ylim : 
            self.set_ylim_range(ax, x, y)
        
        # set panel label
        self.set_panel_label(ax, panel_label)
        
        # set title
        self.set_title(ax, title)

        # set tick size
        self.set_tick_size(ax)
        
        # set_spine_visible 
        self.set_spine_visible(ax, False)

        # set_grid_visible
        self.set_grid_visible(ax, True)
        

    def draw_statter_plot(self, ax, x, y, alpha = 0.7, s = 10, marker='x'):
        ax.scatter(x, y, color='darkgray', alpha=alpha, s=s, marker=marker)
        

    def draw_regression_line(self, ax, x, y, apply_chowtest=True):
        # divider = np.where(np.array(x) == 0)[0][0]
        x_arr = np.array(x)
        if 0 in x_arr:
            divider = np.where(x_arr == 0)[0][0]
        else:
            divider = np.argmin(np.abs(x_arr))
        
        reg_bf = calc_regression_with_ci(x[:divider], y[:divider])
        reg_af = calc_regression_with_ci(x[divider:], y[divider:])
        
        bf = reg_bf["pred_summary"]
        af = reg_af["pred_summary"]

        ax.plot(x[:divider], bf["mean"], linewidth=2, label='before ChatGPT')
        ax.plot(x[divider:], af["mean"], linewidth=2, label='after ChatGPT')

        ax.fill_between(x[:divider], bf["mean_ci_lower"], bf["mean_ci_upper"], alpha=0.1)
        ax.fill_between(x[divider:], af["mean_ci_lower"], af["mean_ci_upper"], alpha=0.1)


        if apply_chowtest:
            # Chow test
            st_0 = st.Stats(x, y, 2, 0.95, divider)
            F_stat, p_value = st_0.chow_test()
            ax.plot(x, st_0.y_predict, linestyle="--", color="black", linewidth=1.5, label='Overall fit')

            p_txt = '$p < 0.001$' if p_value < 0.001 else f'$p = {p_value:.3f}$'            
            p_color = '#CC3333' if p_value < 0.05 else 'gray'
            ax.text(0.5, 1.02, p_txt,
                    ha='center', fontsize=font_setting['p-value'], color=p_color,
                    transform=ax.transAxes)
            
        
        self.set_legend(ax)
        
  
    def draw_regression_with_chow(self, ax, title, x, y, c, alpha=0.9, panel_label = '', set_ylim = True):
        self.draw_statter_plot(ax, x, y)

        self.draw_regression_line(ax, x, y)
    
        # draw chatgpt line
        self.draw_chatgpt_line(ax)
        
        # set ylim
        if set_ylim:
            self.set_ylim_range(ax, x, y)
        
        # set panel label
        self.set_panel_label(ax, panel_label)
        
        # set title
        self.set_title(ax, title)

        # set tick size
        self.set_tick_size(ax)
        
        # set_spine_visible 
        self.set_spine_visible(ax, False)

        # set_grid_visible
        self.set_grid_visible(ax, True)

    def draw_topic_regression(self, ax, title, x, y, c, alpha=0.9, panel_label = ''):
        self.draw_statter_plot(ax, x, y)

        self.draw_regression_line(ax, x, y)
    
        # draw chatgpt line
        self.draw_chatgpt_line(ax)
        
        # set ylim
        self.set_ylim_range(ax, x, y)
        
        # set panel label
        self.set_panel_label(ax, panel_label)
        
        # set title
        self.set_title(ax, title)

        # set tick size
        self.set_tick_size(ax)
        
        # set_spine_visible 
        self.set_spine_visible(ax, False)

        # set_grid_visible
        self.set_grid_visible(ax, True)
    

if __name__ == "__main__":
    from lib.utils.data_loader import DataLoader
    from lib.utils.statistics import *
    from lib.utils.datetime_handler import *
    from lib.utils.utils import *
    dir_root_bert = "../result/bert_based/run_id_0/data"
    dir_root_lda = "../result/lda/run_id_1/data"
    def get_top_and_bottom_topics(data_dir):
        monthly_count = get_monthly_topics_counts(data_dir, list(range(0, 50)))
        before_gpt_count = {topic: sum(monthly_count[topic][:12]) for topic in monthly_count}
        sorted_topics = [k for k, v in sorted(before_gpt_count.items(),
                                              key=lambda item: item[1],
                                              reverse=True)]
        return sorted_topics[:10], sorted_topics[-10:]

    def get_topic_distribution_in_date_range(date_range, data_dir, topics):
        file_list = get_related_files(date_range)
        list_ = []
        for i in file_list:
            file_path = f"{data_dir}/{i}.json"
            json_list = DataLoader.load_json(file_path)
            list_ += json_list
        list_ = get_sublist_of_desired_date_range(list_, date_range)
        if "bert" in data_dir:
            to_return = get_topics_counts_bert(list_, topics)
        else:
            to_return = get_topics_counts_lda(list_, topics)
        to_return = get_fractional_values_dict(to_return)
        return to_return

    def collect_topic_distribution(window, data_dir, topics):
        """

        Args:
            window: window size, which is a positive int

        Returns:
            a dict, where keys are datetime str and values are distributions
        """
        date_str_list = get_datetime_strings_before_and_after_gpt(window)
        to_return = []
        for i in range(len(date_str_list)-1):
            date_range = (date_str_list[i], date_str_list[i+1])
            topic_distribution = get_topic_distribution_in_date_range(
                date_range, data_dir, list(range(0, 50)))
            to_append = {topic: topic_distribution[topic] for topic in topics}
            to_return.append(to_append)
        return to_return
        
        
    plot_gen = PlotGen()
    bert_top_10, bert_bottom_10 = get_top_and_bottom_topics(dir_root_bert)
    lda_top_10, lda_bottom_10 = get_top_and_bottom_topics(dir_root_lda)
    bert_top_10_res = collect_topic_distribution(7, dir_root_bert, bert_top_10)
    bert_top_10_res = list(map(lambda x: sum(x.values()), bert_top_10_res))
    bert_bot_10_res = collect_topic_distribution(7, dir_root_bert,
                                                 bert_bottom_10)
    bert_bot_10_res = list(map(lambda x: sum(x.values()), bert_bot_10_res))
    lda_top_10_res = collect_topic_distribution(7, dir_root_lda, lda_top_10)
    lda_top_10_res = list(map(lambda x: sum(x.values()), lda_top_10_res))
    lda_bot_10_res = collect_topic_distribution(7, dir_root_lda,
                                                lda_bottom_10)
    lda_bot_10_res = list(map(lambda x: sum(x.values()), lda_bot_10_res))
    x = list(range(104))
    plot_gen.draw_scatter_plot(x, bert_top_10_res, title="bert_top_10")
    plot_gen.draw_scatter_plot(x, lda_top_10_res, title="lda_top_10")
    plot_gen.draw_scatter_plot(x, bert_bot_10_res, title="bert_bot_10")
    plot_gen.draw_scatter_plot(x, lda_bot_10_res, title="lda_bot_10")
