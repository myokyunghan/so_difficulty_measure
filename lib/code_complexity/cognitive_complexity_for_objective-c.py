"""
Objective-C Cognitive Complexity Calculator
============================================
Based on: G. Ann Campbell. 2018. "Cognitive Complexity: An Overview and
Evaluation." In TechDebt '18, ICSE, Gothenburg, Sweden.
https://doi.org/10.1145/3194164.3194186

AST structure is very similar to C/C++, with additions for
@try/@catch/@finally and ObjC method definitions.

Dependencies:
  pip install tree-sitter
  git clone https://github.com/amaanq/tree-sitter-objc.git
  cd tree-sitter-objc && pip install .
"""
import os
from tree_sitter import Language, Parser

def create_parser():
    """tree-sitter-language-pack 우선, 개별 패키지 fallback"""
    # 1. tree-sitter-language-pack
    try:
        from tree_sitter_language_pack import get_parser
        return get_parser("objc")
    except Exception:
        pass
    # 2. 개별 패키지
    try:
        import tree_sitter_objc as _mod
        return Parser(Language(_mod.language()))
    except ImportError:
        raise ImportError(
            "Install one of:\n"
            "  pip install tree-sitter-language-pack\n"
            "  pip install tree-sitter-objc")


class CognitiveComplexityCalculator:

    def __init__(self, source_code: str):
        self.source_code = source_code
        self.parser = create_parser()
        self.tree = self.parser.parse(bytes(source_code, "utf-8"))
        self.results = []
        self.details = []

    def _text(self, node):
        if node is None: return ""
        return self.source_code[node.start_byte:node.end_byte]

    def _line(self, node):
        return node.start_point[0] + 1

    def _add_detail(self, node, kind, structural, nesting):
        line = self._line(node)
        total = structural + nesting
        if nesting > 0:
            self.details.append(f"  Line {line:>4}: +{total} ({kind}: +{structural} structural, +{nesting} nesting)")
        else:
            self.details.append(f"  Line {line:>4}: +{total} ({kind})")

    def _add_detail_raw(self, desc, inc):
        self.details.append(f"          +{inc} ({desc})")

    def calculate(self):
        self.results = []
        self._walk_top_level(self.tree.root_node)
        return self.results

    def _walk_top_level(self, node):
        for child in node.children:
            if child.type == 'function_definition':
                self._process_c_function(child)
            elif child.type == 'class_implementation':
                for ch in child.children:
                    if ch.type == 'implementation_definition':
                        for item in ch.children:
                            if item.type == 'method_definition':
                                self._process_objc_method(item)

    def _process_c_function(self, func_node):
        declarator = func_node.child_by_field_name("declarator")
        name = "<anonymous>"
        if declarator:
            inner = declarator.child_by_field_name("declarator")
            if inner: name = self._text(inner)
            else:
                for ch in declarator.children:
                    if ch.type == 'identifier':
                        name = self._text(ch); break
        self.details = []
        body = func_node.child_by_field_name("body")
        c = 0
        if body: c = self._visit_children(body, 0)
        self.results.append({"function": name, "complexity": c,
            "start_line": func_node.start_point[0]+1, "end_line": func_node.end_point[0]+1,
            "details": list(self.details)})

    def _process_objc_method(self, method_node):
        # Extract name: first identifier child (method name)
        name = "<anonymous>"
        for ch in method_node.children:
            if ch.type == 'identifier':
                name = self._text(ch); break
        self.details = []
        # Body: last compound_statement
        body = None
        for ch in method_node.children:
            if ch.type == 'compound_statement':
                body = ch
        c = 0
        if body: c = self._visit_children(body, 0)
        self.results.append({"function": name, "complexity": c,
            "start_line": method_node.start_point[0]+1, "end_line": method_node.end_point[0]+1,
            "details": list(self.details)})

    def _visit_children(self, node, nesting):
        total = 0
        for child in node.children:
            total += self._visit(child, nesting)
        return total

    def _visit(self, node, nesting):
        t = node.type

        if t == "if_statement":
            return self._handle_if_chain(node, nesting, is_first=True)

        if t == "switch_statement":
            inc = 1 + nesting
            self._add_detail(node, "switch", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            if body:
                for child in body.children:
                    if child.type == "case_statement":
                        c += self._visit_case_body(child, nesting + 1)
                    else:
                        c += self._visit(child, nesting + 1)
            return c

        if t in ("for_statement", "for_in_statement"):
            inc = 1 + nesting
            self._add_detail(node, "for", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            if body: c += self._visit_children(body, nesting + 1)
            return c

        if t == "while_statement":
            inc = 1 + nesting
            self._add_detail(node, "while", 1, nesting)
            c = inc
            cond = node.child_by_field_name("condition")
            if cond: c += self._visit(cond, nesting)
            body = node.child_by_field_name("body")
            if body: c += self._visit_children(body, nesting + 1)
            return c

        if t == "do_statement":
            inc = 1 + nesting
            self._add_detail(node, "do-while", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            if body: c += self._visit_children(body, nesting + 1)
            return c

        if t == "try_statement":
            return self._visit_children(node, nesting)

        if t == "catch_clause":
            inc = 1 + nesting
            self._add_detail(node, "catch", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            else:
                for ch in node.children:
                    if ch.type == 'compound_statement':
                        c += self._visit_children(ch, nesting + 1)
                        break
            return c

        if t == "finally_clause":
            for ch in node.children:
                if ch.type == 'compound_statement':
                    return self._visit_children(ch, nesting)
            return 0

        if t == "conditional_expression":
            inc = 1 + nesting
            self._add_detail(node, "ternary", 1, nesting)
            c = inc
            cond = node.child_by_field_name("condition")
            if cond: c += self._visit(cond, nesting)
            cons = node.child_by_field_name("consequence")
            if cons: c += self._visit(cons, nesting + 1)
            alt = node.child_by_field_name("alternative")
            if alt: c += self._visit(alt, nesting + 1)
            return c

        if t == "goto_statement":
            self._add_detail(node, "goto", 1, 0)
            return 1

        if t == "labeled_statement":
            c = 0
            for child in node.children:
                if child.type not in ("statement_identifier", ":"):
                    c += self._visit(child, nesting)
            return c

        if t == "binary_expression":
            return self._handle_binary(node, nesting)

        if t in ("parenthesized_expression", "condition_clause"):
            return self._visit_children(node, nesting)

        if t == "block_expression":  # ObjC block ^{ ... }
            c = 0
            body = node.child_by_field_name("body")
            if body: c += self._visit_children(body, nesting + 1)
            else: c += self._visit_children(node, nesting + 1)
            return c

        return self._visit_children(node, nesting)

    def _visit_case_body(self, case_node, nesting):
        c = 0; skip = True
        for child in case_node.children:
            if child.type == ":": skip = False; continue
            if skip: continue
            c += self._visit(child, nesting)
        return c

    def _handle_if_chain(self, if_node, nesting, is_first=True):
        c = 0
        if is_first:
            c += 1 + nesting; self._add_detail(if_node, "if", 1, nesting)
        else:
            c += 1; self._add_detail(if_node, "else if", 1, 0)

        cond = if_node.child_by_field_name("condition")
        if cond: c += self._visit(cond, nesting)
        consequence = if_node.child_by_field_name("consequence")
        if consequence:
            if consequence.type == "compound_statement": c += self._visit_children(consequence, nesting + 1)
            else: c += self._visit(consequence, nesting + 1)

        alt = if_node.child_by_field_name("alternative")
        if alt:
            if alt.type == "else_clause":
                for child in alt.children:
                    if child.type == "if_statement":
                        c += self._handle_if_chain(child, nesting, is_first=False)
                    elif child.type == "compound_statement":
                        c += 1; self._add_detail(alt, "else", 1, 0)
                        c += self._visit_children(child, nesting + 1)
            elif alt.type == "if_statement":
                c += self._handle_if_chain(alt, nesting, is_first=False)
            elif alt.type == "compound_statement":
                c += 1; self._add_detail(alt, "else", 1, 0)
                c += self._visit_children(alt, nesting + 1)
        return c

    def _handle_binary(self, node, nesting):
        ops = []; self._collect_logical_ops(node, ops)
        if not ops: return self._visit_children(node, nesting)
        c = 0; prev = None
        for op in ops:
            if prev is None or op != prev:
                c += 1
                self._add_detail_raw(f"logical sequence '{op}'" if prev is None else f"logical change to '{op}'", 1)
                prev = op
        return c

    def _collect_logical_ops(self, node, ops):
        if node.type != "binary_expression": return
        op_node = node.child_by_field_name("operator")
        if op_node is None: return
        op_text = self._text(op_node)
        if op_text not in ("&&", "||"): return
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if left and left.type == "binary_expression":
            lop = left.child_by_field_name("operator")
            if lop and self._text(lop) in ("&&", "||"): self._collect_logical_ops(left, ops)
        ops.append(op_text)
        if right and right.type == "binary_expression":
            rop = right.child_by_field_name("operator")
            if rop and self._text(rop) in ("&&", "||"): self._collect_logical_ops(right, ops)


def calculate_file(filepath):
    with open(filepath, "r", encoding="utf-8") as f: source = f.read()
    return CognitiveComplexityCalculator(source).calculate()

def calculate_source(source_code):
    return CognitiveComplexityCalculator(source_code).calculate()

def calculate_directory(dirpath):
    results = []
    for root, dirs, files in os.walk(dirpath):
        for fname in sorted(files):
            if fname.endswith((".m", ".mm")):
                fpath = os.path.join(root, fname)
                try:
                    r = calculate_file(fpath)
                    for x in r: x["file"] = fpath
                    results.extend(r)
                except Exception as e: print(f"Error {fpath}: {e}")
    return results

def print_results(results, verbose=True):
    total = 0
    for r in results:
        total += r["complexity"]
        print(f"\n{'='*60}")
        if r.get("file"): print(f"File: {r['file']}")
        print(f"Function: {r['function']} (lines {r['start_line']}-{r['end_line']})")
        print(f"Cognitive Complexity: {r['complexity']}")
        if verbose and r["details"]:
            for d in r["details"]: print(d)
    print(f"\n{'='*60}")
    print(f"Total: {total}, Functions: {len(results)}")
    if results: print(f"Average: {total/len(results):.1f}")