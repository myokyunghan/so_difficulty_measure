"""
Go Cognitive Complexity Calculator
====================================
Based on:
  - G. Ann Campbell. 2018. "Cognitive Complexity: An Overview and Evaluation."
    TechDebt '18, ICSE, Gothenburg, Sweden.
    https://doi.org/10.1145/3194164.3194186
  - SonarSource. "Cognitive Complexity - a new way of measuring understandability."
    Version 1.7, 29 August 2023.
    https://www.sonarsource.com/docs/CognitiveComplexity.pdf

═══════════════════════════════════════════════════════════════════
Specification (Appendix B, adapted for Go)
═══════════════════════════════════════════════════════════════════

B1. Increments (+1 each)
────────────────────────
  Structural (B):  +1, receives nesting penalty, increases nesting level
    - if                                  → Go: if_statement
    - switch                              → Go: expression_switch_statement,
                                                 type_switch_statement (single +1, p.7)
    - select                              → Go: select_statement (treated as switch, single +1)
    - for (all forms)                     → Go: for_statement (cond, range, classic, infinite)
                                                 — Go has no while; for handles all loop forms

  Hybrid (D):  +1, NO nesting penalty, but increases nesting level
    - else if                             → Go: if_statement as alternative of if_statement
    - else                                → Go: block as alternative of if_statement

  Fundamental (C):  +1, NO nesting penalty, does NOT increase nesting level
    - goto                                → Go: goto_statement
    - break LABEL, continue LABEL         → Go: break_statement / continue_statement with label_name
    - sequences of binary logical ops     → Go: binary_expression with && / ||
    - each method in a recursion cycle    → Not implemented

  Not applicable in Go:
    - try / catch                         → Go has no try/catch (uses error returns + panic/recover)
    - ternary operator                    → Go has no ternary
    - while, do-while                     → Go uses `for` for all loop forms
    - lambda → Go has func_literal which is treated as nested function (B2)

B2. Nesting level (these structures increase nesting for their children)
────────────────────────────────────────────────────────────────────────
    - if, else if, else
    - switch (expression and type), select
    - for (all forms)
    - nested functions: func_literal, nested function_declaration

B3. Nesting increments (these structures RECEIVE +nesting_level penalty)
────────────────────────────────────────────────────────────────────────
    - if                (NOT else if, NOT else)
    - switch, select
    - for

═══════════════════════════════════════════════════════════════════
Go-specific notes
═══════════════════════════════════════════════════════════════════

  - Go has no while/do-while: all looping uses `for`. Four forms exist:
    `for { }` (infinite), `for cond { }` (while-like),
    `for i := 0; i < n; i++ { }` (classic), `for k, v := range x { }` (range).
    All four are parsed as `for_statement`.
  - Go has no try/catch. Error handling uses `if err != nil` patterns and
    `defer` + `recover()` for panic handling. defer/recover are normal calls.
  - Go has 3 switch-like constructs, all treated as switch (single +1, p.7):
      • expression_switch_statement: classic switch
      • type_switch_statement:       switch x.(type)
      • select_statement:            select { case <-ch: ... }
  - break/continue can take an optional label (label_name child) → +1
    fundamental (p.8). Plain break/continue without label = no increment.
  - goto: +1 fundamental (p.8)
  - func_literal (anonymous function/closure): no structural increment,
    increases nesting level (p.9)
  - method_declaration: walked like function_declaration

═══════════════════════════════════════════════════════════════════
Extension: Bare code fallback
═══════════════════════════════════════════════════════════════════

  For Stack Overflow snippets without function declarations:
    Wraps in `package p\nfunc __top__() { ... }` and re-parses.

Dependencies: pip install tree-sitter tree-sitter-go
"""
import os
import re
import sys
import json
from tree_sitter import Language, Parser


def create_parser():
    try:
        from tree_sitter_language_pack import get_parser
        _p = get_parser("go")
        try:
            _p.timeout_micros = 5_000_000
        except (AttributeError, TypeError):
            pass
        return _p
    except Exception:
        pass
    try:
        import tree_sitter_go as _mod
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
            "  pip install tree-sitter-go")


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
            t = child.type
            if t == "function_declaration":
                self._process_function(child)
            elif t == "method_declaration":
                self._process_function(child)

    def _process_function(self, func_node):
        # function_declaration: name field is 'name'
        # method_declaration: name field is 'name', also has 'receiver'
        name_node = func_node.child_by_field_name("name")
        func_name = self._text(name_node) if name_node else "<anonymous>"

        # For methods, prefix with receiver type
        if func_node.type == "method_declaration":
            receiver = func_node.child_by_field_name("receiver")
            if receiver:
                # Find type identifier inside receiver
                recv_type = self._extract_receiver_type(receiver)
                if recv_type:
                    func_name = f"{recv_type}.{func_name}"

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

    def _extract_receiver_type(self, receiver_node):
        """Extract the type name from method receiver: (r *Type) or (r Type)"""
        for child in receiver_node.children:
            if child.type == "parameter_declaration":
                type_node = child.child_by_field_name("type")
                if type_node:
                    if type_node.type == "pointer_type":
                        for sub in type_node.children:
                            if sub.type == "type_identifier":
                                return self._text(sub)
                    elif type_node.type == "type_identifier":
                        return self._text(type_node)
        return None

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

        # ── B1 structural: for (all forms: cond, range, classic, infinite) ──
        if t == "for_statement":
            inc = 1 + nesting
            self._add_detail(node, "for", 1, nesting)
            c = inc
            # Visit condition for logical operators
            for child in node.children:
                if child.type == "binary_expression":
                    c += self._visit(child, nesting)
                elif child.type == "for_clause":
                    # for i := 0; cond; i++ — visit condition
                    cond = child.child_by_field_name("condition")
                    if cond:
                        c += self._visit(cond, nesting)
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── B1 structural: switch (single +1 for entire switch, p.7) ──
        if t in ("expression_switch_statement", "type_switch_statement"):
            kind = ("type switch" if t == "type_switch_statement"
                    else "switch")
            inc = 1 + nesting
            self._add_detail(node, kind, 1, nesting)
            c = inc
            # Visit case bodies (no additional increment for case/default)
            for child in node.children:
                if child.type in ("expression_case", "type_case", "default_case"):
                    for sub in child.children:
                        if sub.type == "statement_list":
                            c += self._visit_children(sub, nesting + 1)
            return c

        # ── B1 structural: select (treated as switch, single +1) ──
        if t == "select_statement":
            inc = 1 + nesting
            self._add_detail(node, "select", 1, nesting)
            c = inc
            for child in node.children:
                if child.type in ("communication_case", "default_case"):
                    for sub in child.children:
                        if sub.type == "statement_list":
                            c += self._visit_children(sub, nesting + 1)
            return c

        # ── B1 fundamental: goto (p.8) ──
        if t == "goto_statement":
            self._add_detail(node, "goto", 1, 0)
            return 1

        # ── B1 fundamental: break LABEL / continue LABEL (p.8) ──
        if t == "break_statement":
            for child in node.children:
                if child.type == "label_name":
                    self._add_detail(node, "break to label", 1, 0)
                    return 1
            return 0

        if t == "continue_statement":
            for child in node.children:
                if child.type == "label_name":
                    self._add_detail(node, "continue to label", 1, 0)
                    return 1
            return 0

        # ── B1 fundamental: sequences of binary logical operators (p.7-8) ──
        if t == "binary_expression":
            op = node.child_by_field_name("operator")
            if op and self._text(op) in ("&&", "||"):
                return self._handle_boolean(node, nesting)
            return self._visit_children(node, nesting)

        # ── B2: func_literal (closure) → no increment, increases nesting (p.9) ──
        if t == "func_literal":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── labeled_statement: unwrap (label itself is not incremented) ──
        if t == "labeled_statement":
            c = 0
            for child in node.children:
                if child.type not in ("label_name", ":"):
                    c += self._visit(child, nesting)
            return c

        # ── parenthesized_expression: unwrap ──
        if t == "parenthesized_expression":
            return self._visit_children(node, nesting)

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

        # condition (may contain logical operators)
        cond = if_node.child_by_field_name("condition")
        if cond:
            c += self._visit(cond, nesting)

        # initializer (Go: if x := foo(); cond { ... })
        init = if_node.child_by_field_name("initializer")
        if init:
            c += self._visit(init, nesting)

        # consequence
        consequence = if_node.child_by_field_name("consequence")
        if consequence:
            c += self._visit_children(consequence, nesting + 1)

        # alternative: if_statement (else if) or block (else)
        alt = if_node.child_by_field_name("alternative")
        if alt:
            if alt.type == "if_statement":
                c += self._handle_if_chain(alt, nesting, is_else_if=True)
            elif alt.type == "block":
                c += 1
                self._add_detail(alt, "else", 1, 0)
                c += self._visit_children(alt, nesting + 1)

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
            if fname.endswith(".go"):
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
    print("Go Cognitive Complexity Calculator")
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
