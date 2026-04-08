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
        _p = get_parser("php")
        try:
            _p.timeout_micros = 5_000_000
        except (AttributeError, TypeError):
            pass
        return _p
    except Exception:
        pass
    try:
        import tree_sitter_php as _mod
        _p = Parser(Language(_mod.language_php()))
        try:
            _p.timeout_micros = 5_000_000
        except (AttributeError, TypeError):
            pass
        return _p
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
        if self._parse_failed or self.tree is None:
            return self.results
        self._walk_top_level(self.tree.root_node)

        # Bare code fallback
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
