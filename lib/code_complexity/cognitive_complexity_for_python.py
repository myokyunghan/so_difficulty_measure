"""
Python Cognitive Complexity Calculator
=======================================
Based on: G. Ann Campbell. 2018. "Cognitive Complexity: An Overview and
Evaluation." In TechDebt '18, ICSE, Gothenburg, Sweden.
https://doi.org/10.1145/3194164.3194186

And the SonarSource Cognitive Complexity white paper:
https://www.sonarsource.com/docs/CognitiveComplexity.pdf

Rules (Section 2 of the paper):

  2.1 Ignore readable shorthand structures
      - No increment for the method/function itself
      - No increment for null-coalescing operators

  2.2 Structural increment (+1) for each break in linear flow:
      - if, elif, else                          (§2.2)
      - for, while                              (§2.2)
      - except                                  (§2.2, "catch")
      - conditional expression (x if c else y)  (§2.2, "ternary operator")
      - sequences of like boolean operators     (§2.2)
      - recursion cycles                        (§2.2, not implemented - requires call graph)

  2.3 Nesting:
    2.3.1 These structures INCREMENT the nesting level:
      - if, elif, else, conditional expression  (§2.3.1)
      - for, while                              (§2.3.1)
      - except                                  (§2.3.1)
      - nested methods: lambda, nested def      (§2.3.1, "nested methods and method-like structures")

    2.3.2 These structures RECEIVE a nesting increment (+nesting_level):
      - if, conditional expression              (§2.3.2, NOT elif/else)
      - for, while                              (§2.3.2)
      - except                                  (§2.3.2)

  Summary:
    elif/else: +1 structural only, NO nesting penalty,
               but they DO increase nesting level for their children.

Dependencies: pip install tree-sitter tree-sitter-python
"""

import tree_sitter_python as ts_py
from tree_sitter import Language, Parser
import os
import json
import sys


PY_LANGUAGE = Language(ts_py.language())


def create_parser():
    parser = Parser(PY_LANGUAGE)
    return parser


class CognitiveComplexityCalculator:

    def __init__(self, source_code: str):
        self.source_code = source_code
        self.parser = create_parser()
        self.tree = self.parser.parse(bytes(source_code, "utf-8"))
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
                f"  Line {line:>4}: +{total} ({kind}: +{structural} structural, +{nesting} nesting)"
            )
        else:
            self.details.append(f"  Line {line:>4}: +{total} ({kind})")

    def _add_detail_raw(self, description, increment):
        self.details.append(f"          +{increment} ({description})")

    # ── Top-level traversal ──

    def calculate(self):
        self.results = []
        self._walk_top_level(self.tree.root_node)
        return self.results

    def _walk_top_level(self, node):
        """최상위에서 함수/클래스를 찾음. 무한 재귀 방지를 위해 알려진 타입만 탐색."""
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
            # module 등 알려진 컨테이너만 재귀
            # 그 외 노드(expression, assignment 등)는 탐색하지 않음

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
        """함수 하나의 complexity 계산. §2.1: 함수 자체에는 increment 없음."""
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

        # §2.2, §2.3.2: if → +1 structural, +nesting penalty
        # §2.3.1: if → increments nesting level
        if t == "if_statement":
            return self._handle_if_chain(node, nesting)

        # §2.2: for → +1 structural
        # §2.3.1: for → increments nesting level
        # §2.3.2: for → receives nesting increment
        if t == "for_statement":
            inc = 1 + nesting
            self._add_detail(node, "for", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            # Python for/else: else is a break in flow → +1
            alt = node.child_by_field_name("alternative")
            if alt and alt.type == "else_clause":
                c += 1
                self._add_detail(alt, "for-else", 1, 0)
                body2 = alt.child_by_field_name("body")
                if body2:
                    c += self._visit_children(body2, nesting + 1)
            return c

        # §2.2: while → +1 structural
        # §2.3.1: while → increments nesting level
        # §2.3.2: while → receives nesting increment
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
            # Python while/else
            alt = node.child_by_field_name("alternative")
            if alt and alt.type == "else_clause":
                c += 1
                self._add_detail(alt, "while-else", 1, 0)
                body2 = alt.child_by_field_name("body")
                if body2:
                    c += self._visit_children(body2, nesting + 1)
            return c

        # §2.2: catch → +1 structural (try itself: no increment)
        # §2.3.1: catch → increments nesting level
        # §2.3.2: catch → receives nesting increment
        if t == "try_statement":
            c = 0
            for child in node.children:
                c += self._visit(child, nesting)
            return c

        if t == "except_clause":
            inc = 1 + nesting
            self._add_detail(node, "except", 1, nesting)
            c = inc
            for child in node.children:
                if child.type == "block":
                    c += self._visit_children(child, nesting + 1)
            return c

        # Python finally: no increment (not a branch)
        if t == "finally_clause":
            c = 0
            for child in node.children:
                if child.type == "block":
                    c += self._visit_children(child, nesting)
            return c

        # §2.2: ternary → +1 structural
        # §2.3.1: ternary → increments nesting level
        # §2.3.2: ternary → receives nesting increment
        if t == "conditional_expression":
            inc = 1 + nesting
            self._add_detail(node, "conditional expr", 1, nesting)
            c = inc
            for child in node.children:
                if child.type in ("if", "else"):
                    continue
                c += self._visit(child, nesting + 1)
            return c

        # §2.2: sequences of like binary logical operators
        if t == "boolean_operator":
            return self._handle_boolean(node, nesting)

        # §2.3.1: nested methods → increment nesting level
        if t == "lambda":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                c += self._visit(body, nesting + 1)
            return c

        # §2.3.1: nested methods → increment nesting level
        if t == "function_definition":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

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
        c = 0

        # §2.2: if → +1 structural
        # §2.3.2: if → +nesting penalty
        inc = 1 + nesting
        self._add_detail(if_node, "if", 1, nesting)
        c += inc

        # condition 내부 (boolean operator 등)
        cond = if_node.child_by_field_name("condition")
        if cond:
            c += self._visit(cond, nesting)

        # §2.3.1: if → increases nesting level for consequence
        consequence = if_node.child_by_field_name("consequence")
        if consequence:
            c += self._visit_children(consequence, nesting + 1)

        # elif / else 처리
        for child in if_node.children:
            fname = None
            if child.parent:
                for i, c2 in enumerate(child.parent.children):
                    if c2 == child:
                        fname = child.parent.field_name_for_child(i)
                        break

            if child.type == "elif_clause" and fname == "alternative":
                c += self._handle_elif(child, nesting)
            elif child.type == "else_clause" and fname == "alternative":
                c += self._handle_else(child, nesting)

        return c

    def _handle_elif(self, elif_node, nesting):
        c = 0

        # §2.2: else if → +1 structural
        # §2.3.2: else if → NO nesting penalty (not in §2.3.2 list)
        c += 1
        self._add_detail(elif_node, "elif", 1, 0)

        cond = elif_node.child_by_field_name("condition")
        if cond:
            c += self._visit(cond, nesting)

        # §2.3.1: else if → increases nesting level for consequence
        consequence = elif_node.child_by_field_name("consequence")
        if consequence:
            c += self._visit_children(consequence, nesting + 1)

        # chained elif / else
        for child in elif_node.children:
            fname = None
            if child.parent:
                for i, c2 in enumerate(child.parent.children):
                    if c2 == child:
                        fname = child.parent.field_name_for_child(i)
                        break

            if child.type == "elif_clause" and fname == "alternative":
                c += self._handle_elif(child, nesting)
            elif child.type == "else_clause" and fname == "alternative":
                c += self._handle_else(child, nesting)

        return c

    def _handle_else(self, else_node, nesting):
        c = 0

        # §2.2: else → +1 structural
        # §2.3.2: else → NO nesting penalty
        c += 1
        self._add_detail(else_node, "else", 1, 0)

        # §2.3.1: else → increases nesting level for body
        body = else_node.child_by_field_name("body")
        if body:
            c += self._visit_children(body, nesting + 1)
        return c

    # ── Boolean operator sequences (§2.2) ──

    def _handle_boolean(self, node, nesting):
        """
        §2.2: "sequences of like binary logical operators"
        Same operator in sequence → +1 (once for the whole sequence)
        Switch to different operator → +1 additional

        Examples:
            a and b and c       → +1 (one sequence of 'and')
            a and b or c        → +2 (one 'and', then switch to 'or')
            a or b or c and d   → +2 (one 'or', then switch to 'and')
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
                desc = f"logical sequence '{op}'" if prev is None else f"logical change to '{op}'"
                self._add_detail_raw(desc, 1)
                prev = op
        return c

    def _collect_boolean_ops(self, node, ops):
        """boolean_operator 트리에서 and/or를 좌→우 순서로 수집"""
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
        print(f"Function: {r['function']} (lines {r['start_line']}-{r['end_line']})")
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

    # ── Test cases with expected values from the paper ──
    test_code = '''
def simple_function():
    x = 10
# Expected: 0 (§2.1: no increment for method itself)

def sum_of_primes(max_val):
    total = 0
    for i in range(1, max_val + 1):                # +1 (for, §2.2)
        for j in range(2, i):                       # +2 (for, §2.2 +1, §2.3.2 nesting=1)
            if i % j == 0:                          # +3 (if, §2.2 +1, §2.3.2 nesting=2)
                break
        else:                                       # +1 (for-else, §2.2)
            total += i
    return total
# Expected: 7

def complex_example(a, b, c):
    if a and b:                                     # +1 (if, §2.2) +1 (and, §2.2)
        for i in range(c):                          # +2 (for, nesting=1)
            if i > 10:                              # +3 (if, nesting=2)
                return i
            elif i > 5:                             # +1 (elif, §2.2, no nesting penalty §2.3.2)
                continue
            else:                                   # +1 (else, §2.2, no nesting penalty)
                print(i)
    elif c > 0:                                     # +1 (elif, §2.2)
        pass
# Expected: 10

def boolean_logic(a, b, c, d):
    if a and b and c:                               # +1 (if) +1 (and sequence)
        return True
    elif a or b or c:                               # +1 (elif) +1 (or sequence)
        return False
    elif a and b or c and d:                        # +1 (elif) +1(and) +1(or) +1(and)
        return True
    else:                                           # +1 (else)
        return False
# Expected: 9

def try_example():
    try:                                            # no increment (§2.2: try not listed)
        if True:                                    # +1 (if)
            pass
    except Exception:                               # +1 (except/catch, §2.2)
        if True:                                    # +2 (if, nesting=1)
            raise
# Expected: 4

def nested_def_example():
    def inner():                                    # nesting +1 (§2.3.1)
        if True:                                    # +2 (if, nesting=1)
            pass
    inner()
# Expected: 2

def ternary_example(flag):
    return 1 if flag else 0                         # +1 (ternary, §2.2)
# Expected: 1

def lambda_example():
    items = [1, 2, 3]
    result = list(filter(lambda x: x > 1, items))  # lambda nesting+1, no control flow
# Expected: 0

def finally_example():
    try:
        pass
    except Exception:                               # +1 (except)
        pass
    finally:                                        # no increment (finally is not a branch)
        if True:                                    # +1 (if, nesting=0, finally does not nest)
            pass
# Expected: 2
'''

    print("Python Cognitive Complexity Calculator")
    print("Based on Campbell 2018 (ICSE TechDebt '18)")
    print("https://doi.org/10.1145/3194164.3194186")
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
            
# """
# Python Cognitive Complexity Calculator
# =======================================
# SonarSource Cognitive Complexity 화이트페이퍼 규칙에 따라
# Python 소스코드의 함수별 인지 복잡도를 계산합니다.

# 규칙:
# 1. Structural increment (+1):
#    - if, elif, else, for, while, except
#    - conditional_expression (ternary: x if cond else y)
#    - 논리 연산자 시퀀스 전환 (and, or)

# 2. Nesting increment (+nesting_level):
#    - if, for, while, except, conditional_expression이 중첩될 때
#    - elif / else는 nesting penalty 없음

# 3. Nesting level 증가:
#    - if, for, while, except, conditional_expression
#    - lambda, nested def (함수 내 함수)

# 의존성: pip install tree-sitter tree-sitter-python
# """

# import tree_sitter_python as ts_py
# from tree_sitter import Language, Parser
# import os
# import json
# import sys


# PY_LANGUAGE = Language(ts_py.language())


# def create_parser():
#     parser = Parser(PY_LANGUAGE)
#     return parser


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

#     def calculate(self):
#         self.results = []
#         self._walk_top_level(self.tree.root_node)
#         return self.results

#     def _walk_top_level(self, node):
#         for child in node.children:
#             if child.type == "function_definition":
#                 self._process_function(child)
#             elif child.type == "class_definition":
#                 self._walk_class(child)
#             elif child.type == "decorated_definition":
#                 # @decorator 붙은 함수/클래스
#                 for sub in child.children:
#                     if sub.type == "function_definition":
#                         self._process_function(sub)
#                     elif sub.type == "class_definition":
#                         self._walk_class(sub)

#     def _walk_class(self, class_node):
#         body = class_node.child_by_field_name("body")
#         if body is None:
#             return
#         for child in body.children:
#             if child.type == "function_definition":
#                 self._process_function(child)
#             elif child.type == "class_definition":
#                 self._walk_class(child)
#             elif child.type == "decorated_definition":
#                 for sub in child.children:
#                     if sub.type == "function_definition":
#                         self._process_function(sub)
#                     elif sub.type == "class_definition":
#                         self._walk_class(sub)

#     def _process_function(self, func_node):
#         name_node = func_node.child_by_field_name("name")
#         func_name = self._text(name_node) if name_node else "<anonymous>"

#         self.details = []
#         body = func_node.child_by_field_name("body")
#         complexity = 0
#         if body:
#             complexity = self._visit_children(body, 0)

#         self.results.append({
#             "function": func_name,
#             "complexity": complexity,
#             "start_line": func_node.start_point[0] + 1,
#             "end_line": func_node.end_point[0] + 1,
#             "details": list(self.details),
#         })

#     def _visit_children(self, node, nesting):
#         total = 0
#         for child in node.children:
#             total += self._visit(child, nesting)
#         return total

#     def _visit(self, node, nesting):
#         t = node.type

#         # ── if statement ──
#         if t == "if_statement":
#             return self._handle_if_chain(node, nesting)

#         # ── for statement ──
#         if t == "for_statement":
#             inc = 1 + nesting
#             self._add_detail(node, "for", 1, nesting)
#             c = inc
#             body = node.child_by_field_name("body")
#             if body:
#                 c += self._visit_children(body, nesting + 1)
#             # for/else
#             alt = node.child_by_field_name("alternative")
#             if alt and alt.type == "else_clause":
#                 c += 1
#                 self._add_detail(alt, "for-else", 1, 0)
#                 body2 = alt.child_by_field_name("body")
#                 if body2:
#                     c += self._visit_children(body2, nesting + 1)
#             return c

#         # ── while statement ──
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
#             # while/else
#             alt = node.child_by_field_name("alternative")
#             if alt and alt.type == "else_clause":
#                 c += 1
#                 self._add_detail(alt, "while-else", 1, 0)
#                 body2 = alt.child_by_field_name("body")
#                 if body2:
#                     c += self._visit_children(body2, nesting + 1)
#             return c

#         # ── try statement (try 자체는 increment 없음) ──
#         if t == "try_statement":
#             c = 0
#             for child in node.children:
#                 c += self._visit(child, nesting)
#             return c

#         # ── except clause ──
#         if t == "except_clause":
#             inc = 1 + nesting
#             self._add_detail(node, "except", 1, nesting)
#             c = inc
#             # except body는 마지막 block child
#             for child in node.children:
#                 if child.type == "block":
#                     c += self._visit_children(child, nesting + 1)
#             return c

#         # ── conditional expression (ternary: x if cond else y) ──
#         if t == "conditional_expression":
#             inc = 1 + nesting
#             self._add_detail(node, "conditional expr", 1, nesting)
#             c = inc
#             # 내부 자식들에 대해 nesting+1로 처리
#             for child in node.children:
#                 if child.type in ("if", "else"):
#                     continue
#                 c += self._visit(child, nesting + 1)
#             return c

#         # ── boolean operator (and, or) ──
#         if t == "boolean_operator":
#             return self._handle_boolean(node, nesting)

#         # ── lambda (nesting +1) ──
#         if t == "lambda":
#             c = 0
#             body = node.child_by_field_name("body")
#             if body:
#                 c += self._visit(body, nesting + 1)
#             return c

#         # ── nested function definition (nesting +1) ──
#         if t == "function_definition":
#             # 함수 내 함수: nesting 증가, 별도 결과로 추가하지 않음
#             c = 0
#             body = node.child_by_field_name("body")
#             if body:
#                 c += self._visit_children(body, nesting + 1)
#             return c

#         # ── decorated definition ──
#         if t == "decorated_definition":
#             c = 0
#             for child in node.children:
#                 if child.type in ("function_definition", "class_definition"):
#                     c += self._visit(child, nesting)
#             return c

#         # ── 기타: 자식 재귀 ──
#         return self._visit_children(node, nesting)

#     def _handle_if_chain(self, if_node, nesting):
#         c = 0

#         # if
#         c += 1 + nesting

#         cond = if_node.child_by_field_name("condition")
#         if cond:
#             c += self._visit(cond, nesting)

#         consequence = if_node.child_by_field_name("consequence")
#         if consequence:
#             c += self._visit_children(consequence, nesting + 1)

#         # alternative (elif / else) → 한 번만 처리
#         alt = if_node.child_by_field_name("alternative")
#         if alt:
#             if alt.type == "elif_clause":
#                 c += self._handle_elif(alt, nesting)
#             elif alt.type == "else_clause":
#                 c += self._handle_else(alt, nesting)

#         return c

#     # def _handle_if_chain(self, if_node, nesting):
#     #     c = 0

#     #     # if: +1 structural + nesting penalty
#     #     inc = 1 + nesting
#     #     self._add_detail(if_node, "if", 1, nesting)
#     #     c += inc

#     #     # condition 내부 (boolean operator 등)
#     #     cond = if_node.child_by_field_name("condition")
#     #     if cond:
#     #         c += self._visit(cond, nesting)

#     #     # consequence
#     #     consequence = if_node.child_by_field_name("consequence")
#     #     if consequence:
#     #         c += self._visit_children(consequence, nesting + 1)

#     #     # alternative: elif_clause 또는 else_clause
#     #     # tree-sitter-python은 여러 elif/else를 순차적으로 배치
#     #     for child in if_node.children:
#     #         fname = None
#     #         if child.parent:
#     #             for i, c2 in enumerate(child.parent.children):
#     #                 if c2 == child:
#     #                     fname = child.parent.field_name_for_child(i)
#     #                     break

#     #         if child.type == "elif_clause" and fname == "alternative":
#     #             c += self._handle_elif(child, nesting)
#     #         elif child.type == "else_clause" and fname == "alternative":
#     #             c += self._handle_else(child, nesting)

#     #     return c

#     def _handle_elif(self, elif_node, nesting):
#         c = 0
#         # elif: +1 (nesting penalty 없음)
#         c += 1
#         self._add_detail(elif_node, "elif", 1, 0)

#         cond = elif_node.child_by_field_name("condition")
#         if cond:
#             c += self._visit(cond, nesting)

#         consequence = elif_node.child_by_field_name("consequence")
#         if consequence:
#             c += self._visit_children(consequence, nesting + 1)

#         # elif 뒤의 또 다른 elif/else
#         for child in elif_node.children:
#             fname = None
#             if child.parent:
#                 for i, c2 in enumerate(child.parent.children):
#                     if c2 == child:
#                         fname = child.parent.field_name_for_child(i)
#                         break

#             if child.type == "elif_clause" and fname == "alternative":
#                 c += self._handle_elif(child, nesting)
#             elif child.type == "else_clause" and fname == "alternative":
#                 c += self._handle_else(child, nesting)

#         return c

#     def _handle_else(self, else_node, nesting):
#         c = 0
#         c += 1
#         self._add_detail(else_node, "else", 1, 0)

#         body = else_node.child_by_field_name("body")
#         if body:
#             c += self._visit_children(body, nesting + 1)
#         return c

#     def _handle_boolean(self, node, nesting):
#         """
#         Python의 boolean_operator 처리
#         같은 연산자(and/or) 연속 → +1
#         다른 연산자로 전환 → 추가 +1
#         """
#         ops = []
#         self._collect_boolean_ops(node, ops)

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

#     def _collect_boolean_ops(self, node, ops):
#         if node.type != "boolean_operator":
#             return

#         op_node = node.child_by_field_name("operator")
#         if op_node is None:
#             return
#         op_text = self._text(op_node)
#         if op_text not in ("and", "or"):
#             return

#         left = node.child_by_field_name("left")
#         right = node.child_by_field_name("right")

#         if left and left.type == "boolean_operator":
#             self._collect_boolean_ops(left, ops)

#         ops.append(op_text)

#         if right and right.type == "boolean_operator":
#             self._collect_boolean_ops(right, ops)


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
#             if fname.endswith(".py"):
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
# def simple_function():
#     x = 10

# def sum_of_primes(max_val):
#     total = 0
#     for i in range(1, max_val + 1):                # +1 (for)
#         for j in range(2, i):                       # +2 (for, nesting=1)
#             if i % j == 0:                          # +3 (if, nesting=2)
#                 break                               # no label in python
#         else:                                       # +1 (for-else)
#             total += i
#     return total
# # Expected: 7

# def complex_example(a, b, c):
#     if a and b:                                     # +1 (if) +1 (and)
#         for i in range(c):                          # +2 (for, nesting=1)
#             if i > 10:                              # +3 (if, nesting=2)
#                 return i
#             elif i > 5:                             # +1 (elif)
#                 continue
#             else:                                   # +1 (else)
#                 print(i)
#     elif c > 0:                                     # +1 (elif)
#         pass
# # Expected: 11

# def boolean_logic(a, b, c, d):
#     if a and b and c:                               # +1 (if) +1 (and)
#         return True
#     elif a or b or c:                               # +1 (elif) +1 (or)
#         return False
#     elif a and b or c and d:                        # +1 (elif) +1(and) +1(or) +1(and)
#         return True
#     else:                                           # +1 (else)
#         return False
# # Expected: 9

# def try_example():
#     try:
#         if True:                                    # +1 (if)
#             pass
#     except Exception:                               # +1 (except)
#         if True:                                    # +2 (if, nesting=1)
#             raise
# # Expected: 4

# def nested_def_example():
#     def inner():                                    # nesting +1
#         if True:                                    # +2 (if, nesting=1)
#             pass
#     inner()
# # Expected: 2

# def ternary_example(flag):
#     return 1 if flag else 0                         # +1 (conditional expr)
# # Expected: 1

# def lambda_example():
#     items = [1, 2, 3]
#     result = list(filter(lambda x: x > 1, items))  # lambda: nesting +1, no control flow inside
# # Expected: 0
# '''

#     print("Python Cognitive Complexity Calculator")
#     print("Based on SonarSource Cognitive Complexity specification")
#     print("=" * 60)

#     results = calculate_source(test_code)
#     print_results(results, verbose=True)

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