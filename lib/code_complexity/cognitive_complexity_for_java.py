"""
Java Cognitive Complexity Calculator
=====================================
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
    - if                                          → Java: if_statement
    - switch                                      → Java: switch_expression (single +1 for entire switch, p.7)
    - for, foreach                                → Java: for_statement, enhanced_for_statement
    - while, do while                             → Java: while_statement, do_statement
    - catch                                       → Java: catch_clause (single +1 regardless of exception count, p.7)
    - ternary operator                            → Java: ternary_expression

  Hybrid (D):  +1, NO nesting penalty, but increases nesting level
    - else if                                     → Java: if_statement as alternative of if_statement
    - else                                        → Java: block as alternative of if_statement

  Fundamental (C):  +1, NO nesting penalty, does NOT increase nesting level
    - break LABEL, continue LABEL                 → Java: break_statement / continue_statement with identifier
    - sequences of binary logical operators       → Java: binary_expression with && / ||
    - each method in a recursion cycle             → Not implemented (requires call graph)

B2. Nesting level (these structures increase nesting for their children)
────────────────────────────────────────────────────────────────────────
    - if, else if, else, ternary operator
    - switch
    - for, foreach, while, do while
    - catch
    - nested methods: lambda expressions, anonymous classes

B3. Nesting increments (these structures RECEIVE +nesting_level penalty)
────────────────────────────────────────────────────────────────────────
    - if, ternary operator       (NOT else if, NOT else)
    - switch
    - for, foreach, while, do while
    - catch

═══════════════════════════════════════════════════════════════════
Additional rules from the white paper
═══════════════════════════════════════════════════════════════════

  - try and finally: no increment, no nesting level change (p.7)
  - switch: entire switch + all cases = single structural increment (p.7)
  - catch: single +1 regardless of how many exception types caught (p.7)
  - Logical operators: +1 per sequence of same operator, +1 each time
    operator changes. e.g. a && b || c && d → +3 (p.7-8)
  - break/continue to LABEL: +1 fundamental each (p.8)
  - Early return: no increment (p.8)
  - Lambda / anonymous class: no structural increment, but increments
    nesting level (p.9)

═══════════════════════════════════════════════════════════════════
Extension: Bare code fallback
═══════════════════════════════════════════════════════════════════

  For Stack Overflow snippets without class/method declarations:
    1. Calculator first searches for method declarations in the AST.
    2. If none found, wraps the source in a dummy method and re-parses.
    3. Result is labeled as <top-level> with adjusted line numbers.

Dependencies: pip install tree-sitter tree-sitter-java
"""
import os
import re
import sys
import json
from tree_sitter import Language, Parser


def create_parser():
    """tree-sitter-language-pack 우선, 개별 패키지 fallback"""
    try:
        from tree_sitter_language_pack import get_parser
        return get_parser("java")
    except Exception:
        pass
    try:
        import tree_sitter_java as _mod
        return Parser(Language(_mod.language()))
    except ImportError:
        raise ImportError(
            "Install one of:\n"
            "  pip install tree-sitter-language-pack\n"
            "  pip install tree-sitter-java")


class CognitiveComplexityCalculator:

    def __init__(self, source_code: str):
        self.source_code = source_code
        self.parser = create_parser()
        self.tree = self.parser.parse(bytes(source_code, "utf-8"))
        self.results = []
        self.details = []

    # ── Helpers ──

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
                f"+{structural} structural, +{nesting} nesting)"
            )
        else:
            self.details.append(f"  Line {line:>4}: +{total} ({kind})")

    def _add_detail_raw(self, description, increment):
        self.details.append(f"          +{increment} ({description})")

    # ── Top-level traversal ──

    def calculate(self):
        self.results = []
        self._walk_top_level(self.tree.root_node)

        # Bare code fallback (Stack Overflow snippets 등)
        if not self.results:
            wrapped = "class __Top__ { void __top__() {\n" + self.source_code + "\n}}"
            try:
                tree2 = self.parser.parse(bytes(wrapped, "utf-8"))
                if not tree2.root_node.has_error:
                    orig_src, orig_tree = self.source_code, self.tree
                    self.source_code = wrapped
                    self.tree = tree2
                    self.results = []
                    self._walk_top_level(tree2.root_node)
                    self.source_code = orig_src
                    self.tree = orig_tree
                    for r in self.results:
                        r["function"] = "<top-level>"
                        r["start_line"] = max(1, r["start_line"] - 1)
                        r["end_line"] = max(1, r["end_line"] - 1)
                        r["details"] = [
                            re.sub(
                                r"  Line\s+(\d+):",
                                lambda m: f"  Line {max(1, int(m.group(1)) - 1):>4}:",
                                d,
                            )
                            if d.startswith("  Line ") else d
                            for d in r["details"]
                        ]
            except Exception:
                pass

        return self.results

    def _walk_top_level(self, node):
        """최상위에서 클래스/인터페이스/메서드를 찾음."""
        for child in node.children:
            if child.type in ("class_declaration", "interface_declaration",
                              "enum_declaration", "record_declaration"):
                self._walk_class(child)
            elif child.type == "method_declaration":
                self._process_function(child)

    def _walk_class(self, class_node):
        """클래스 body 내부의 메서드와 중첩 클래스 탐색."""
        body = class_node.child_by_field_name("body")
        if body is None:
            return
        for child in body.children:
            if child.type in ("method_declaration", "constructor_declaration"):
                self._process_function(child)
            elif child.type in ("class_declaration", "interface_declaration",
                                "enum_declaration", "record_declaration"):
                self._walk_class(child)

    def _process_function(self, func_node):
        """메서드 하나의 complexity 계산. 메서드 자체에는 increment 없음 (Ignore shorthand)."""
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
            "start_line": func_node.start_point[0] + 1,
            "end_line": func_node.end_point[0] + 1,
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

        # ── B1 structural: if → +1, B3: receives nesting, B2: increases nesting ──
        if t == "if_statement":
            return self._handle_if_chain(node, nesting, is_else_if=False)

        # ── B1 structural: for → +1, B3: receives nesting, B2: increases nesting ──
        if t in ("for_statement", "enhanced_for_statement"):
            inc = 1 + nesting
            self._add_detail(node, "for", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── B1 structural: while → +1, B3: receives nesting, B2: increases nesting ──
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

        # ── B1 structural: do-while → +1, B3: receives nesting, B2: increases nesting ──
        if t == "do_statement":
            inc = 1 + nesting
            self._add_detail(node, "do-while", 1, nesting)
            c = inc
            # condition (parenthesized_expression after 'while')
            cond = node.child_by_field_name("condition")
            if cond:
                c += self._visit(cond, nesting)
            # body (block after 'do')
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── B1 structural: switch → +1 (single increment for entire switch+cases, p.7)
        # ── B3: receives nesting, B2: increases nesting ──
        if t == "switch_expression":
            inc = 1 + nesting
            self._add_detail(node, "switch", 1, nesting)
            c = inc
            # switch_block contains switch_block_statement_group nodes
            for child in node.children:
                if child.type == "switch_block":
                    for group in child.children:
                        if group.type == "switch_block_statement_group":
                            # case/default labels: no additional increment
                            # visit statements inside
                            c += self._visit_children(group, nesting + 1)
            return c

        # ── try: no increment, no nesting change (p.7) ──
        if t == "try_statement":
            c = 0
            for child in node.children:
                c += self._visit(child, nesting)
            return c

        # ── try-with-resources: no increment, no nesting change ──
        if t == "try_with_resources_statement":
            c = 0
            for child in node.children:
                c += self._visit(child, nesting)
            return c

        # ── B1 structural: catch → +1 (single, regardless of exception count, p.7)
        # ── B3: receives nesting, B2: increases nesting ──
        if t == "catch_clause":
            inc = 1 + nesting
            self._add_detail(node, "catch", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── finally: no increment, no nesting change (p.7) ──
        if t == "finally_clause":
            c = 0
            for child in node.children:
                if child.type == "block":
                    c += self._visit_children(child, nesting)
            return c

        # ── B1 structural: ternary → +1, B3: receives nesting, B2: increases nesting ──
        if t == "ternary_expression":
            inc = 1 + nesting
            self._add_detail(node, "ternary", 1, nesting)
            c = inc
            # Visit condition, consequence, alternative
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

        # ── B1 fundamental: sequences of binary logical operators (p.7-8) ──
        if t == "binary_expression":
            op = node.child_by_field_name("operator")
            if op and self._text(op) in ("&&", "||"):
                return self._handle_boolean(node, nesting)
            # Non-logical binary expressions: recurse normally
            return self._visit_children(node, nesting)

        # ── B1 fundamental: break LABEL / continue LABEL (p.8) ──
        if t == "break_statement":
            # break with a label → +1 fundamental
            for child in node.children:
                if child.type == "identifier":
                    self._add_detail(node, "break to label", 1, 0)
                    return 1
            return 0

        if t == "continue_statement":
            # continue with a label → +1 fundamental
            for child in node.children:
                if child.type == "identifier":
                    self._add_detail(node, "continue to label", 1, 0)
                    return 1
            return 0

        # ── B2: lambda → no structural increment, but increments nesting level (p.9) ──
        if t == "lambda_expression":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── B2: anonymous class → no structural increment, but increments nesting level ──
        if t == "object_creation_expression":
            # Check if it has a class_body (anonymous class)
            for child in node.children:
                if child.type == "class_body":
                    c = 0
                    for member in child.children:
                        if member.type in ("method_declaration", "constructor_declaration"):
                            # Visit method body at nesting + 1
                            body = member.child_by_field_name("body")
                            if body:
                                c += self._visit_children(body, nesting + 1)
                        else:
                            c += self._visit(member, nesting + 1)
                    return c
            # No class_body → normal object creation, recurse
            return self._visit_children(node, nesting)

        # ── labeled_statement: just unwrap, don't add increment for the label itself ──
        if t == "labeled_statement":
            c = 0
            for child in node.children:
                if child.type not in ("identifier", ":"):
                    c += self._visit(child, nesting)
            return c

        # ── parenthesized_expression: unwrap ──
        if t == "parenthesized_expression":
            return self._visit_children(node, nesting)

        # ── switch labels (case/default): no increment (handled by switch) ──
        if t in ("switch_label",):
            return 0

        # ── default: recurse ──
        return self._visit_children(node, nesting)

    # ── if / else if / else chain ──

    def _handle_if_chain(self, if_node, nesting, is_else_if):
        c = 0

        if is_else_if:
            # B1 hybrid: else if → +1, NO nesting penalty, increases nesting level
            c += 1
            self._add_detail(if_node, "else if", 1, 0)
        else:
            # B1 structural: if → +1, B3: receives nesting
            inc = 1 + nesting
            self._add_detail(if_node, "if", 1, nesting)
            c += inc

        # condition 내부 (logical operators 등)
        cond = if_node.child_by_field_name("condition")
        if cond:
            c += self._visit(cond, nesting)

        # B2: increases nesting level for consequence
        consequence = if_node.child_by_field_name("consequence")
        if consequence:
            c += self._visit_children(consequence, nesting + 1)

        # alternative: else if or else
        alt = if_node.child_by_field_name("alternative")
        if alt:
            if alt.type == "if_statement":
                # else if: hybrid increment
                c += self._handle_if_chain(alt, nesting, is_else_if=True)
            elif alt.type == "block":
                # else block: hybrid +1, no nesting penalty, increases nesting
                c += 1
                self._add_detail(alt, "else", 1, 0)
                c += self._visit_children(alt, nesting + 1)

        return c

    # ── Boolean operator sequences (B1 fundamental, p.7-8) ──

    def _handle_boolean(self, node, nesting):
        """
        Sequences of like binary logical operators.
        Same operator in sequence → +1 (once for the whole sequence).
        Switch to different operator → +1 additional.

        Examples (from the white paper p.7-8):
            a && b && c && d     → +1
            a || b && c || d     → +3 (+1 ||, +1 &&, +1 ||)
        """
        ops = []
        self._collect_boolean_ops(node, ops)

        if not ops:
            return self._visit_children(node, nesting)

        c = 0
        prev = None
        for op in ops:
            if prev is None or op != prev:
                c += 1
                desc = (f"logical sequence '{op}'"
                        if prev is None
                        else f"logical change to '{op}'")
                self._add_detail_raw(desc, 1)
                prev = op
        return c

    def _collect_boolean_ops(self, node, ops):
        """binary_expression 트리에서 &&/||를 좌→우 순서로 수집."""
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
        source = f.read()
    calc = CognitiveComplexityCalculator(source)
    return calc.calculate()


def calculate_source(source_code: str):
    calc = CognitiveComplexityCalculator(source_code)
    return calc.calculate()


def calculate_directory(dirpath: str):
    all_results = []
    for root, dirs, files in os.walk(dirpath):
        for fname in sorted(files):
            if fname.endswith(".java"):
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

    print("Java Cognitive Complexity Calculator")
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
            output = [{
                "file": r.get("file", ""),
                "function": r["function"],
                "complexity": r["complexity"],
                "start_line": r["start_line"],
                "end_line": r["end_line"],
            } for r in results]
            print(json.dumps(output, indent=2))
        else:
            print_results(results, verbose)