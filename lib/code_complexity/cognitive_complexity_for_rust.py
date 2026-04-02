"""
Rust Cognitive Complexity Calculator
=====================================
SonarSource Cognitive Complexity 화이트페이퍼 규칙에 따라
Rust 소스코드의 함수별 인지 복잡도를 계산합니다.

규칙:
1. Structural increment (+1):
   - if, else if, else, match, for, while, loop
   - break/continue with label
   - 논리 연산자 시퀀스 전환

2. Nesting increment (+nesting_level):
   - if, match, for, while, loop이 중첩될 때
   - else if / else는 nesting penalty 없음 (structural +1만)

3. Nesting level 증가 (다음 자식들에게 적용):
   - if, match, for, while, loop, closure

의존성: pip install tree-sitter tree-sitter-rust
"""

import tree_sitter_rust as ts_rust
from tree_sitter import Language, Parser
import os
import json
import sys


RUST_LANGUAGE = Language(ts_rust.language())


def create_parser():
    parser = Parser(RUST_LANGUAGE)
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

    def calculate(self):
        self.results = []
        self._walk_top_level(self.tree.root_node)
        return self.results

    def _walk_top_level(self, node):
        for child in node.children:
            if child.type == "function_item":
                self._process_function(child)
            elif child.type == "impl_item":
                for impl_child in child.children:
                    if impl_child.type == "declaration_list":
                        for item in impl_child.children:
                            if item.type == "function_item":
                                self._process_function(item)
            elif child.type in ("mod_item", "source_file"):
                self._walk_top_level(child)
            elif hasattr(child, 'children'):
                # mod 블록 등
                for grandchild in child.children:
                    if grandchild.type in ("declaration_list",):
                        self._walk_top_level(grandchild)

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
            "start_line": func_node.start_point[0] + 1,
            "end_line": func_node.end_point[0] + 1,
            "details": list(self.details),
        })

    def _visit_children(self, node, nesting):
        total = 0
        for child in node.children:
            total += self._visit(child, nesting)
        return total

    def _visit(self, node, nesting):
        t = node.type

        # ── if expression ──
        if t == "if_expression":
            return self._handle_if_chain(node, nesting, is_first=True)

        # ── match expression ──
        if t == "match_expression":
            inc = 1 + nesting
            self._add_detail(node, "match", 1, nesting)
            c = inc
            match_body = node.child_by_field_name("body")
            if match_body:
                for arm in match_body.children:
                    if arm.type == "match_arm":
                        val = arm.child_by_field_name("value")
                        if val:
                            c += self._visit(val, nesting + 1)
            return c

        # ── for expression ──
        if t == "for_expression":
            inc = 1 + nesting
            self._add_detail(node, "for", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── while expression ──
        if t == "while_expression":
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

        # ── loop expression ──
        if t == "loop_expression":
            inc = 1 + nesting
            self._add_detail(node, "loop", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── break / continue with label ──
        if t in ("break_expression", "continue_expression"):
            has_label = any(child.type == "label" for child in node.children)
            if has_label:
                keyword = "break" if t == "break_expression" else "continue"
                self._add_detail(node, f"{keyword} with label", 1, 0)
                return 1
            return 0

        # ── binary expression (논리 연산자) ──
        if t == "binary_expression":
            return self._handle_binary(node, nesting)

        # ── closure (nesting level +1) ──
        if t == "closure_expression":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                c += self._visit(body, nesting + 1)
            else:
                for child in node.children:
                    if child.type not in ("closure_parameters", "|", "move", "async", "||"):
                        c += self._visit(child, nesting + 1)
            return c

        # ── 기타: 자식 재귀 ──
        return self._visit_children(node, nesting)

    def _handle_if_chain(self, if_node, nesting, is_first=True):
        c = 0

        if is_first:
            inc = 1 + nesting
            self._add_detail(if_node, "if", 1, nesting)
            c += inc
        else:
            c += 1
            self._add_detail(if_node, "else if", 1, 0)

        # condition
        cond = if_node.child_by_field_name("condition")
        if cond:
            c += self._visit(cond, nesting)

        # consequence
        consequence = if_node.child_by_field_name("consequence")
        if consequence:
            c += self._visit_children(consequence, nesting + 1)

        # alternative
        alt = if_node.child_by_field_name("alternative")
        if alt and alt.type == "else_clause":
            c += self._handle_else_clause(alt, nesting)

        return c

    def _handle_else_clause(self, else_clause, nesting):
        c = 0
        for child in else_clause.children:
            if child.type == "if_expression":
                c += self._handle_if_chain(child, nesting, is_first=False)
            elif child.type == "block":
                c += 1
                self._add_detail(else_clause, "else", 1, 0)
                c += self._visit_children(child, nesting + 1)
        return c

    def _handle_binary(self, node, nesting):
        ops = []
        self._collect_logical_ops(node, ops)

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

    def _collect_logical_ops(self, node, ops):
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
            left_op = left.child_by_field_name("operator")
            if left_op and self._text(left_op) in ("&&", "||"):
                self._collect_logical_ops(left, ops)

        ops.append(op_text)

        if right and right.type == "binary_expression":
            right_op = right.child_by_field_name("operator")
            if right_op and self._text(right_op) in ("&&", "||"):
                self._collect_logical_ops(right, ops)


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
            if fname.endswith(".rs"):
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

    test_code = r'''
fn simple_function() {
    let x = 10;
}

fn sum_of_primes(max: i32) -> i32 {
    let mut total = 0;
    'outer: for i in 1..=max {
        for j in 2..i {
            if i % j == 0 {
                continue 'outer;
            }
        }
        total += i;
    }
    total
}

fn get_words(number: i32) -> &'static str {
    match number {
        1 => "one",
        2 => "a couple",
        _ => "lots",
    }
}

fn complex_example(a: bool, b: bool, c: i32) -> i32 {
    if a && b {
        for i in 0..c {
            if i > 10 {
                return i;
            } else if i > 5 {
                continue;
            } else {
                println!("{}", i);
            }
        }
    } else if c > 0 {
        match c {
            1 => return 1,
            _ => return 0,
        }
    }
    0
}

fn boolean_logic(a: bool, b: bool, c: bool, d: bool) -> bool {
    if a && b && c {
        true
    } else if a || b || c {
        false
    } else if a && b || c && d {
        true
    } else {
        false
    }
}
'''

    print("Rust Cognitive Complexity Calculator")
    print("Based on SonarSource Cognitive Complexity specification")
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