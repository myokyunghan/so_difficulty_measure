"""
TypeScript Cognitive Complexity Calculator
============================================
Based on: G. Ann Campbell. 2018. "Cognitive Complexity: An Overview and
Evaluation." In TechDebt '18, ICSE, Gothenburg, Sweden.
https://doi.org/10.1145/3194164.3194186

Rules (Section 2 of the paper):

  2.1 Ignore readable shorthand structures
      - No increment for the function/method itself
      - No increment for null-coalescing (?., ??)

  2.2 Structural increment (+1):
      - if, else if, else                             (§2.2)
      - switch                                        (§2.2)
      - for, for...in, for...of, while, do...while   (§2.2)
      - catch                                         (§2.2)
      - ternary (? :)                                 (§2.2)
      - break LABEL, continue LABEL                   (§2.2, "goto LABEL")
      - sequences of like binary logical operators    (§2.2)

  2.3 Nesting:
    2.3.1 Increment nesting level:
      - if, else if, else, switch, ternary            (§2.3.1)
      - for, for...in, for...of, while, do...while   (§2.3.1)
      - catch                                         (§2.3.1)
      - nested functions: arrow, function expr, method (§2.3.1)

    2.3.2 Receive nesting increment (+nesting_level):
      - if, switch, ternary                           (§2.3.2, NOT else if/else)
      - for, for...in, for...of, while, do...while   (§2.3.2)
      - catch                                         (§2.3.2)

Dependencies: pip install tree-sitter tree-sitter-typescript
"""
import os
import sys
import json
from tree_sitter import Language, Parser

def create_parser():
    """tree-sitter-language-pack 우선, 개별 패키지 fallback"""
    # 1. tree-sitter-language-pack
    try:
        from tree_sitter_language_pack import get_parser
        return get_parser("typescript")
    except Exception:
        pass
    # 2. 개별 패키지
    try:
        import tree_sitter_typescript as _mod
        return Parser(Language(_mod.language_typescript()))
    except ImportError:
        raise ImportError(
            "Install one of:\n"
            "  pip install tree-sitter-language-pack\n"
            "  pip install tree-sitter-typescript")


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
        """최상위에서 함수/클래스를 찾음."""
        for child in node.children:
            if child.type == "function_declaration":
                self._process_function(child)
            elif child.type == "class_declaration":
                self._walk_class(child)
            elif child.type in ("lexical_declaration", "variable_declaration"):
                # const fn = () => {} or var fn = function() {}
                self._find_functions_in_declaration(child)
            elif child.type == "expression_statement":
                # module.exports = function() {} etc.
                self._find_functions_in_expression(child)
            elif child.type == "export_statement":
                for sub in child.children:
                    if sub.type == "function_declaration":
                        self._process_function(sub)
                    elif sub.type == "class_declaration":
                        self._walk_class(sub)
                    elif sub.type in ("lexical_declaration", "variable_declaration"):
                        self._find_functions_in_declaration(sub)

    def _find_functions_in_declaration(self, decl_node):
        """변수 선언에서 함수 표현식/화살표 함수를 찾음"""
        for child in decl_node.children:
            if child.type == "variable_declarator":
                name_node = child.child_by_field_name("name")
                value_node = child.child_by_field_name("value")
                if value_node and value_node.type in ("arrow_function", "function"):
                    func_name = self._text(name_node) if name_node else "<anonymous>"
                    self._process_function_node(value_node, func_name)

    def _find_functions_in_expression(self, expr_node):
        """표현식에서 함수 할당을 찾음"""
        for child in expr_node.children:
            if child.type == "assignment_expression":
                right = child.child_by_field_name("right")
                left = child.child_by_field_name("left")
                if right and right.type in ("arrow_function", "function"):
                    func_name = self._text(left) if left else "<anonymous>"
                    self._process_function_node(right, func_name)

    def _walk_class(self, class_node):
        body = class_node.child_by_field_name("body")
        if body is None:
            return
        for child in body.children:
            if child.type == "method_definition":
                self._process_method(child)

    def _process_function(self, func_node):
        """function_declaration 처리"""
        name_node = func_node.child_by_field_name("name")
        func_name = self._text(name_node) if name_node else "<anonymous>"
        self._process_function_node(func_node, func_name)

    def _process_method(self, method_node):
        """class method_definition 처리"""
        name_node = method_node.child_by_field_name("name")
        func_name = self._text(name_node) if name_node else "<anonymous>"

        self.details = []
        body = method_node.child_by_field_name("body")
        complexity = 0
        if body:
            complexity = self._visit_children(body, 0)

        self.results.append({
            "function": func_name,
            "complexity": complexity,
            "start_line": method_node.start_point[0] + 1,
            "end_line": method_node.end_point[0] + 1,
            "details": list(self.details),
        })

    def _process_function_node(self, func_node, func_name):
        """§2.1: 함수 자체에는 increment 없음"""
        self.details = []
        body = func_node.child_by_field_name("body")
        complexity = 0
        if body:
            if body.type == "statement_block":
                complexity = self._visit_children(body, 0)
            else:
                # arrow function with expression body: const f = x => x + 1
                complexity = self._visit(body, 0)

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
        if t == "if_statement":
            return self._handle_if_chain(node, nesting, is_first=True)

        # §2.2: switch → +1 structural
        # §2.3.2: switch → receives nesting increment
        if t == "switch_statement":
            inc = 1 + nesting
            self._add_detail(node, "switch", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            if body:
                for child in body.children:
                    if child.type in ("switch_case", "switch_default"):
                        c += self._visit_case_body(child, nesting + 1)
            return c

        # §2.2: for → +1 structural
        if t == "for_statement":
            inc = 1 + nesting
            self._add_detail(node, "for", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # §2.2: for...in, for...of → +1 structural
        if t == "for_in_statement":
            # tree-sitter-typescript uses for_in_statement for both for-in and for-of
            op = None
            for child in node.children:
                if child.type in ("in", "of"):
                    op = child.type
                    break
            label = f"for...{op}" if op else "for...in"
            inc = 1 + nesting
            self._add_detail(node, label, 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # §2.2: while → +1 structural
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

        # §2.2: do...while → +1 structural
        if t == "do_statement":
            inc = 1 + nesting
            self._add_detail(node, "do...while", 1, nesting)
            c = inc
            cond = node.child_by_field_name("condition")
            if cond:
                c += self._visit(cond, nesting)
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # §2.2: catch → +1 structural (try: no increment)
        if t == "try_statement":
            c = 0
            for child in node.children:
                c += self._visit(child, nesting)
            return c

        if t == "catch_clause":
            inc = 1 + nesting
            self._add_detail(node, "catch", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # finally: no increment (not a branch)
        if t == "finally_clause":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting)
            return c

        # §2.2: ternary → +1 structural
        if t == "ternary_expression":
            inc = 1 + nesting
            self._add_detail(node, "ternary", 1, nesting)
            c = inc
            cond = node.child_by_field_name("condition")
            if cond:
                c += self._visit(cond, nesting)
            cons = node.child_by_field_name("consequence")
            if cons:
                c += self._visit(cons, nesting + 1)
            alt = node.child_by_field_name("alternative")
            if alt:
                c += self._visit(alt, nesting + 1)
            return c

        # §2.2: break LABEL, continue LABEL → +1 structural
        if t in ("break_statement", "continue_statement"):
            has_label = any(ch.type == "statement_identifier" for ch in node.children)
            if has_label:
                keyword = "break" if t == "break_statement" else "continue"
                self._add_detail(node, f"{keyword} with label", 1, 0)
                return 1
            return 0

        # labeled_statement: label 자체는 increment 없음
        if t == "labeled_statement":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                c += self._visit(body, nesting)
            return c

        # §2.2: sequences of like binary logical operators
        if t == "binary_expression":
            return self._handle_binary(node, nesting)

        # parenthesized_expression
        if t == "parenthesized_expression":
            return self._visit_children(node, nesting)

        # §2.3.1: nested functions → increment nesting level
        if t in ("arrow_function", "function"):
            c = 0
            body = node.child_by_field_name("body")
            if body:
                if body.type == "statement_block":
                    c += self._visit_children(body, nesting + 1)
                else:
                    c += self._visit(body, nesting + 1)
            return c

        # generator_function
        if t == "generator_function":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # 기타: 자식 재귀
        return self._visit_children(node, nesting)

    def _visit_case_body(self, case_node, nesting):
        """switch_case / switch_default 내부 처리 (case 자체는 increment 없음)"""
        c = 0
        for child in case_node.children:
            if child.type in ("case", "default", ":"):
                continue
            if child.type == "number" and child.parent and child.parent.type == "switch_case":
                # case value
                continue
            # body field
            fname = None
            if child.parent:
                for i, ch in enumerate(child.parent.children):
                    if ch == child:
                        fname = child.parent.field_name_for_child(i)
                        break
            if fname == "body" or child.type not in ("case", "default", ":", "number", "string"):
                c += self._visit(child, nesting)
        return c

    # ── if / else if / else chain ──

    def _handle_if_chain(self, if_node, nesting, is_first=True):
        c = 0

        if is_first:
            # §2.2: if → +1 structural
            # §2.3.2: if → +nesting penalty
            inc = 1 + nesting
            self._add_detail(if_node, "if", 1, nesting)
            c += inc
        else:
            # §2.2: else if → +1 structural, NO nesting penalty (§2.3.2)
            c += 1
            self._add_detail(if_node, "else if", 1, 0)

        # condition
        cond = if_node.child_by_field_name("condition")
        if cond:
            c += self._visit(cond, nesting)

        # §2.3.1: if → increases nesting level
        consequence = if_node.child_by_field_name("consequence")
        if consequence:
            if consequence.type == "statement_block":
                c += self._visit_children(consequence, nesting + 1)
            else:
                c += self._visit(consequence, nesting + 1)

        # alternative
        alt = if_node.child_by_field_name("alternative")
        if alt:
            if alt.type == "else_clause":
                c += self._handle_else_clause(alt, nesting)
            elif alt.type == "if_statement":
                c += self._handle_if_chain(alt, nesting, is_first=False)
            elif alt.type == "statement_block":
                c += 1
                self._add_detail(alt, "else", 1, 0)
                c += self._visit_children(alt, nesting + 1)
            else:
                c += 1
                self._add_detail(alt, "else", 1, 0)
                c += self._visit(alt, nesting + 1)

        return c

    def _handle_else_clause(self, else_clause, nesting):
        c = 0
        for child in else_clause.children:
            if child.type == "if_statement":
                c += self._handle_if_chain(child, nesting, is_first=False)
            elif child.type == "statement_block":
                c += 1
                self._add_detail(else_clause, "else", 1, 0)
                c += self._visit_children(child, nesting + 1)
        return c

    # ── Boolean operator sequences (§2.2) ──

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
            if fname.endswith((".ts", ".tsx")):
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

    test_code = '''
function simple() {
    let x = 10;
}

function sumOfPrimes(max) {
    let total = 0;
    OUT: for (let i = 1; i <= max; ++i) {
        for (let j = 2; j < i; ++j) {
            if (i % j === 0) {
                continue OUT;
            }
        }
        total += i;
    }
    return total;
}

function getWords(number) {
    switch (number) {
        case 1: return 'one';
        case 2: return 'a couple';
        default: return 'lots';
    }
}

function complexExample(a, b, c) {
    if (a && b) {
        for (let i = 0; i < c; i++) {
            if (i > 10) {
                return i;
            } else if (i > 5) {
                continue;
            } else {
                console.log(i);
            }
        }
    } else if (c > 0) {
        switch (c) {
            case 1: return 1;
            default: return 0;
        }
    }
    return 0;
}

function booleanLogic(a, b, c, d) {
    if (a && b && c) {
        return true;
    } else if (a || b || c) {
        return false;
    } else if (a && b || c && d) {
        return true;
    } else {
        return false;
    }
}

function tryCatchFinally() {
    try {
        if (true) {}
    } catch (e) {
        if (e instanceof Error) {
            throw e;
        }
    } finally {
        console.log('done');
    }
}

const arrowFn = (x) => {
    if (x > 0) return x;
    return -x;
};

const ternaryFn = (flag) => flag ? 1 : 0;

function doWhileExample(x) {
    do {
        x--;
    } while (x > 0);
}

function forOfExample(arr) {
    for (const item of arr) {
        if (item > 0) {
            console.log(item);
        }
    }
}

class MyClass {
    method1() {
        if (true) {
            for (let i = 0; i < 10; i++) {}
        }
    }
    method2(x) {
        return x;
    }
}
'''

    print("TypeScript Cognitive Complexity Calculator")
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