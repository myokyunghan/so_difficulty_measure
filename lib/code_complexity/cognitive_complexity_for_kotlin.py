"""
Kotlin Cognitive Complexity Calculator
========================================
Based on:
  - G. Ann Campbell. 2018. "Cognitive Complexity: An Overview and Evaluation."
    TechDebt '18, ICSE, Gothenburg, Sweden.
  - SonarSource. "Cognitive Complexity" v1.7, 29 August 2023.

═══════════════════════════════════════════════════════════════════
Specification (Appendix B, adapted for Kotlin)
═══════════════════════════════════════════════════════════════════

B1. Increments (+1 each)
────────────────────────
  Structural (B):  +1, receives nesting penalty, increases nesting level
    - if                                  → Kotlin: if_expression (if is an expression in Kotlin)
    - when (switch equivalent)            → Kotlin: when_expression (single +1, p.7)
    - for                                 → Kotlin: for_statement
    - while, do-while                     → Kotlin: while_statement, do_while_statement
    - catch                               → Kotlin: catch_block (+1, p.7)
    - if-expression as ternary            → same as if_expression (Kotlin has no ?: ternary)

  Hybrid (D):  +1, NO nesting penalty, but increases nesting level
    - else if                             → Kotlin: if_expression as alternative of if_expression
    - else                                → Kotlin: block as alternative of if_expression

  Fundamental (C):  +1, NO nesting penalty, does NOT increase nesting level
    - break@label, continue@label         → Kotlin: labeled_expression with break@/continue@
    - sequences of logical operators      → Kotlin: binary_expression with && / ||
    - each method in a recursion cycle    → Not implemented

B2. Nesting level
────────────────────────────────────────────────────────────────────────
    - if, else if, else
    - when
    - for, while, do-while
    - catch
    - nested functions: lambda_literal, anonymous_function, nested function_declaration

B3. Nesting increments (receive +nesting_level penalty)
────────────────────────────────────────────────────────────────────────
    - if                (NOT else if, NOT else)
    - when
    - for, while, do-while
    - catch

═══════════════════════════════════════════════════════════════════
Kotlin-specific notes
═══════════════════════════════════════════════════════════════════

  - if is an expression in Kotlin (no separate ternary operator).
    `val x = if (a) 1 else 0` is treated the same as a regular if/else.
  - when: Kotlin's switch equivalent. Single +1 for entire when (p.7).
  - break@label / continue@label: Kotlin uses labeled_expression with
    label node containing "break@" or "continue@". +1 fundamental (p.8).
  - try/finally: no increment (p.7). catch_block: +1 structural.
  - Lambda literals { ... }: no structural increment, increases nesting (p.9).
  - Kotlin conjunction/disjunction use standard binary_expression AST.

Dependencies: pip install tree-sitter tree-sitter-kotlin
"""
import os
import re
import sys
import json
from tree_sitter import Language, Parser


def create_parser():
    """Prefer individual tree_sitter_kotlin package because
    tree_sitter_language_pack may return a wrong/generic parser for
    kotlin on some installations."""
    try:
        import tree_sitter_kotlin as _mod
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
        _p = get_parser("kotlin")
        try:
            _p.timeout_micros = 5_000_000
        except (AttributeError, TypeError):
            pass
        return _p
    except Exception:
        pass
    raise ImportError("Install: pip install tree-sitter-kotlin")
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
            if child.type == "function_declaration":
                self._process_function(child)
            elif child.type in ("class_declaration", "object_declaration",
                                "interface_declaration"):
                self._walk_class(child)

    def _walk_class(self, class_node):
        body = class_node.child_by_field_name("body")
        if body is None:
            # Try class_body
            for child in class_node.children:
                if child.type in ("class_body", "enum_class_body"):
                    body = child
                    break
        if body is None:
            return
        for child in body.children:
            if child.type == "function_declaration":
                self._process_function(child)
            elif child.type in ("class_declaration", "object_declaration",
                                "interface_declaration"):
                self._walk_class(child)
            elif child.type == "companion_object":
                for sub in child.children:
                    if sub.type in ("class_body",):
                        for member in sub.children:
                            if member.type == "function_declaration":
                                self._process_function(member)

    def _process_function(self, func_node):
        name_node = func_node.child_by_field_name("name")
        if name_node is None:
            for child in func_node.children:
                if child.type in ("identifier", "simple_identifier"):
                    name_node = child
                    break
        func_name = self._text(name_node) if name_node else "<anonymous>"
        self.details = []

        # Find body: function_body → block, or function_body directly
        body = None
        for child in func_node.children:
            if child.type == "function_body":
                for sub in child.children:
                    if sub.type in ("block", "statements"):
                        body = sub
                        break
                if body is None:
                    body = child
                break

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

        # control_structure_body / statements: pure wrappers, just recurse
        if t in ("control_structure_body", "statements"):
            return self._visit_children(node, nesting)

        # ── B1 structural: if (if_expression) ──
        if t == "if_expression":
            return self._handle_if_chain(node, nesting, is_else_if=False)

        # ── B1 structural: for ──
        if t == "for_statement":
            inc = 1 + nesting
            self._add_detail(node, "for", 1, nesting)
            c = inc
            for child in node.children:
                if child.type in ("block", "control_structure_body", "statements"):
                    c += self._visit_children(child, nesting + 1)
            return c

        # ── B1 structural: while ──
        if t == "while_statement":
            inc = 1 + nesting
            self._add_detail(node, "while", 1, nesting)
            c = inc
            cond = node.child_by_field_name("condition")
            if cond:
                c += self._visit(cond, nesting)
            for child in node.children:
                if child.type in ("block", "control_structure_body", "statements"):
                    c += self._visit_children(child, nesting + 1)
            return c

        # ── B1 structural: do-while ──
        if t == "do_while_statement":
            inc = 1 + nesting
            self._add_detail(node, "do-while", 1, nesting)
            c = inc
            cond = node.child_by_field_name("condition")
            if cond:
                c += self._visit(cond, nesting)
            for child in node.children:
                if child.type in ("block", "control_structure_body", "statements"):
                    c += self._visit_children(child, nesting + 1)
            return c

        # ── B1 structural: when (single +1, p.7) ──
        if t == "when_expression":
            inc = 1 + nesting
            self._add_detail(node, "when", 1, nesting)
            c = inc
            for child in node.children:
                if child.type == "when_entry":
                    c += self._visit_children(child, nesting + 1)
            return c

        # ── try: no increment (p.7) ──
        if t == "try_expression":
            c = 0
            for child in node.children:
                c += self._visit(child, nesting)
            return c

        # ── B1 structural: catch (p.7) ──
        if t == "catch_block":
            inc = 1 + nesting
            self._add_detail(node, "catch", 1, nesting)
            c = inc
            for child in node.children:
                if child.type == "block":
                    c += self._visit_children(child, nesting + 1)
            return c

        # ── finally: no increment (p.7) ──
        if t == "finally_block":
            for child in node.children:
                if child.type == "block":
                    return self._visit_children(child, nesting)
            return 0

        # ── B1 fundamental: logical operators ──
        if t == "binary_expression":
            op = node.child_by_field_name("operator")
            if op and self._text(op) in ("&&", "||"):
                return self._handle_boolean(node, nesting)
            return self._visit_children(node, nesting)

        # Also handle conjunction_expression / disjunction_expression if present
        if t in ("conjunction_expression", "disjunction_expression"):
            return self._handle_boolean_conj_disj(node, nesting)

        # ── B1 fundamental: break@label / continue@label (p.8) ──
        if t == "labeled_expression":
            label_node = None
            for child in node.children:
                if child.type == "label":
                    label_node = child
                    break
            if label_node:
                label_text = self._text(label_node)
                if label_text.startswith("break@") or label_text.startswith("continue@"):
                    kw = "break" if label_text.startswith("break@") else "continue"
                    self._add_detail(node, f"{kw} to label", 1, 0)
                    return 1
            return self._visit_children(node, nesting)

        # ── B2: lambda_literal → nesting (p.9) ──
        if t == "lambda_literal":
            c = 0
            for child in node.children:
                if child.type in ("statements", "block"):
                    c += self._visit_children(child, nesting + 1)
                elif child.type not in ("{", "}", "lambda_parameters", "->"):
                    c += self._visit(child, nesting + 1)
            return c

        # ── B2: anonymous_function → nesting (p.9) ──
        if t == "anonymous_function":
            c = 0
            for child in node.children:
                if child.type in ("function_body", "block"):
                    c += self._visit_children(child, nesting + 1)
            return c

        # ── B2: nested function_declaration → nesting (p.9) ──
        if t == "function_declaration":
            c = 0
            for child in node.children:
                if child.type == "function_body":
                    c += self._visit_children(child, nesting + 1)
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

        # condition
        cond = if_node.child_by_field_name("condition")
        if cond:
            c += self._visit(cond, nesting)

        # Use field-based access for consequence/alternative when available
        # (works for both grammars: 'block' and 'control_structure_body')
        consequence = if_node.child_by_field_name("consequence")
        alternative = if_node.child_by_field_name("alternative")

        if consequence is not None:
            # Visit consequence body (control_structure_body unwraps automatically)
            c += self._visit_children(consequence, nesting + 1)

            if alternative is not None:
                if alternative.type == "if_expression":
                    c += self._handle_if_chain(alternative, nesting, is_else_if=True)
                else:
                    c += 1
                    self._add_detail(alternative, "else", 1, 0)
                    c += self._visit_children(alternative, nesting + 1)
            return c

        # Fallback: legacy children-based traversal for grammars without
        # consequence/alternative fields
        children = list(if_node.children)
        else_idx = None
        for i, child in enumerate(children):
            if child.type == "else":
                else_idx = i
                break

        for child in children[:else_idx] if else_idx else children:
            if child.type in ("block", "control_structure_body", "statements"):
                c += self._visit_children(child, nesting + 1)

        if else_idx is not None:
            for child in children[else_idx + 1:]:
                if child.type == "if_expression":
                    c += self._handle_if_chain(child, nesting, is_else_if=True)
                    break
                elif child.type in ("block", "control_structure_body", "statements"):
                    c += 1
                    self._add_detail(child, "else", 1, 0)
                    c += self._visit_children(child, nesting + 1)
                    break
                elif child.type not in ("{", "}"):
                    c += 1
                    self._add_detail(child, "else", 1, 0)
                    c += self._visit(child, nesting + 1)
                    break

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

    def _handle_boolean_conj_disj(self, node, nesting):
        ops = []
        self._collect_conj_disj_ops(node, ops)
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

    def _collect_conj_disj_ops(self, node, ops):
        if node.type == "conjunction_expression":
            lhs = node.child_by_field_name("lhs")
            rhs = node.child_by_field_name("rhs")
            if lhs and lhs.type in ("conjunction_expression", "disjunction_expression"):
                self._collect_conj_disj_ops(lhs, ops)
            ops.append("&&")
            if rhs and rhs.type in ("conjunction_expression", "disjunction_expression"):
                self._collect_conj_disj_ops(rhs, ops)
        elif node.type == "disjunction_expression":
            lhs = node.child_by_field_name("lhs")
            rhs = node.child_by_field_name("rhs")
            if lhs and lhs.type in ("conjunction_expression", "disjunction_expression"):
                self._collect_conj_disj_ops(lhs, ops)
            ops.append("||")
            if rhs and rhs.type in ("conjunction_expression", "disjunction_expression"):
                self._collect_conj_disj_ops(rhs, ops)


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
            if fname.endswith((".kt", ".kts")):
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
    print("Kotlin Cognitive Complexity Calculator")
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