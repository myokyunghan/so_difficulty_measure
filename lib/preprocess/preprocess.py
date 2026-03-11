import re


class HTMLParser:
    def __init__(self):
        self.html_entities = {
            "&nbsp": "",
            "&amp": "&",
            "&quot": '"',
            "&lt": "<",
            "&gt": ">",
        }
        self.tag_pattern = '<.*?>'

    def remove_tags(self, post_str):
        """

        Args:
            post_str: a str

        Returns:
            a str with all tags removed
        """
        to_return = re.sub(self.tag_pattern, '', post_str)
        return to_return

    def replace_entities(self, post_str):
        """

        Args:
            post_str: a str

        Returns:
            a str with all listed entities replaced
        """
        to_return = post_str
        for key, val in self.html_entities.items():
            to_return = to_return.replace(key, val)
        return to_return

    def get_html_cleaned_str(self, post_str):
        """

        Args:
            post_str: a str

        Returns:
            a str
        """
        to_return = self.remove_tags(post_str)
        to_return = self.replace_entities(to_return)
        return to_return
class CodeSectionParser:
    def __init__(self):
        self.code_tag_start = "<code>"
        self.code_tag_end = "</code>"
        self.pre_tag_start = "<pre>"
        self.pre_tag_end = "</pre>"
        self.code_section_start = "<pre><code>"
        self.code_section_end = "</code></pre>"
                                                  
        self.code_section_list = ["<pre><code>", '<pre class="lang-none prettyprint-override"><code>', '<pre class="lang-py prettyprint-override"><code>']
        self.code_section_start_pattern = r"<pre\s.*?><code>"

        # self.html_entities = {
        #     "&nbsp": "",
        #     "&amp": "&",
        #     "&quot;": '"',
        #     "&lt": "<",
        #     "&gt": ">",
        # }

    def __call__(self, post_str):
        """
        Args:
            post_str: a str

        Returns:
            a dict that contains the parsed info
        """
        to_return = {}
        code_section_dict_list = self.collect_code_sections(post_str=post_str)
        to_return["code_sections"] = code_section_dict_list
        return to_return

    def collect_code_sections(self, post_str):
        """
        Args:
            post_str: a str

        Returns:
            a list of dict
        """
        if any(css in post_str for css in self.code_section_list):
            to_return = self.get_spans_of_code_sections(post_str=post_str)
        else:
            to_return = []
        return to_return

    def get_spans_of_code_sections(self, post_str):
        """
        Args:
            post_str: a str

        Returns:
            a list of dict where each dict has the format of
            {
                "off_beg": an int,
                "off_end": an int,
                "span_str": a str
            }
        """
        start_offsets = {m.start(): css for css in self.code_section_list for m in re.finditer(css, post_str)}
        start_offsets = dict(sorted(start_offsets.items()))

        end_offsets = [
            m.start() for m in re.finditer(self.code_section_end, post_str)
        ]
        if len(start_offsets) != len(end_offsets):
            return []
        to_return = []
        for idx, offset_begin in enumerate(start_offsets):
            offset_begin += len(start_offsets[offset_begin])
            offset_end = end_offsets[idx]
            span_ = post_str[offset_begin:offset_end]
            to_return.append({
                "off_beg": offset_begin,
                "off_end": offset_end,
                "span_str": span_
            })
        return to_return
    

    def chg_tag(self, code, lang="python"):
        """
        Args:
            post_str: a str

        Returns:
            a list of dict where each dict has the format of
            {
                "off_beg": an int,
                "off_end": an int,
                "span_str": a str
            }
        """
        st_pattern = r'<pre(?: class="[^"]*")?><code>'
        st_dst = f"```{lang}\n"
        code = re.sub(st_pattern, st_dst, code, count=0, flags=0)
        
        end_dst = "```"
        end_pattern =r'</code></pre>'
        code = re.sub(end_pattern, end_dst, code, count=0, flags=0)
        return code
    
    def clean_q_str_for_annotation(self, post_str):
        """
        Args:
            post_str: a str

        Returns:
            a str for human annotation
        """
        htmlp = HTMLParser()
        t_body_str = self.chg_tag(post_str)
        clean_str = htmlp.get_html_cleaned_str(t_body_str)
        clean_str = re.sub(r";(?=\S)", "", clean_str)
        
        return clean_str

if __name__ == "__main__":
    from data_loader import DataLoader
    parser_, data_loader = CodeSectionParser(), DataLoader()
    dict_list = data_loader.load_json('./data/questions/0.json')
    to_save = []
    for dict_ in dict_list:
        body_ = dict_["body"]
        parsed_ = parser_(post_str=body_)
        parsed_["original_dict"] = dict_
        to_save.append(parsed_)
    data_loader.save_json(path="./data/bertopic_test.json", data_=to_save)
