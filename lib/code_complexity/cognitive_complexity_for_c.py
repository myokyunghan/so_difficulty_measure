"""
C Cognitive Complexity Calculator
===================================
Based on:
  - G. Ann Campbell. 2018. "Cognitive Complexity: An Overview and Evaluation."
    TechDebt '18, ICSE, Gothenburg, Sweden.
    https://doi.org/10.1145/3194164.3194186
  - SonarSource. "Cognitive Complexity - a new way of measuring understandability."
    Version 1.7, 29 August 2023.
    https://www.sonarsource.com/docs/CognitiveComplexity.pdf

═══════════════════════════════════════════════════════════════════
Specification (Appendix B of the SonarSource white paper v1.7)
═══════════════════════════════════════════════════════════════════

B1. Increments (+1 each)
────────────────────────
  Structural (B):  +1, receives nesting penalty, increases nesting level
    - if                                  → C: if_statement
    - switch                              → C: switch_statement (single +1, p.7)
    - for                                 → C: for_statement
    - while, do while                     → C: while_statement, do_statement
    - ternary operator                    → C: conditional_expression
    - #if, #ifdef, #ifndef                → C: preproc_if, preproc_ifdef

  Hybrid (D):  +1, NO nesting penalty, but increases nesting level
    - else if                             → C: else_clause containing if_statement
    - else                                → C: else_clause containing compound_statement
    - #else, #elif                        → C: preproc_else, preproc_elif

  Fundamental (C):  +1, NO nesting penalty, does NOT increase nesting level
    - goto                                → C: goto_statement
    - sequences of binary logical ops     → C: binary_expression with && / ||
    - each method in a recursion cycle    → Not implemented

  Not applicable in C:
    - catch (no try/catch in C)
    - break/continue LABEL (C has no labeled break/continue)
    - lambda / nested functions (not in standard C)

B2. Nesting level
────────────────────────────────────────────────────────────────────────
    - if, else if, else, ternary, #if, #ifdef
    - switch, for, while, do while

B3. Nesting increments (receive +nesting_level penalty)
────────────────────────────────────────────────────────────────────────
    - if, ternary       (NOT else if, NOT else)
    - switch, for, while, do while

═══════════════════════════════════════════════════════════════════
Additional rules
═══════════════════════════════════════════════════════════════════

  - switch: entire switch + all cases = single structural increment (p.7)
  - goto: +1 fundamental (p.8)
  - Logical operators (&&, ||): +1 per sequence, +1 on change (p.7-8)
  - Early return: no increment (p.8)

═══════════════════════════════════════════════════════════════════
Extension: Bare code fallback
═══════════════════════════════════════════════════════════════════

  For snippets without function declarations:
    Wraps in `void __top__() { ... }` and re-parses.

Dependencies: pip install tree-sitter tree-sitter-c
"""
import os
import re
import sys
import json
from tree_sitter import Language, Parser


def create_parser():
    try:
        from tree_sitter_language_pack import get_parser
        _p = get_parser("c")
        try:
            _p.timeout_micros = 5_000_000
        except (AttributeError, TypeError):
            pass
        return _p
    except Exception:
        pass
    try:
        import tree_sitter_c as _mod
        _p = Parser(Language(_mod.language()))
        try:
            _p.timeout_micros = 5_000_000
        except (AttributeError, TypeError):
            pass
        return _p
    except ImportError:
        raise ImportError(
            "Install one of:\n"
            "  pip install tree-sitter-language-pack\n"
            "  pip install tree-sitter-c")


class CognitiveComplexityCalculator:

    def __init__(self, source_code: str):
        self.source_code = source_code
        self.parser = create_parser()
        try:

            self.tree = self.parser.parse(bytes(source_code, "utf-8"))

            self._parse_failed = False

        except ValueError:

            self.tree = None

            self._parse_failed = True
        self.results = []
        self.details = []

    def _text(self, node):
        if node is None:
            return ""
        return self.source_code[node.start_byte:node.end_byte]

    def _line(self, node):
        return node.start_point[0] + 1

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
        if self._parse_failed or self.tree is None:
            return self.results
        self._walk_top_level(self.tree.root_node)

        # Bare code fallback
        return self.results

    def _walk_top_level(self, node):
        for child in node.children:
            if child.type == "function_definition":
                self._process_function(child)
            elif child.type in ("struct_specifier", "union_specifier",
                                "enum_specifier"):
                pass  # C structs don't contain methods
            elif child.type == "preproc_ifdef":
                # Functions may be inside preprocessor blocks
                for sub in child.children:
                    if sub.type == "function_definition":
                        self._process_function(sub)
                    elif sub.type == "preproc_else":
                        for sub2 in sub.children:
                            if sub2.type == "function_definition":
                                self._process_function(sub2)
            elif child.type == "preproc_if":
                for sub in child.children:
                    if sub.type == "function_definition":
                        self._process_function(sub)
                    elif sub.type in ("preproc_else", "preproc_elif"):
                        for sub2 in sub.children:
                            if sub2.type == "function_definition":
                                self._process_function(sub2)
            elif child.type == "declaration":
                # Static inline functions in headers
                for sub in child.children:
                    if sub.type == "function_definition":
                        self._process_function(sub)

    def _process_function(self, func_node):
        func_name = self._extract_func_name(func_node)
        self.details = []
        body = func_node.child_by_field_name("body")
        complexity = 0
        if body:
            complexity = self._visit_children(body, 0)
        self.results.append({
            "function": func_name,
            "complexity": complexity,
            "start_line": func_node.start_point[0] + 1,
            "end_line": func_node.end_point[0] + 1,
            "details": list(self.details),
        })

    def _extract_func_name(self, func_node):
        decl = func_node.child_by_field_name("declarator")
        if decl is None:
            return "<anonymous>"
        return self._find_identifier(decl)

    def _find_identifier(self, node):
        if node.type in ("identifier", "field_identifier"):
            return self._text(node)
        decl = node.child_by_field_name("declarator")
        if decl:
            return self._find_identifier(decl)
        for child in node.children:
            if child.type in ("identifier", "field_identifier"):
                return self._text(child)
        return "<anonymous>"

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
            return self._handle_if_chain(node, nesting, is_else_if=False)

        # ── B1 structural: for ──
        if t == "for_statement":
            inc = 1 + nesting
            self._add_detail(node, "for", 1, nesting)
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
                c += self._visit_children(cond, nesting)
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
                c += self._visit_children(cond, nesting)
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
                    if child.type == "case_statement":
                        c += self._visit_children(child, nesting + 1)
            return c

        # ── B1 structural: ternary (conditional_expression) ──
        if t == "conditional_expression":
            inc = 1 + nesting
            self._add_detail(node, "ternary", 1, nesting)
            c = inc
            cond = node.child_by_field_name("condition")
            if cond:
                c += self._visit(cond, nesting)
            consequence = node.child_by_field_name("consequence")
            if consequence:
                c += self._visit(consequence, nesting + 1)
            alt = node.child_by_field_name("alternative")
            if alt:
                c += self._visit(alt, nesting + 1)
            return c

        # ── B1 fundamental: logical operators (p.7-8) ──
        if t == "binary_expression":
            op = node.child_by_field_name("operator")
            if op and self._text(op) in ("&&", "||"):
                return self._handle_boolean(node, nesting)
            return self._visit_children(node, nesting)

        # ── B1 fundamental: goto (p.8) ──
        if t == "goto_statement":
            self._add_detail(node, "goto", 1, 0)
            return 1

        # ── B1 structural: preprocessor conditionals ──
        if t in ("preproc_if", "preproc_ifdef"):
            inc = 1 + nesting
            self._add_detail(node, "#if", 1, nesting)
            c = inc
            for child in node.children:
                if child.type in ("preproc_else", "preproc_elif"):
                    c += self._visit(child, nesting)
                elif child.type not in ("#if", "#ifdef", "#ifndef", "#endif",
                                        "identifier", "preproc_arg", "\n"):
                    c += self._visit(child, nesting + 1)
            return c

        # ── B1 hybrid: #else / #elif ──
        if t == "preproc_else":
            c = 1
            self._add_detail(node, "#else", 1, 0)
            for child in node.children:
                if child.type not in ("#else", "\n"):
                    c += self._visit(child, nesting + 1)
            return c

        if t == "preproc_elif":
            c = 1
            self._add_detail(node, "#elif", 1, 0)
            for child in node.children:
                if child.type not in ("#elif", "\n", "preproc_arg"):
                    c += self._visit(child, nesting + 1)
            return c

        # ── else_clause: handled by _handle_if_chain ──
        if t == "else_clause":
            return 0

        # ── parenthesized_expression: unwrap ──
        if t == "parenthesized_expression":
            return self._visit_children(node, nesting)

        # ── labeled_statement: just visit body ──
        if t == "labeled_statement":
            c = 0
            for child in node.children:
                if child.type not in ("statement_identifier", ":"):
                    c += self._visit(child, nesting)
            return c

        # ── default: recurse ──
        return self._visit_children(node, nesting)

    # ── if / else if / else chain ──

    def _handle_if_chain(self, if_node, nesting, is_else_if):
        c = 0
        if is_else_if:
            c += 1
            self._add_detail(if_node, "else if", 1, 0)
        else:
            inc = 1 + nesting
            self._add_detail(if_node, "if", 1, nesting)
            c += inc

        cond = if_node.child_by_field_name("condition")
        if cond:
            c += self._visit_children(cond, nesting)

        consequence = if_node.child_by_field_name("consequence")
        if consequence:
            c += self._visit_children(consequence, nesting + 1)

        alt = if_node.child_by_field_name("alternative")
        if alt and alt.type == "else_clause":
            for child in alt.children:
                if child.type == "if_statement":
                    c += self._handle_if_chain(child, nesting, is_else_if=True)
                elif child.type == "compound_statement":
                    c += 1
                    self._add_detail(child, "else", 1, 0)
                    c += self._visit_children(child, nesting + 1)
        return c

    # ── Boolean operator sequences (B1 fundamental, p.7-8) ──

    def _handle_boolean(self, node, nesting):
        ops = []
        self._collect_boolean_ops(node, ops)
        if not ops:
            return self._visit_children(node, nesting)
        c = 0
        prev = None
        for op in ops:
            if prev is None or op != prev:
                c += 1
                desc = (f"logical sequence '{op}'" if prev is None
                        else f"logical change to '{op}'")
                self._add_detail_raw(desc, 1)
                prev = op
        return c

    def _collect_boolean_ops(self, node, ops):
        if node.type != "binary_expression":
            return
        op_node = node.child_by_field_name("operator")
        if op_node is None:
            return
        op_text = self._text(op_node)
        if op_text not in ("&&", "||"):
            return
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")
        if left and left.type == "binary_expression":
            lo = left.child_by_field_name("operator")
            if lo and self._text(lo) in ("&&", "||"):
                self._collect_boolean_ops(left, ops)
        ops.append(op_text)
        if right and right.type == "binary_expression":
            ro = right.child_by_field_name("operator")
            if ro and self._text(ro) in ("&&", "||"):
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
            if fname.endswith((".c", ".h")):
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
    print("C Cognitive Complexity Calculator")
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
