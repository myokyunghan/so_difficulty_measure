class SectionExtractor:
    def __init__(self):
        self.text_section_joiner = "\n\n\n"
        self.code_section_joiner = "\n\n\n"

    def get_text_section(self, dict_):
        """

        Args:
            dict_: a dict

        Returns:
            a str
        """
        body = dict_["body"]
        start = 0
        text_sections = []
        for code_ in dict_["code_sections"]:
            text_sections.append(body[start:code_["off_beg"]])
            start = code_["off_end"]
        text_sections.append(body[start:])
        to_return = self.text_section_joiner.join(text_sections)
        return to_return

    def get_code_section(self, dict_):
        """

        Args:
            dict_: a dict

        Returns:
            a str
        """
        code_sections = dict_["code_sections"]
        code_sections = [code_["span_str"] for code_ in code_sections]
        to_return = self.code_section_joiner.join(code_sections)
        return to_return

