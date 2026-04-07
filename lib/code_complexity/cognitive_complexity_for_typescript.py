"""
TypeScript Cognitive Complexity Calculator
============================================
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
    - if                                  → TS: if_statement
    - switch                              → TS: switch_statement (single +1, p.7)
    - for, for-in, for-of                 → TS: for_statement, for_in_statement
    - while, do while                     → TS: while_statement, do_statement
    - catch                               → TS: catch_clause
    - ternary operator                    → TS: ternary_expression

  Hybrid (D):  +1, NO nesting penalty, but increases nesting level
    - else if                             → TS: else_clause containing if_statement
    - else                                → TS: else_clause containing statement_block

  Fundamental (C):  +1, NO nesting penalty, does NOT increase nesting level
    - break LABEL, continue LABEL         → TS: break_statement / continue_statement with label
    - sequences of binary logical ops     → TS: binary_expression with && / ||
    - each method in a recursion cycle    → Not implemented

  Ignored (p.6 "Ignore shorthand"):
    - nullish coalescing (??), optional chaining (?.)  → No increment
    - non-null assertion (!)              → No increment (TS-specific)

B2. Nesting level (these structures increase nesting for their children)
────────────────────────────────────────────────────────────────────────
    - if, else if, else, ternary
    - switch
    - for, for-in, for-of, while, do while
    - catch
    - nested functions: arrow_function, function_expression, method_definition

B3. Nesting increments (these structures RECEIVE +nesting_level penalty)
────────────────────────────────────────────────────────────────────────
    - if, ternary       (NOT else if, NOT else)
    - switch
    - for, for-in, for-of, while, do while
    - catch

═══════════════════════════════════════════════════════════════════
TypeScript-specific notes
═══════════════════════════════════════════════════════════════════

  - TypeScript is a superset of JavaScript. Most rules are identical to JS.
  - Type-only constructs do NOT contribute to complexity:
      type_alias_declaration, interface_declaration (no method bodies),
      enum_declaration, type annotations, generic type parameters
  - abstract_class_declaration: walked like class_declaration
  - abstract_method_signature: no body, no complexity
  - method_definition: walked like a function (constructor, get, set included)
  - internal_module (namespace): walked recursively to find functions/classes
  - Decorators: ignored (no body to walk)
  - JS Appendix A p.14 declarative namespace exception: applied here too,
    since it's about the JavaScript-style outer-function pattern.

═══════════════════════════════════════════════════════════════════
Extension: Bare code fallback
═══════════════════════════════════════════════════════════════════

  For Stack Overflow snippets without function declarations:
    Wraps the source in a dummy function and re-parses.

Dependencies: pip install tree-sitter tree-sitter-typescript
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
        return get_parser("typescript")
    except Exception:
        pass
    try:
        import tree_sitter_typescript as _mod
        return Parser(Language(_mod.language_typescript()))
    except ImportError:
        raise ImportError(
            "Install one of:\n"
            "  pip install tree-sitter-language-pack\n"
            "  pip install tree-sitter-typescript")


# Node types that cause a structural increment (B1) - used for declarative check
_STRUCTURAL_FLOW = frozenset([
    "if_statement", "for_statement", "for_in_statement",
    "while_statement", "do_statement", "switch_statement",
])


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

        # Bare code fallback
        if not self.results:
            wrapped = "function __top__() {\n" + self.source_code + "\n}"
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
                            ) if d.startswith("  Line ") else d
                            for d in r["details"]
                        ]
            except Exception:
                pass

        return self.results

    def _walk_top_level(self, node):
        """최상위에서 함수 선언과 클래스/네임스페이스를 찾음."""
        for child in node.children:
            t = child.type
            if t in ("function_declaration", "generator_function_declaration"):
                self._process_function(child)
            elif t in ("class_declaration", "abstract_class_declaration"):
                self._walk_class(child)
            elif t == "internal_module":
                # namespace
                body = child.child_by_field_name("body")
                if body:
                    self._walk_top_level(body)
            elif t == "module":
                body = child.child_by_field_name("body")
                if body:
                    self._walk_top_level(body)
            elif t == "export_statement":
                for sub in child.children:
                    if sub.type in ("function_declaration",
                                    "generator_function_declaration"):
                        self._process_function(sub)
                    elif sub.type in ("class_declaration",
                                      "abstract_class_declaration"):
                        self._walk_class(sub)
                    elif sub.type == "internal_module":
                        body = sub.child_by_field_name("body")
                        if body:
                            self._walk_top_level(body)
            elif t == "expression_statement":
                # namespace can be wrapped in expression_statement in some cases
                for sub in child.children:
                    if sub.type == "internal_module":
                        body = sub.child_by_field_name("body")
                        if body:
                            self._walk_top_level(body)

    def _walk_class(self, class_node):
        """클래스 body 내부의 메서드 탐색."""
        body = class_node.child_by_field_name("body")
        if body is None:
            return
        for child in body.children:
            if child.type == "method_definition":
                self._process_function(child)
            # abstract_method_signature has no body, skip

    def _process_function(self, func_node):
        """함수 하나의 complexity 계산. 함수 자체에는 increment 없음."""
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

        # ── B1 structural: if ──
        if t == "if_statement":
            return self._handle_if_chain(node, nesting, is_else_if=False)

        # ── B1 structural: for / for-in / for-of ──
        if t in ("for_statement", "for_in_statement"):
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

        # ── B1 structural: switch (single +1 for entire switch, p.7) ──
        if t == "switch_statement":
            inc = 1 + nesting
            self._add_detail(node, "switch", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            if body:
                for child in body.children:
                    if child.type in ("switch_case", "switch_default"):
                        # No additional increment for case/default
                        for sub in child.children:
                            if sub.type not in ("case", "default", ":", "number",
                                                "string", "identifier"):
                                c += self._visit(sub, nesting + 1)
            return c

        # ── try: no increment, no nesting change (p.7) ──
        if t == "try_statement":
            c = 0
            for child in node.children:
                c += self._visit(child, nesting)
            return c

        # ── B1 structural: catch → +1, receives nesting, increases nesting ──
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
            body = node.child_by_field_name("body")
            if body:
                return self._visit_children(body, nesting)
            return 0

        # ── B1 structural: ternary → +1, receives nesting, increases nesting ──
        if t == "ternary_expression":
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

        # ── B1 fundamental: sequences of binary logical operators (p.7-8) ──
        if t == "binary_expression":
            op = node.child_by_field_name("operator")
            if op and self._text(op) in ("&&", "||"):
                return self._handle_boolean(node, nesting)
            # Note: ?? (nullish coalescing) is ignored per p.6
            return self._visit_children(node, nesting)

        # ── B1 fundamental: break LABEL / continue LABEL (p.8) ──
        if t == "break_statement":
            label = node.child_by_field_name("label")
            if label:
                self._add_detail(node, "break to label", 1, 0)
                return 1
            return 0

        if t == "continue_statement":
            label = node.child_by_field_name("label")
            if label:
                self._add_detail(node, "continue to label", 1, 0)
                return 1
            return 0

        # ── B2: arrow function → no increment, but increases nesting (p.9) ──
        if t == "arrow_function":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── B2: function expression → no increment, but increases nesting (p.9) ──
        # ── Appendix A p.14: JS declarative namespace exception ──
        if t in ("function_expression", "function"):
            c = 0
            body = node.child_by_field_name("body")
            if body:
                if self._is_declarative_function(body):
                    c += self._visit_children(body, nesting)
                else:
                    c += self._visit_children(body, nesting + 1)
            return c

        # ── B2: generator function expression ──
        if t == "generator_function":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── B2: nested method_definition (e.g. inside object literal) ──
        if t == "method_definition":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── labeled_statement: unwrap (label itself is not incremented) ──
        if t == "labeled_statement":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                c += self._visit(body, nesting)
            return c

        # ── else_clause: handled by _handle_if_chain, skip if encountered alone ──
        if t == "else_clause":
            return 0

        # ── parenthesized_expression: unwrap ──
        if t == "parenthesized_expression":
            return self._visit_children(node, nesting)

        # ── TypeScript type-only nodes: ignore ──
        if t in ("type_annotation", "type_parameters", "type_arguments",
                 "type_alias_declaration", "interface_declaration",
                 "enum_declaration", "ambient_declaration",
                 "as_expression", "satisfies_expression", "type_assertion",
                 "non_null_expression"):
            # type_annotation, type_parameters etc. don't contain runtime code
            # non_null_expression (x!) - just unwrap, the inner expression matters
            if t == "non_null_expression":
                return self._visit_children(node, nesting)
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
            # B1 structural: if → +1, receives nesting
            inc = 1 + nesting
            self._add_detail(if_node, "if", 1, nesting)
            c += inc

        # condition 내부
        cond = if_node.child_by_field_name("condition")
        if cond:
            c += self._visit(cond, nesting)

        # consequence
        consequence = if_node.child_by_field_name("consequence")
        if consequence:
            c += self._visit_children(consequence, nesting + 1)

        # alternative: else_clause
        alt = if_node.child_by_field_name("alternative")
        if alt and alt.type == "else_clause":
            for child in alt.children:
                if child.type == "if_statement":
                    # else if
                    c += self._handle_if_chain(child, nesting, is_else_if=True)
                elif child.type == "statement_block":
                    # else
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
                desc = (f"logical sequence '{op}'"
                        if prev is None
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

    # ── JS declarative namespace exception (Appendix A, p.14) ──

    def _is_declarative_function(self, body_node):
        """
        Appendix A p.14: An outer function used purely as a declarative
        namespace (containing only declarations at top level) is ignored
        for nesting. If any structural control-flow exists at top level,
        it is NOT declarative.
        """
        for child in body_node.children:
            if child.type in ("{", "}"):
                continue
            if child.type in ("variable_declaration", "lexical_declaration",
                              "function_declaration", "class_declaration",
                              "empty_statement", "return_statement",
                              "comment"):
                continue
            if child.type == "expression_statement":
                for sub in child.children:
                    if sub.type in _STRUCTURAL_FLOW:
                        return False
                continue
            if child.type in _STRUCTURAL_FLOW:
                return False
        return True


# ── Public API ──

def calculate_file(filepath: str):
    with open(filepath, "r", encoding="utf-8") as f:
        source = f.read()
    return CognitiveComplexityCalculator(source).calculate()


def calculate_source(source_code: str):
    return CognitiveComplexityCalculator(source_code).calculate()


def calculate_directory(dirpath: str):
    all_results = []
    for root, dirs, files in os.walk(dirpath):
        for fname in sorted(files):
            if fname.endswith((".ts", ".mts", ".cts")):
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

    print("TypeScript Cognitive Complexity Calculator")
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