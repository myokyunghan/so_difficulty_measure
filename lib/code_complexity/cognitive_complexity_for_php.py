"""
PHP Cognitive Complexity Calculator
======================================
Based on:
  - G. Ann Campbell. 2018. "Cognitive Complexity: An Overview and Evaluation."
    TechDebt '18, ICSE, Gothenburg, Sweden.
    https://doi.org/10.1145/3194164.3194186
  - SonarSource. "Cognitive Complexity - a new way of measuring understandability."
    Version 1.7, 29 August 2023.
    https://www.sonarsource.com/docs/CognitiveComplexity.pdf

═══════════════════════════════════════════════════════════════════
Specification (Appendix B, adapted for PHP)
═══════════════════════════════════════════════════════════════════

B1. Increments (+1 each)
────────────────────────
  Structural (B):  +1, receives nesting penalty, increases nesting level
    - if                                  → PHP: if_statement
    - switch                              → PHP: switch_statement (single +1, p.7)
    - for, foreach                        → PHP: for_statement, foreach_statement
    - while, do while                     → PHP: while_statement, do_statement
    - catch                               → PHP: catch_clause (single +1, p.7)
    - ternary operator                    → PHP: conditional_expression ($a ? $b : $c)

  Hybrid (D):  +1, NO nesting penalty, but increases nesting level
    - elseif                              → PHP: else_if_clause
    - else                                → PHP: else_clause

  Fundamental (C):  +1, NO nesting penalty, does NOT increase nesting level
    - goto                                → PHP: goto_statement
    - sequences of binary logical ops     → PHP: binary_expression with && / || / and / or
    - each method in a recursion cycle    → Not implemented

  Ignored (p.6 "Ignore shorthand"):
    - null-coalescing (??, ?->)           → No increment

B2. Nesting level
────────────────────────────────────────────────────────────────────────
    - if, elseif, else, ternary
    - switch, for, foreach, while, do while
    - catch
    - nested functions: anonymous_function, arrow_function

B3. Nesting increments (receive +nesting_level penalty)
────────────────────────────────────────────────────────────────────────
    - if, ternary       (NOT elseif, NOT else)
    - switch, for, foreach, while, do while
    - catch

═══════════════════════════════════════════════════════════════════
Additional rules
═══════════════════════════════════════════════════════════════════

  - try / finally: no increment, no nesting change (p.7)
  - switch: entire switch + all cases = single structural increment (p.7)
  - goto: +1 fundamental (p.8)
  - PHP logical keywords (and, or): treated same as &&, || for sequences
  - anonymous_function (Closure): no structural increment, increases nesting (p.9)
  - arrow_function (fn() =>): no structural increment, increases nesting (p.9)

Dependencies: pip install tree-sitter tree-sitter-php
"""
import os
import re
import sys
import json
from tree_sitter import Language, Parser


def create_parser():
    try:
        from tree_sitter_language_pack import get_parser
        return get_parser("php")
    except Exception:
        pass
    try:
        import tree_sitter_php as _mod
        return Parser(Language(_mod.language_php()))
    except ImportError:
        raise ImportError(
            "Install: pip install tree-sitter-php")


class CognitiveComplexityCalculator:

    def __init__(self, source_code: str):
        self.source_code = source_code
        self.parser = create_parser()
        # Ensure <?php tag for proper parsing
        if not source_code.strip().startswith("<?"):
            source_code = "<?php\n" + source_code + "\n?>"
            self._offset = 1  # line offset for bare code
        else:
            self._offset = 0
        self._parse_source = source_code
        self.tree = self.parser.parse(bytes(source_code, "utf-8"))
        self.results = []
        self.details = []

    def _text(self, node):
        if node is None:
            return ""
        return self._parse_source[node.start_byte:node.end_byte]

    def _line(self, node):
        return node.start_point[0] + 1 - self._offset

    def _add_detail(self, node, kind, structural, nesting):
        line = self._line(node)
        total = structural + nesting
        if nesting > 0:
            self.details.append(
                f"  Line {line:>4}: +{total} ({kind}: "
                f"+{structural} structural, +{nesting} nesting)")
        else:
            self.details.append(f"  Line {line:>4}: +{total} ({kind})")

    def _add_detail_raw(self, description, increment):
        self.details.append(f"          +{increment} ({description})")

    # ── Top-level traversal ──

    def calculate(self):
        self.results = []
        self._walk_top_level(self.tree.root_node)

        # Bare code fallback
        if not self.results:
            wrapped = "<?php\nfunction __top__() {\n" + self.source_code + "\n}\n?>"
            try:
                tree2 = self.parser.parse(bytes(wrapped, "utf-8"))
                if not tree2.root_node.has_error:
                    orig_src = self._parse_source
                    orig_tree = self.tree
                    self._parse_source = wrapped
                    self._offset = 2
                    self.tree = tree2
                    self.results = []
                    self._walk_top_level(tree2.root_node)
                    self._parse_source = orig_src
                    self.tree = orig_tree
                    self._offset = 0
                    for r in self.results:
                        r["function"] = "<top-level>"
            except Exception:
                pass
        return self.results

    def _walk_top_level(self, node):
        for child in node.children:
            if child.type == "function_definition":
                self._process_function(child)
            elif child.type in ("class_declaration", "interface_declaration",
                                "trait_declaration", "enum_declaration"):
                self._walk_class(child)
            elif child.type == "namespace_definition":
                body = child.child_by_field_name("body")
                if body:
                    self._walk_top_level(body)

    def _walk_class(self, class_node):
        body = class_node.child_by_field_name("body")
        if body is None:
            return
        for child in body.children:
            if child.type == "method_declaration":
                self._process_function(child)
            elif child.type in ("class_declaration", "trait_declaration"):
                self._walk_class(child)

    def _process_function(self, func_node):
        name_node = func_node.child_by_field_name("name")
        func_name = self._text(name_node) if name_node else "<anonymous>"
        self.details = []
        body = func_node.child_by_field_name("body")
        complexity = 0
        if body:
            complexity = self._visit_children(body, 0)
        self.results.append({
            "function": func_name,
            "complexity": complexity,
            "start_line": self._line(func_node),
            "end_line": func_node.end_point[0] + 1 - self._offset,
            "details": list(self.details),
        })

    # ── Node visitors ──

    def _visit_children(self, node, nesting):
        total = 0
        for child in node.children:
            total += self._visit(child, nesting)
        return total

    def _visit(self, node, nesting):
        t = node.type

        # ── B1 structural: if ──
        if t == "if_statement":
            return self._handle_if_chain(node, nesting)

        # ── B1 structural: for / foreach ──
        if t in ("for_statement", "foreach_statement"):
            kw = "for" if t == "for_statement" else "foreach"
            inc = 1 + nesting
            self._add_detail(node, kw, 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── B1 structural: while ──
        if t == "while_statement":
            inc = 1 + nesting
            self._add_detail(node, "while", 1, nesting)
            c = inc
            cond = node.child_by_field_name("condition")
            if cond:
                c += self._visit(cond, nesting)
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── B1 structural: do-while ──
        if t == "do_statement":
            inc = 1 + nesting
            self._add_detail(node, "do-while", 1, nesting)
            c = inc
            cond = node.child_by_field_name("condition")
            if cond:
                c += self._visit(cond, nesting)
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── B1 structural: switch (single +1, p.7) ──
        if t == "switch_statement":
            inc = 1 + nesting
            self._add_detail(node, "switch", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            if body:
                for child in body.children:
                    if child.type in ("case_statement", "default_statement"):
                        c += self._visit_children(child, nesting + 1)
            return c

        # ── try: no increment (p.7) ──
        if t == "try_statement":
            c = 0
            for child in node.children:
                c += self._visit(child, nesting)
            return c

        # ── B1 structural: catch (p.7) ──
        if t == "catch_clause":
            inc = 1 + nesting
            self._add_detail(node, "catch", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── finally: no increment (p.7) ──
        if t == "finally_clause":
            body = node.child_by_field_name("body")
            if body:
                return self._visit_children(body, nesting)
            return 0

        # ── B1 structural: ternary (conditional_expression) ──
        if t == "conditional_expression":
            inc = 1 + nesting
            self._add_detail(node, "ternary", 1, nesting)
            c = inc
            cond = node.child_by_field_name("condition")
            if cond:
                c += self._visit(cond, nesting)
            body = node.child_by_field_name("body")
            if body:
                c += self._visit(body, nesting + 1)
            alt = node.child_by_field_name("alternative")
            if alt:
                c += self._visit(alt, nesting + 1)
            return c

        # ── B1 fundamental: logical operators ──
        if t == "binary_expression":
            op = node.child_by_field_name("operator")
            if op and self._text(op) in ("&&", "||", "and", "or"):
                return self._handle_boolean(node, nesting)
            return self._visit_children(node, nesting)

        # ── B1 fundamental: goto (p.8) ──
        if t == "goto_statement":
            self._add_detail(node, "goto", 1, 0)
            return 1

        # ── B2: anonymous_function (Closure) → nesting (p.9) ──
        if t == "anonymous_function":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── B2: arrow_function (fn() =>) → nesting (p.9) ──
        if t == "arrow_function":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                c += self._visit(body, nesting + 1)
            return c

        # ── parenthesized_expression: unwrap ──
        if t == "parenthesized_expression":
            return self._visit_children(node, nesting)

        # ── skip else_if_clause/else_clause here (handled in _handle_if_chain) ──
        if t in ("else_if_clause", "else_clause"):
            return 0

        # ── default: recurse ──
        return self._visit_children(node, nesting)

    # ── if / elseif / else chain ──

    def _handle_if_chain(self, if_node, nesting):
        c = 0
        # if → +1 structural + nesting
        inc = 1 + nesting
        self._add_detail(if_node, "if", 1, nesting)
        c += inc

        cond = if_node.child_by_field_name("condition")
        if cond:
            c += self._visit(cond, nesting)

        body = if_node.child_by_field_name("body")
        if body:
            c += self._visit_children(body, nesting + 1)

        # elseif / else are children with field 'alternative'
        for child in if_node.children:
            if child.type == "else_if_clause":
                c += self._handle_elseif(child, nesting)
            elif child.type == "else_clause":
                c += self._handle_else(child, nesting)
        return c

    def _handle_elseif(self, node, nesting):
        c = 1
        self._add_detail(node, "elseif", 1, 0)
        cond = node.child_by_field_name("condition")
        if cond:
            c += self._visit(cond, nesting)
        body = node.child_by_field_name("body")
        if body:
            c += self._visit_children(body, nesting + 1)
        return c

    def _handle_else(self, node, nesting):
        c = 1
        self._add_detail(node, "else", 1, 0)
        body = node.child_by_field_name("body")
        if body:
            c += self._visit_children(body, nesting + 1)
        return c

    # ── Boolean operator sequences (p.7-8) ──

    def _handle_boolean(self, node, nesting):
        ops = []
        self._collect_boolean_ops(node, ops)
        if not ops:
            return self._visit_children(node, nesting)
        c = 0
        prev = None
        for op in ops:
            norm = "&&" if op in ("&&", "and") else "||"
            if prev is None or norm != prev:
                c += 1
                desc = (f"logical sequence '{op}'" if prev is None
                        else f"logical change to '{op}'")
                self._add_detail_raw(desc, 1)
                prev = norm
        return c

    def _collect_boolean_ops(self, node, ops):
        if node.type != "binary_expression":
            return
        op_node = node.child_by_field_name("operator")
        if op_node is None:
            return
        op_text = self._text(op_node)
        if op_text not in ("&&", "||", "and", "or"):
            return
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if left and left.type == "binary_expression":
            lo = left.child_by_field_name("operator")
            if lo and self._text(lo) in ("&&", "||", "and", "or"):
                self._collect_boolean_ops(left, ops)
        ops.append(op_text)
        if right and right.type == "binary_expression":
            ro = right.child_by_field_name("operator")
            if ro and self._text(ro) in ("&&", "||", "and", "or"):
                self._collect_boolean_ops(right, ops)


# ── Public API ──

def calculate_file(filepath: str):
    with open(filepath, "r", encoding="utf-8") as f:
        return CognitiveComplexityCalculator(f.read()).calculate()

def calculate_source(source_code: str):
    return CognitiveComplexityCalculator(source_code).calculate()

def calculate_directory(dirpath: str):
    all_results = []
    for root, dirs, files in os.walk(dirpath):
        for fname in sorted(files):
            if fname.endswith(".php"):
                fpath = os.path.join(root, fname)
                try:
                    results = calculate_file(fpath)
                    for r in results:
                        r["file"] = fpath
                    all_results.extend(results)
                except Exception as e:
                    print(f"Error processing {fpath}: {e}")
    return all_results

def print_results(results, verbose=True):
    total = 0
    for r in results:
        total += r["complexity"]
        print(f"\n{'='*60}")
        fname = r.get("file", "")
        if fname:
            print(f"File: {fname}")
        print(f"Function: {r['function']} "
              f"(lines {r['start_line']}-{r['end_line']})")
        print(f"Cognitive Complexity: {r['complexity']}")
        if verbose and r["details"]:
            print("Details:")
            for d in r["details"]:
                print(d)
    print(f"\n{'='*60}")
    print(f"Total Cognitive Complexity: {total}")
    print(f"Number of functions: {len(results)}")
    if results:
        print(f"Average per function: {total / len(results):.1f}")

if __name__ == "__main__":
    print("PHP Cognitive Complexity Calculator")
    print("SonarSource Specification v1.7 (29 August 2023)")
    print("=" * 60)
    if len(sys.argv) > 1:
        path = sys.argv[1]
        verbose = "-v" in sys.argv or "--verbose" in sys.argv
        if os.path.isdir(path):
            results = calculate_directory(path)
        elif os.path.isfile(path):
            results = calculate_file(path)
        else:
            print(f"Not found: {path}")
            sys.exit(1)
        if "--json" in sys.argv:
            print(json.dumps([{"file": r.get("file",""), "function": r["function"],
                               "complexity": r["complexity"], "start_line": r["start_line"],
                               "end_line": r["end_line"]} for r in results], indent=2))
        else:
            print_results(results, verbose)
            
# """
# PHP Cognitive Complexity Calculator
# =====================================
# Based on: G. Ann Campbell. 2018. "Cognitive Complexity: An Overview and
# Evaluation." In TechDebt '18, ICSE, Gothenburg, Sweden.
# https://doi.org/10.1145/3194164.3194186

# Rules (Section 2 of the paper):

#   2.1 Ignore readable shorthand structures
#       - No increment for the method/class itself
#       - No increment for null-coalescing operators

#   2.2 Structural increment (+1):
#       - if, else if, else                          (§2.2)
#       - switch                                     (§2.2)
#       - for, foreach, while, do...while            (§2.2)
#       - catch                                      (§2.2)
#       - ternary (? :)                              (§2.2)
#       - break LABEL, continue LABEL                (§2.2, "goto LABEL")
#       - sequences of like binary logical operators (§2.2)
#       - each method in a recursion cycle           (§2.2, not implemented)

#   2.3 Nesting:
#     2.3.1 Increment nesting level:
#       - if, else if, else, switch, ternary         (§2.3.1)
#       - for, foreach, while, do...while            (§2.3.1)
#       - catch                                      (§2.3.1)
#       - nested methods: lambda, anonymous class    (§2.3.1)

#     2.3.2 Receive nesting increment (+nesting_level):
#       - if, switch, ternary                        (§2.3.2, NOT else if/else)
#       - for, foreach, while, do...while            (§2.3.2)
#       - catch                                      (§2.3.2)

# Dependencies: pip install tree-sitter tree-sitter-php
# """
# import os
# import sys
# import json
# from tree_sitter import Language, Parser

# def create_parser():
#     """tree-sitter-language-pack 우선, 개별 패키지 fallback"""
#     # 1. tree-sitter-language-pack
#     try:
#         from tree_sitter_language_pack import get_parser
#         return get_parser("php")
#     except Exception:
#         pass
#     # 2. 개별 패키지
#     try:
#         import tree_sitter_php as _mod
#         return Parser(Language(_mod.language_php()))
#     except ImportError:
#         raise ImportError(
#             "Install one of:\n"
#             "  pip install tree-sitter-language-pack\n"
#             "  pip install tree-sitter-php")


# class CognitiveComplexityCalculator:

#     def __init__(self, source_code: str):
#         self.source_code = source_code
#         self.parser = create_parser()
#         self.tree = self.parser.parse(bytes(source_code, "utf-8"))
#         self.results = []
#         self.details = []

#     def _text(self, node):
#         if node is None:
#             return ""
#         return self.source_code[node.start_byte:node.end_byte]

#     def _line(self, node):
#         return node.start_point[0] + 1

#     def _add_detail(self, node, kind, structural, nesting):
#         line = self._line(node)
#         total = structural + nesting
#         if nesting > 0:
#             self.details.append(
#                 f"  Line {line:>4}: +{total} ({kind}: +{structural} structural, +{nesting} nesting)"
#             )
#         else:
#             self.details.append(f"  Line {line:>4}: +{total} ({kind})")

#     def _add_detail_raw(self, description, increment):
#         self.details.append(f"          +{increment} ({description})")

#     # ── Top-level traversal (recursion-safe) ──

#     def calculate(self):
#         self.results = []
#         self._walk_top_level(self.tree.root_node)
#         return self.results

#     def _walk_top_level(self, node):
#         """최상위에서 함수/클래스를 찾음."""
#         for child in node.children:
#             if child.type == "function_definition":
#                 self._process_method(child)
#             elif child.type in ("class_declaration", "interface_declaration",
#                               "enum_declaration", "record_declaration", "trait_declaration"):
#                 self._walk_class(child)
#             elif child.type == "program":
#                 self._walk_top_level(child)
#             elif child.type == "function_definition":
#                 self._process_method(child)
#             # import, package, comment 등은 무시
#             # ERROR 노드도 무시하여 무한 재귀 방지

#     def _walk_class(self, class_node):
#         body = class_node.child_by_field_name("body")
#         if body is None:
#             return
#         for child in body.children:
#             if child.type in ("method_declaration", "constructor_declaration", "function_definition"):
#                 self._process_method(child)
#             elif child.type in ("class_declaration", "interface_declaration",
#                                 "enum_declaration", "record_declaration"):
#                 self._walk_class(child)

#     def _process_method(self, method_node):
#         """§2.1: 메서드 자체에는 increment 없음"""
#         name_node = method_node.child_by_field_name("name")
#         func_name = self._text(name_node) if name_node else "<anonymous>"

#         self.details = []
#         body = method_node.child_by_field_name("body")
#         complexity = 0
#         if body:
#             complexity = self._visit_children(body, 0)

#         self.results.append({
#             "function": func_name,
#             "complexity": complexity,
#             "start_line": method_node.start_point[0] + 1,
#             "end_line": method_node.end_point[0] + 1,
#             "details": list(self.details),
#         })

#     # ── Node visitors ──

#     def _visit_children(self, node, nesting):
#         total = 0
#         for child in node.children:
#             total += self._visit(child, nesting)
#         return total

#     def _visit(self, node, nesting):
#         t = node.type

#         # §2.2, §2.3.2: if → +1 structural, +nesting penalty
#         if t == "if_statement":
#             return self._handle_if_chain(node, nesting, is_first=True)

#         # §2.2: switch → +1 structural
#         # §2.3.2: switch → receives nesting increment
#         if t in ("switch_expression", "switch_statement"):
#             inc = 1 + nesting
#             self._add_detail(node, "switch", 1, nesting)
#             c = inc
#             body = node.child_by_field_name("body")
#             if body:
#                 # case 자체는 increment 없음, 내부 statements만 처리
#                 for child in body.children:
#                     if child.type == "switch_block_statement_group":
#                         c += self._visit_switch_group(child, nesting + 1)
#                     elif child.type in ("switch_rule",):
#                         c += self._visit_children(child, nesting + 1)
#             return c

#         # §2.2: for → +1 structural
#         # §2.3.2: for → receives nesting increment
#         if t in ("for_statement", "enhanced_for_statement", "foreach_statement"):
#             inc = 1 + nesting
#             self._add_detail(node, "for", 1, nesting)
#             c = inc
#             body = node.child_by_field_name("body")
#             if body:
#                 c += self._visit_children(body, nesting + 1)
#             return c

#         # §2.2: while → +1 structural
#         if t == "while_statement":
#             inc = 1 + nesting
#             self._add_detail(node, "while", 1, nesting)
#             c = inc
#             cond = node.child_by_field_name("condition")
#             if cond:
#                 c += self._visit(cond, nesting)
#             body = node.child_by_field_name("body")
#             if body:
#                 c += self._visit_children(body, nesting + 1)
#             return c

#         # §2.2: do...while → +1 structural
#         if t == "do_statement":
#             inc = 1 + nesting
#             self._add_detail(node, "do-while", 1, nesting)
#             c = inc
#             cond = node.child_by_field_name("condition")
#             if cond:
#                 c += self._visit(cond, nesting)
#             body = node.child_by_field_name("body")
#             if body:
#                 c += self._visit_children(body, nesting + 1)
#             return c

#         # §2.2: catch → +1 structural (try: no increment)
#         if t == "try_statement":
#             c = 0
#             for child in node.children:
#                 c += self._visit(child, nesting)
#             return c

#         if t == "catch_clause":
#             inc = 1 + nesting
#             self._add_detail(node, "catch", 1, nesting)
#             c = inc
#             body = node.child_by_field_name("body")
#             if body:
#                 c += self._visit_children(body, nesting + 1)
#             return c

#         # finally: no increment (not a branch)
#         if t == "finally_clause":
#             c = 0
#             body = node.child_by_field_name("body")
#             if body:
#                 c += self._visit_children(body, nesting)
#             return c

#         # §2.2: ternary → +1 structural
#         # §2.3.2: ternary → receives nesting increment
#         if t == "ternary_expression":
#             inc = 1 + nesting
#             self._add_detail(node, "ternary", 1, nesting)
#             c = inc
#             cond = node.child_by_field_name("condition")
#             if cond:
#                 c += self._visit(cond, nesting)
#             cons = node.child_by_field_name("consequence")
#             if cons:
#                 c += self._visit(cons, nesting + 1)
#             alt = node.child_by_field_name("alternative")
#             if alt:
#                 c += self._visit(alt, nesting + 1)
#             return c

#         # §2.2: break LABEL, continue LABEL → +1 structural
#         if t in ("break_statement", "continue_statement"):
#             has_label = any(ch.type == "identifier" for ch in node.children)
#             if has_label:
#                 keyword = "break" if t == "break_statement" else "continue"
#                 self._add_detail(node, f"{keyword} with label", 1, 0)
#                 return 1
#             return 0

#         # labeled_statement: label 자체는 increment 없음
#         if t == "labeled_statement":
#             c = 0
#             for child in node.children:
#                 if child.type not in ("identifier", ":"):
#                     c += self._visit(child, nesting)
#             return c

#         # §2.2: sequences of like binary logical operators
#         if t == "binary_expression":
#             return self._handle_binary(node, nesting)

#         # parenthesized_expression
#         if t == "parenthesized_expression":
#             return self._visit_children(node, nesting)

#         # §2.3.1: lambda → increment nesting level
#         if t in ("lambda_expression", "anonymous_function", "arrow_function"):
#             c = 0
#             body = node.child_by_field_name("body")
#             if body:
#                 c += self._visit(body, nesting + 1)
#             return c

#         # §2.3.1: anonymous class → increment nesting level
#         if t == "object_creation_expression":
#             c = 0
#             for child in node.children:
#                 if child.type == "class_body":
#                     for item in child.children:
#                         if item.type in ("method_declaration", "constructor_declaration"):
#                             body = item.child_by_field_name("body")
#                             if body:
#                                 c += self._visit_children(body, nesting + 1)
#                         else:
#                             c += self._visit(item, nesting)
#                 else:
#                     c += self._visit(child, nesting)
#             return c

#         # 기타: 자식 재귀
#         return self._visit_children(node, nesting)

#     def _visit_switch_group(self, group_node, nesting):
#         """switch_block_statement_group 내부 처리 (switch_label 제외)"""
#         c = 0
#         for child in group_node.children:
#             if child.type != "switch_label":
#                 c += self._visit(child, nesting)
#         return c

#     # ── if / else if / else chain ──

#     def _handle_if_chain(self, if_node, nesting, is_first=True):
#         c = 0

#         if is_first:
#             # §2.2: if → +1 structural
#             # §2.3.2: if → +nesting penalty
#             inc = 1 + nesting
#             self._add_detail(if_node, "if", 1, nesting)
#             c += inc
#         else:
#             # §2.2: else if → +1 structural, NO nesting penalty (§2.3.2)
#             c += 1
#             self._add_detail(if_node, "else if", 1, 0)

#         # condition
#         cond = if_node.child_by_field_name("condition")
#         if cond:
#             c += self._visit(cond, nesting)

#         # §2.3.1: if/else if → increases nesting level for consequence
#         consequence = if_node.child_by_field_name("consequence") or if_node.child_by_field_name("body")
#         if consequence:
#             c += self._visit_children(consequence, nesting + 1)

#         # alternative
#         alt = if_node.child_by_field_name("alternative")
#         if alt:
#             if alt.type == "if_statement":
#                 c += self._handle_if_chain(alt, nesting, is_first=False)
#             elif alt.type == "else_clause":
#                 # PHP: else_clause contains either if_statement or compound_statement
#                 for ch in alt.children:
#                     if ch.type == "if_statement":
#                         c += self._handle_if_chain(ch, nesting, is_first=False)
#                     elif ch.type in ("compound_statement", "block"):
#                         c += 1
#                         self._add_detail(alt, "else", 1, 0)
#                         c += self._visit_children(ch, nesting + 1)
#             elif alt.type in ("block", "compound_statement"):
#                 c += 1
#                 self._add_detail(alt, "else", 1, 0)
#                 c += self._visit_children(alt, nesting + 1)
#             else:
#                 c += 1
#                 self._add_detail(alt, "else", 1, 0)
#                 c += self._visit(alt, nesting + 1)

#         return c

#     # ── Boolean operator sequences (§2.2) ──

#     def _handle_binary(self, node, nesting):
#         """
#         §2.2: "sequences of like binary logical operators"
#         Same operator in sequence → +1
#         Switch to different operator → +1 additional
#         """
#         ops = []
#         self._collect_logical_ops(node, ops)

#         if not ops:
#             return self._visit_children(node, nesting)

#         c = 0
#         prev = None
#         for op in ops:
#             if prev is None or op != prev:
#                 c += 1
#                 desc = f"logical sequence '{op}'" if prev is None else f"logical change to '{op}'"
#                 self._add_detail_raw(desc, 1)
#                 prev = op
#         return c

#     def _collect_logical_ops(self, node, ops):
#         """binary_expression 트리에서 &&, || 연산자를 좌→우 순서로 수집"""
#         if node.type != "binary_expression":
#             return
#         op_node = node.child_by_field_name("operator")
#         if op_node is None:
#             return
#         op_text = self._text(op_node)
#         if op_text not in ("&&", "||"):
#             return

#         left = node.child_by_field_name("left")
#         right = node.child_by_field_name("right")

#         if left and left.type == "binary_expression":
#             left_op = left.child_by_field_name("operator")
#             if left_op and self._text(left_op) in ("&&", "||"):
#                 self._collect_logical_ops(left, ops)

#         ops.append(op_text)

#         if right and right.type == "binary_expression":
#             right_op = right.child_by_field_name("operator")
#             if right_op and self._text(right_op) in ("&&", "||"):
#                 self._collect_logical_ops(right, ops)


# # ── Public API ──

# def calculate_file(filepath: str):
#     with open(filepath, "r", encoding="utf-8") as f:
#         source = f.read()
#     calc = CognitiveComplexityCalculator(source)
#     return calc.calculate()


# def calculate_source(source_code: str):
#     calc = CognitiveComplexityCalculator(source_code)
#     return calc.calculate()


# def calculate_directory(dirpath: str):
#     all_results = []
#     for root, dirs, files in os.walk(dirpath):
#         for fname in sorted(files):
#             if fname.endswith(".php"):
#                 fpath = os.path.join(root, fname)
#                 try:
#                     results = calculate_file(fpath)
#                     for r in results:
#                         r["file"] = fpath
#                     all_results.extend(results)
#                 except Exception as e:
#                     print(f"Error processing {fpath}: {e}")
#     return all_results


# def print_results(results, verbose=True):
#     total = 0
#     for r in results:
#         total += r["complexity"]
#         print(f"\n{'='*60}")
#         fname = r.get("file", "")
#         if fname:
#             print(f"File: {fname}")
#         print(f"Function: {r['function']} (lines {r['start_line']}-{r['end_line']})")
#         print(f"Cognitive Complexity: {r['complexity']}")
#         if verbose and r["details"]:
#             print("Details:")
#             for d in r["details"]:
#                 print(d)

#     print(f"\n{'='*60}")
#     print(f"Total Cognitive Complexity: {total}")
#     print(f"Number of functions: {len(results)}")
#     if results:
#         print(f"Average per function: {total / len(results):.1f}")


# if __name__ == "__main__":

#     test_code = '''
# class Example {

#     String getName() {
#         return this.name;
#     }

#     int sumOfPrimes(int max) {
#         int total = 0;
#         OUT: for (int i = 1; i <= max; ++i) {
#             for (int j = 2; j < i; ++j) {
#                 if (i % j == 0) {
#                     continue OUT;
#                 }
#             }
#             total += i;
#         }
#         return total;
#     }

#     String getWords(int number) {
#         switch (number) {
#             case 1: return "one";
#             case 2: return "a couple";
#             default: return "lots";
#         }
#     }

#     int complexExample(boolean a, boolean b, int c) {
#         if (a && b) {
#             for (int i = 0; i < c; i++) {
#                 if (i > 10) {
#                     return i;
#                 } else if (i > 5) {
#                     continue;
#                 } else {
#                     System.out.println(i);
#                 }
#             }
#         } else if (c > 0) {
#             switch (c) {
#                 case 1: return 1;
#                 default: return 0;
#             }
#         }
#         return 0;
#     }

#     boolean booleanLogic(boolean a, boolean b, boolean c, boolean d) {
#         if (a && b && c) {
#             return true;
#         } else if (a || b || c) {
#             return false;
#         } else if (a && b || c && d) {
#             return true;
#         } else {
#             return false;
#         }
#     }

#     String tryCatchFinally(String path) {
#         try {
#             if (path == null) {
#                 return "";
#             }
#         } catch (Exception e) {
#             if (e instanceof RuntimeException) {
#                 throw e;
#             }
#         } finally {
#             System.out.println("done");
#         }
#         return path;
#     }

#     void lambdaExample() {
#         Runnable r = () -> {
#             if (true) {
#                 System.out.println("hello");
#             }
#         };
#     }

#     int ternaryExample(boolean flag) {
#         return flag ? 1 : 0;
#     }

#     void doWhileExample(int x) {
#         do {
#             x--;
#         } while (x > 0);
#     }
# }
# '''

#     print("PHP Cognitive Complexity Calculator")
#     print("Based on Campbell 2018 (ICSE TechDebt '18)")
#     print("https://doi.org/10.1145/3194164.3194186")
#     print("=" * 60)

#     results = calculate_source(test_code)
#     print_results(results, verbose=True)

#     # Non-code test (recursion safety)
#     print("\n\n--- Non-code test ---")
#     log = 'WARN Exception encountered org.springframework.context.ApplicationContextException: Unable to start'
#     r2 = calculate_source(log)
#     print(f"Log text: functions={len(r2)}, complexity={sum(x['complexity'] for x in r2)}")

#     if len(sys.argv) > 1:
#         path = sys.argv[1]
#         verbose = "-v" in sys.argv or "--verbose" in sys.argv

#         if os.path.isdir(path):
#             results = calculate_directory(path)
#         elif os.path.isfile(path):
#             results = calculate_file(path)
#         else:
#             print(f"Not found: {path}")
#             sys.exit(1)

#         if "--json" in sys.argv:
#             output = [{
#                 "file": r.get("file", ""),
#                 "function": r["function"],
#                 "complexity": r["complexity"],
#                 "start_line": r["start_line"],
#                 "end_line": r["end_line"],
#             } for r in results]
#             print(json.dumps(output, indent=2))
#         else:
#             print_results(results, verbose)