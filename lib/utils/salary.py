from utils.file_io import load_json, save_json
from math import log
import itertools


class SalaryRaise:
    def __init__(self):
        self.data_dir_root = "./result"
        self.salary_info = load_json(
            f"{self.data_dir_root}/tag/salary.json"
        )
        self.tag_info = load_json(
            f"{self.data_dir_root}/tag/tag_info.json"
        )
        self.plot_generator = PlotGen()
        self.years = [2019, 2020, 2021, 2022, 2023, 2024]
        self.remove_tags_not_in_db()

    def __call__(self):
        self.collect_plots()

    def remove_tags_not_in_db(self):
        """

        Returns:
            None
        """
        to_pop = []
        for tag in self.salary_info:
            if tag not in self.tag_info:
                to_pop.append(tag)
        for tag in to_pop:
            self.salary_info.pop(tag)

    def get_tag_list_by_year(self, year):
        """

        Args:
            year: an int

        Returns:
            a list of str
        """
        to_return = [tag for tag in self.salary_info if str(year) in
                     self.salary_info[tag]]
        return to_return

    def collect_plots(self):
        for year in self.years:
            self.draw_one_year_plot(year)
        for i in range(len(self.years)-1):
            years_pair = [self.years[i], self.years[i+1]]
            self.draw_rate_of_change_plot(*years_pair)
        for i in range(len(self.years)-2):
            years_triplet = [self.years[i], self.years[i+1], self.years[i+2]]
            self.draw_rate_of_change_diff_plot(*years_triplet)

    def draw_one_year_plot(self, year):
        """
        Draws log(post cnt) x Avg. salary scatter plot.

        Args:
            year: an int

        Returns:
            None
        """
        tag_list = self.get_tag_list_by_year(year)
        x, y = [], []
        for tag_str in tag_list:
            tags = tag_str.split("/")
            x_value = sum([int(self.tag_info[tag]["db_count_before_gpt"])
                           for tag in tags])
            y_value = int(self.salary_info[tag_str][str(year)])
            x.append(log(x_value))
            y.append(y_value)
        self.plot_generator.draw_scatter_plot_and_save(x=x, y=y,
                                              title=f"salary_{year}",
                                              x_label="log(post count)")

    def get_rate_of_change(self, tag_str, year_before, year_after):
        """

        Args:
            tag_str: a key of self.salary_info
            year_before: an int
            year_after: an int

        Returns:
            a float
        """
        y_before = int(self.salary_info[tag_str][str(year_before)])
        y_after = int(self.salary_info[tag_str][str(year_after)])
        to_return = (y_after - y_before) / y_before
        return to_return

    def draw_rate_of_change_plot(self, year_before, year_after):
        """
        Draws log(post cnt) x salary raise scatter plot.

        Args:
            year_before: an int
            year_after: an int

        Returns:
            None
        """
        tags_before = self.get_tag_list_by_year(year_before)
        tags_after = self.get_tag_list_by_year(year_after)
        tag_list = set(tags_before) & set(tags_after)
        x, y = [], []
        for tag_str in tag_list:
            tags = tag_str.split("/")
            x_value = sum([int(self.tag_info[tag]["db_count_before_gpt"])
                           for tag in tags])
            y_value = self.get_rate_of_change(tag_str, year_before, year_after)
            x.append(log(x_value))
            y.append(y_value)
        self.plot_generator.draw_scatter_plot_and_save(
            x=x, y=y, title=f"salary_raise_{year_before}_{year_after}",
            x_label="log(post count)"
        )

    def draw_rate_of_change_diff_plot(self, year_1, year_2, year_3):
        tags_1 = self.get_tag_list_by_year(year_1)
        tags_2 = self.get_tag_list_by_year(year_2)
        tags_3 = self.get_tag_list_by_year(year_3)
        tag_list = set(tags_1) & set(tags_2) & set(tags_3)
        x, y = [], []
        print("tag_list : ", tag_list)
        print("tag_list_len : ", len(tag_list))
        for tag_str in tag_list:
            tags = tag_str.split("/")
            print('tags : ', tags)
            x_value = sum([int(self.tag_info[tag]["db_count_before_gpt"])
                           for tag in tags])
            print("x_value : ", x_value)
            y_before = self.get_rate_of_change(tag_str, year_1, year_2)
            y_after = self.get_rate_of_change(tag_str, year_2, year_3)
            y_value = y_after - y_before
            x.append(log(x_value))
            y.append(y_value)
        self.plot_generator.draw_scatter_plot_and_save(
            x=x, y=y, title=f"salary_raise_diff_{year_1}_{year_2}_{year_3}",
            x_label="log(post count)"
        )


if __name__ == "__main__":
    sal_raise = SalaryRaise()
    sal_raise()
