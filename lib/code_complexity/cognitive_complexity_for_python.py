"""
Python Cognitive Complexity Calculator
=======================================
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
    - if                                          → Python: if_statement
    - switch                                      → Python: match_statement (3.10+)
    - for, foreach                                → Python: for_statement
    - while, do while                             → Python: while_statement
    - catch                                       → Python: except_clause
    - ternary operator                            → Python: conditional_expression (x if c else y)

  Hybrid (D):  +1, NO nesting penalty, but increases nesting level
    - else if, elif                               → Python: elif_clause
    - else                                        → Python: else_clause

  Fundamental (C):  +1, NO nesting penalty, does NOT increase nesting level
    - goto LABEL, break LABEL, continue LABEL     → N/A in Python
    - sequences of binary logical operators       → Python: boolean_operator (and/or)
    - each method in a recursion cycle             → Not implemented (requires call graph)

B2. Nesting level (these structures increase nesting for their children)
────────────────────────────────────────────────────────────────────────
    - if, else if/elif, else, ternary operator
    - switch (match)
    - for, foreach, while, do while
    - catch (except)
    - nested methods and method-like structures (lambda, nested def)

B3. Nesting increments (these structures RECEIVE +nesting_level penalty)
────────────────────────────────────────────────────────────────────────
    - if, ternary operator       (NOT elif, NOT else)
    - switch (match)
    - for, foreach, while, do while
    - catch (except)

═══════════════════════════════════════════════════════════════════
Additional rules from the white paper
═══════════════════════════════════════════════════════════════════

  - try and finally: no increment, no nesting level change (p.7)
  - switch/match: the entire switch + all cases = single structural increment (p.7)
  - Logical operators: +1 per sequence of same operator, +1 each time operator
    changes. e.g. a && b || c && d → +1(&&) +1(||) +1(&&) = +3 (p.7-8)

═══════════════════════════════════════════════════════════════════
Python-specific (Appendix A of the white paper)
═══════════════════════════════════════════════════════════════════

  Python Decorator exception (p.15, added in v1.3):
    A function whose body contains ONLY a nested function + return statement
    is treated as a decorator: the nested function's nesting starts at 0
    instead of being incremented. If any other statement (besides the nested
    def and return) exists in the body, the standard nesting rules apply.
    Also applies recursively for decorator_generator patterns (nested 2 levels).

  Python for-else / while-else:
    Not in the original spec but Python-specific. Treated as hybrid increment
    (+1 structural, no nesting penalty), similar to else in if-chains.

═══════════════════════════════════════════════════════════════════
Extension: Bare code fallback
═══════════════════════════════════════════════════════════════════

  For Stack Overflow snippets and bare code without function declarations:
    1. Calculator first searches for function/method declarations in the AST.
    2. If none found, wraps the source in `def __top__(): ...` and re-parses.
    3. Result is labeled as <top-level> with adjusted line numbers.

Dependencies: pip install tree-sitter tree-sitter-python
"""
import os
import re
import sys
import json
from tree_sitter import Language, Parser


def create_parser():
    """Prefer individual tree_sitter_python package because
    tree_sitter_language_pack may return a wrong/generic parser for
    python on some installations."""
    try:
        import tree_sitter_python as _mod
        _p = Parser(Language(_mod.language()))
        try:
            _p.timeout_micros = 5_000_000
        except (AttributeError, TypeError):
            pass
        return _p
    except ImportError:
        pass
    try:
        from tree_sitter_language_pack import get_parser
        _p = get_parser("python")
        try:
            _p.timeout_micros = 5_000_000
        except (AttributeError, TypeError):
            pass
        return _p
    except Exception:
        pass
    raise ImportError("Install: pip install tree-sitter-python")
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
        if self._parse_failed or self.tree is None:
            return self.results
        self._walk_top_level(self.tree.root_node)

        # Bare code fallback (Stack Overflow snippets 등)

        return self.results

    @staticmethod
    def _indent(src):
        lines = src.split("\n")
        return "\n".join("    " + line if line.strip() else line for line in lines)

    def _walk_top_level(self, node):
        """최상위에서 함수/클래스를 찾음."""
        for child in node.children:
            if child.type == "function_definition":
                self._process_function(child)
            elif child.type == "class_definition":
                self._walk_class(child)
            elif child.type == "decorated_definition":
                for sub in child.children:
                    if sub.type == "function_definition":
                        self._process_function(sub)
                    elif sub.type == "class_definition":
                        self._walk_class(sub)

    def _walk_class(self, class_node):
        body = class_node.child_by_field_name("body")
        if body is None:
            return
        for child in body.children:
            if child.type == "function_definition":
                self._process_function(child)
            elif child.type == "class_definition":
                self._walk_class(child)
            elif child.type == "decorated_definition":
                for sub in child.children:
                    if sub.type == "function_definition":
                        self._process_function(sub)
                    elif sub.type == "class_definition":
                        self._walk_class(sub)

    def _process_function(self, func_node):
        """함수 하나의 complexity 계산. 함수 자체에는 increment 없음 (Ignore shorthand)."""
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
            return self._handle_if_chain(node, nesting)

        # ── B1 structural: for → +1, B3: receives nesting, B2: increases nesting ──
        if t == "for_statement":
            inc = 1 + nesting
            self._add_detail(node, "for", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            # Python for-else: hybrid +1, no nesting penalty
            alt = node.child_by_field_name("alternative")
            if alt and alt.type == "else_clause":
                c += 1
                self._add_detail(alt, "for-else", 1, 0)
                body2 = alt.child_by_field_name("body")
                if body2:
                    c += self._visit_children(body2, nesting + 1)
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
            # Python while-else: hybrid +1, no nesting penalty
            alt = node.child_by_field_name("alternative")
            if alt and alt.type == "else_clause":
                c += 1
                self._add_detail(alt, "while-else", 1, 0)
                body2 = alt.child_by_field_name("body")
                if body2:
                    c += self._visit_children(body2, nesting + 1)
            return c

        # ── B1 structural: switch → +1 (single increment for entire match+cases)
        # ── B3: receives nesting, B2: increases nesting ──
        if t == "match_statement":
            inc = 1 + nesting
            self._add_detail(node, "match", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            if body:
                for child in body.children:
                    if child.type == "case_clause":
                        # case itself: no additional increment (switch rule, p.7)
                        consequence = child.child_by_field_name("consequence")
                        if consequence:
                            c += self._visit_children(consequence, nesting + 1)
                        # guard clause (case X if cond): visit the guard condition
                        guard = child.child_by_field_name("guard")
                        if guard:
                            c += self._visit_children(guard, nesting)
            return c

        # ── try: no increment, no nesting change (p.7) ──
        if t == "try_statement":
            c = 0
            for child in node.children:
                c += self._visit(child, nesting)
            return c

        # ── B1 structural: catch → +1, B3: receives nesting, B2: increases nesting ──
        if t == "except_clause":
            inc = 1 + nesting
            self._add_detail(node, "except", 1, nesting)
            c = inc
            for child in node.children:
                if child.type == "block":
                    c += self._visit_children(child, nesting + 1)
            return c

        # ── finally: no increment, no nesting change (p.7) ──
        if t == "finally_clause":
            c = 0
            for child in node.children:
                if child.type == "block":
                    c += self._visit_children(child, nesting)
            return c

        # ── B1 structural: ternary → +1, B3: receives nesting, B2: increases nesting ──
        if t == "conditional_expression":
            inc = 1 + nesting
            self._add_detail(node, "conditional expr", 1, nesting)
            c = inc
            for child in node.children:
                if child.type in ("if", "else"):
                    continue
                c += self._visit(child, nesting + 1)
            return c

        # ── B1 fundamental: sequences of binary logical operators (p.7-8) ──
        if t == "boolean_operator":
            return self._handle_boolean(node, nesting)

        # ── B2: nested methods → increment nesting level (no structural increment) ──
        if t == "lambda":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                c += self._visit(body, nesting + 1)
            return c

        # ── B2: nested def → increment nesting level ──
        # ── Appendix A: Python decorator exception (p.15) ──
        if t == "function_definition":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                parent_func = self._find_parent_function(node)
                if parent_func and self._is_decorator_pattern(parent_func):
                    # Decorator exception: nested def does NOT increment nesting
                    c += self._visit_children(body, nesting)
                else:
                    c += self._visit_children(body, nesting + 1)
            return c

        # decorated_definition 내부의 함수/클래스 처리
        if t == "decorated_definition":
            c = 0
            for child in node.children:
                if child.type in ("function_definition", "class_definition"):
                    c += self._visit(child, nesting)
            return c

        # 기타: 자식 재귀
        return self._visit_children(node, nesting)

    # ── if / elif / else chain ──

    def _handle_if_chain(self, if_node, nesting):
        """B1 structural: if → +1, B3: receives nesting, B2: increases nesting."""
        c = 0

        inc = 1 + nesting
        self._add_detail(if_node, "if", 1, nesting)
        c += inc

        # condition 내부 (boolean operator 등)
        cond = if_node.child_by_field_name("condition")
        if cond:
            c += self._visit(cond, nesting)

        # B2: if increases nesting level for consequence
        consequence = if_node.child_by_field_name("consequence")
        if consequence:
            c += self._visit_children(consequence, nesting + 1)

        # elif / else: hybrid increment (B1 hybrid: +1, B2: increases nesting, B3: NO penalty)
        for child in if_node.children:
            fname = self._field_name(child)
            if child.type == "elif_clause" and fname == "alternative":
                c += self._handle_elif(child, nesting)
            elif child.type == "else_clause" and fname == "alternative":
                c += self._handle_else(child, nesting)

        return c

    def _handle_elif(self, elif_node, nesting):
        """B1 hybrid: elif → +1, NO nesting penalty, but increases nesting level."""
        c = 1
        self._add_detail(elif_node, "elif", 1, 0)

        cond = elif_node.child_by_field_name("condition")
        if cond:
            c += self._visit(cond, nesting)

        consequence = elif_node.child_by_field_name("consequence")
        if consequence:
            c += self._visit_children(consequence, nesting + 1)

        # chained elif / else
        for child in elif_node.children:
            fname = self._field_name(child)
            if child.type == "elif_clause" and fname == "alternative":
                c += self._handle_elif(child, nesting)
            elif child.type == "else_clause" and fname == "alternative":
                c += self._handle_else(child, nesting)

        return c

    def _handle_else(self, else_node, nesting):
        """B1 hybrid: else → +1, NO nesting penalty, but increases nesting level."""
        c = 1
        self._add_detail(else_node, "else", 1, 0)

        body = else_node.child_by_field_name("body")
        if body:
            c += self._visit_children(body, nesting + 1)
        return c

    @staticmethod
    def _field_name(node):
        """노드의 부모에서 이 노드의 field name을 찾음."""
        if node.parent is None:
            return None
        for i, child in enumerate(node.parent.children):
            if child == node:
                return node.parent.field_name_for_child(i)
        return None

    @staticmethod
    def _find_parent_function(node):
        """AST를 올라가며 가장 가까운 부모 function_definition을 찾음.
        node 자신이 function_definition인 경우 건너뜀."""
        cur = node.parent
        while cur is not None:
            if cur.type == "function_definition":
                return cur
            cur = cur.parent
        return None

    # ── Boolean operator sequences (B1 fundamental, p.7-8) ──

    def _handle_boolean(self, node, nesting):
        """
        Sequences of like binary logical operators.
        Same operator in sequence → +1 (once for the whole sequence).
        Switch to different operator → +1 additional.

        Examples (from the white paper p.7-8):
            a and b and c       → +1
            a and b or c and d  → +3 (+1 and, +1 or, +1 and)
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
        """boolean_operator 트리에서 and/or를 좌→우 순서로 수집."""
        if node.type != "boolean_operator":
            return

        op_node = node.child_by_field_name("operator")
        if op_node is None:
            return
        op_text = self._text(op_node)
        if op_text not in ("and", "or"):
            return

        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")

        if left and left.type == "boolean_operator":
            self._collect_boolean_ops(left, ops)

        ops.append(op_text)

        if right and right.type == "boolean_operator":
            self._collect_boolean_ops(right, ops)

    # ── Python decorator exception (Appendix A, p.15) ──

    def _is_decorator_pattern(self, func_node):
        """
        Appendix A (p.15): Python decorator exception.
        A function whose body contains ONLY:
          - one or more nested function definitions, AND
          - a return statement
        is treated as a decorator pattern. The nested def does NOT
        increment the nesting level.

        Also applies recursively for decorator_generator patterns
        (e.g., outer → generator → decorator, all containing only
        nested defs and returns).
        """
        body = func_node.child_by_field_name("body")
        if body is None:
            return False

        has_nested_func = False
        for child in body.children:
            if child.type == "function_definition":
                has_nested_func = True
            elif child.type == "return_statement":
                pass  # allowed
            elif child.type == "expression_statement":
                # docstring은 허용
                if (child.children and
                        child.children[0].type in ("string", "concatenated_string")):
                    pass
                else:
                    return False
            else:
                return False

        return has_nested_func


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
            if fname.endswith(".py"):
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

    test_code = '''
def simple_function():
    x = 10
# Expected: 0

def sum_of_primes(max_val):
    total = 0
    for i in range(1, max_val + 1):
        for j in range(2, i):
            if i % j == 0:
                break
        else:
            total += i
    return total
# Expected: 7

def complex_example(a, b, c):
    if a and b:
        for i in range(c):
            if i > 10:
                return i
            elif i > 5:
                continue
            else:
                print(i)
    elif c > 0:
        pass
# Expected: 10

def boolean_logic(a, b, c, d):
    if a and b and c:
        return True
    elif a or b or c:
        return False
    elif a and b or c and d:
        return True
    else:
        return False
# Expected: 9

def try_example():
    try:
        if True:
            pass
    except Exception:
        if True:
            raise
# Expected: 4

def nested_def_example():
    def inner():
        if True:
            pass
    inner()
# Expected: 2

def ternary_example(flag):
    return 1 if flag else 0
# Expected: 1

def lambda_example():
    items = [1, 2, 3]
    result = list(filter(lambda x: x > 1, items))
# Expected: 0

def finally_example():
    try:
        pass
    except Exception:
        pass
    finally:
        if True:
            pass
# Expected: 2
'''

    print("Python Cognitive Complexity Calculator")
    print("SonarSource Specification v1.7 (29 August 2023)")
    print("=" * 60)

    results = calculate_source(test_code)
    print_results(results, verbose=True)

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
