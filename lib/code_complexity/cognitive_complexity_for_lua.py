"""
Lua Cognitive Complexity Calculator
=====================================
Based on:
  - G. Ann Campbell. 2018. "Cognitive Complexity: An Overview and Evaluation."
    TechDebt '18, ICSE, Gothenburg, Sweden.
    https://doi.org/10.1145/3194164.3194186
  - SonarSource. "Cognitive Complexity - a new way of measuring understandability."
    Version 1.7, 29 August 2023.
    https://www.sonarsource.com/docs/CognitiveComplexity.pdf

═══════════════════════════════════════════════════════════════════
Specification (Appendix B, adapted for Lua)
═══════════════════════════════════════════════════════════════════

B1. Increments (+1 each)
────────────────────────
  Structural (B):  +1, receives nesting penalty, increases nesting level
    - if                                  → Lua: if_statement
    - for (numeric)                       → Lua: for_statement with
                                            for_numeric_clause
    - for (generic, in)                   → Lua: for_statement with
                                            for_generic_clause
    - while                               → Lua: while_statement
    - repeat-until                        → Lua: repeat_statement (Lua's
                                            do-while equivalent; condition
                                            is on `until`)

  Hybrid (D):  +1, NO nesting penalty, but increases nesting level
    - elseif                              → Lua: elseif_statement
    - else                                → Lua: else_statement

  Fundamental (C):  +1, NO nesting penalty, no nesting change
    - goto                                → Lua: goto_statement (Lua 5.2+)
    - sequences of binary logical ops     → Lua: binary_expression with
                                            and / or operators
    - each method in a recursion cycle    → Not implemented

  Not applicable in Lua:
    - switch                              → Lua has no switch statement.
                                            Idiomatic Lua uses if/elseif
                                            chains or table dispatch.
    - try/catch                           → Lua has no try/catch syntax.
                                            Error handling uses pcall/xpcall
                                            function calls — no syntactic
                                            construct to detect.
    - ternary                             → Lua has no ternary operator.
                                            The idiom `cond and a or b` is
                                            a fundamental logical sequence,
                                            already counted via and/or.
    - break LABEL, continue LABEL         → Lua has unlabeled `break` only
                                            (no labels, no `continue`).
                                            Plain break adds no complexity.

B2. Nesting level
────────────────────────────────────────────────────────────────────────
    - if, elseif, else
    - for (numeric and generic)
    - while
    - repeat
    - nested functions: function_definition (anonymous functions),
      nested function_declaration

B3. Nesting increments (receive +nesting_level penalty)
────────────────────────────────────────────────────────────────────────
    - if (NOT elseif, NOT else)
    - for, while, repeat

═══════════════════════════════════════════════════════════════════
Lua-specific notes
═══════════════════════════════════════════════════════════════════

  - Lua uses keyword operators for booleans: `and`, `or`, `not`. Both
    `and` and `or` are short-circuit. `not` is a unary operator and is
    NOT counted as part of logical operator sequences (the spec counts
    only binary boolean operator sequences).

  - Lua has TWO `for` forms:
      • Numeric: `for i = 1, 10 do ... end`     → for_numeric_clause
      • Generic: `for k, v in pairs(t) do end`  → for_generic_clause
    Both are structural increments with nesting.

  - `repeat ... until cond` is Lua's do-while equivalent. Note: the
    condition is evaluated AT THE END (and the loop continues while the
    condition is FALSE — opposite of `while`). +1 structural with nesting.

  - Lua has multiple ways to define functions:
      • `function f() ... end`              — global function
      • `local function f() ... end`        — local function
      • `function Foo.bar() ... end`        — table method via dot
      • `function Foo:bar() ... end`        — table method via colon
                                              (implicit `self` parameter)
      • `f = function() ... end`            — anonymous function assigned
      • `{ greet = function() ... end }`    — function inside a table
                                              constructor
    All are processed as functions. The first four produce
    `function_declaration` nodes; the last two produce `function_definition`
    nodes (anonymous, nested).

  - Lua tables with function fields are the standard OOP pattern. We
    extract method names from `dot_index_expression` (`Foo.bar`) and
    `method_index_expression` (`Foo:bar`) for reporting.

  - Lua 5.2+ supports `goto label` and `::label::` syntax. goto is
    fundamental (+1, no nesting). Label statements themselves do not
    add complexity.

  - Lua has only an unlabeled `break` (no `continue`, no labeled break).
    Per the spec, plain break/continue add no complexity — only the
    LABELED forms do.

  - Lua has no try/catch syntax. Error handling is done via `pcall(f)`
    and `xpcall(f, handler)` library functions. These are regular
    function calls and are not detected as exception handlers.

  - The Lua "ternary" idiom `cond and trueVal or falseVal` is already
    accounted for as a logical operator sequence (and→change to or = +2),
    matching how it would feel to read.

═══════════════════════════════════════════════════════════════════
Extension: Bare code fallback
═══════════════════════════════════════════════════════════════════

  Lua source files are scripts: a `chunk` containing top-level statements.
  If no function declarations are found at all, the entire chunk is
  treated as a `<chunk>` pseudo-function.

Dependencies: pip install tree-sitter tree-sitter-lua
"""
import os
import sys
import json
from tree_sitter import Language, Parser


def create_parser():
    try:
        from tree_sitter_language_pack import get_parser
        _p = get_parser("lua")
        try:
            _p.timeout_micros = 5_000_000
        except (AttributeError, TypeError):
            pass
        return _p
    except Exception:
        pass
    try:
        import tree_sitter_lua as _mod
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
            "  pip install tree-sitter-lua")


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

    def _field_name(self, parent, child):
        for i, c in enumerate(parent.children):
            if c == child:
                return parent.field_name_for_child(i)
        return None

    # ── Top-level traversal ──

    def calculate(self):
        self.results = []
        if self._parse_failed or self.tree is None:
            return self.results
        self._collect_functions(self.tree.root_node)

        # Bare-code fallback: if no functions, treat whole chunk as one
        if not self.results:
            chunk = self.tree.root_node
            self.details = []
            complexity = self._visit_children(chunk, 0)
            if complexity > 0 or self.details:
                self.results.append({
                    "function": "<chunk>",
                    "complexity": complexity,
                    "start_line": chunk.start_point[0] + 1,
                    "end_line": chunk.end_point[0] + 1,
                    "details": list(self.details),
                })
        return self.results

    def _collect_functions(self, node):
        """Walk the tree and collect all top-level (non-nested) functions
        and table-field functions for reporting. Nested functions inside
        another function's body are processed via the visitor (they add
        nesting but are not separate report entries)."""
        # Recursively scan, but stop descending into function bodies
        # because nested functions inside a function get nesting treatment
        # rather than separate reports.
        for child in node.children:
            t = child.type
            if t in ("function_declaration",):
                self._process_function(child)
            elif t == "variable_declaration":
                # local x = function() ... end OR local t = { f = function() ... end }
                self._collect_from_assignment(child)
            elif t == "assignment_statement":
                self._collect_from_assignment(child)
            elif t == "expression_statement":
                self._collect_functions(child)
            else:
                # Recurse into containers (chunk root, blocks at top level)
                if t in ("chunk", "block"):
                    self._collect_functions(child)

    def _collect_from_assignment(self, node):
        """Process anonymous functions on the RHS of an assignment.
        Examples:
          f = function(x) ... end
          local M = { greet = function(self) ... end }
        """
        # Find the variable name(s) and the value(s)
        # variable_declaration wraps assignment_statement; unwrap if needed
        if node.type == "variable_declaration":
            # Look for the inner assignment_statement
            for child in node.children:
                if child.type == "assignment_statement":
                    self._collect_from_assignment(child)
                    return

        var_list = None
        expr_list = None
        for child in node.children:
            if child.type == "variable_list":
                var_list = child
            elif child.type == "expression_list":
                expr_list = child

        if expr_list is None:
            return

        # Get variable names
        var_names = []
        if var_list:
            for child in var_list.children:
                if child.type in ("identifier", "dot_index_expression",
                                   "bracket_index_expression"):
                    var_names.append(self._text(child))

        # Walk expression_list, looking for function_definition or
        # table_constructor with embedded function_definitions.
        idx = 0
        for child in expr_list.children:
            if child.type == "function_definition":
                name = var_names[idx] if idx < len(var_names) else "<anonymous>"
                self._process_function_definition(child, name)
                idx += 1
            elif child.type == "table_constructor":
                base_name = var_names[idx] if idx < len(var_names) else "<table>"
                self._process_table_methods(child, base_name)
                idx += 1
            elif child.type not in (",",):
                idx += 1

    def _process_table_methods(self, table_node, base_name):
        """Walk a table_constructor for function-valued fields."""
        for child in table_node.children:
            if child.type == "field":
                # field has name = value form
                field_name = None
                value_node = None
                for sub in child.children:
                    fn = self._field_name(child, sub)
                    if fn == "name":
                        field_name = self._text(sub)
                    elif fn == "value":
                        value_node = sub
                if value_node is not None and value_node.type == "function_definition":
                    method_name = (f"{base_name}.{field_name}"
                                   if field_name else f"{base_name}.<func>")
                    self._process_function_definition(value_node, method_name)
                elif value_node is not None and value_node.type == "table_constructor":
                    sub_name = (f"{base_name}.{field_name}"
                                if field_name else base_name)
                    self._process_table_methods(value_node, sub_name)

    def _process_function(self, func_node):
        """Process a function_declaration node."""
        name_node = func_node.child_by_field_name("name")
        func_name = self._extract_function_name(name_node)

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

    def _process_function_definition(self, func_node, name):
        """Process an anonymous function_definition with a known name."""
        self.details = []
        body = func_node.child_by_field_name("body")
        complexity = 0
        if body:
            complexity = self._visit_children(body, 0)

        self.results.append({
            "function": name,
            "complexity": complexity,
            "start_line": func_node.start_point[0] + 1,
            "end_line": func_node.end_point[0] + 1,
            "details": list(self.details),
        })

    def _extract_function_name(self, name_node):
        if name_node is None:
            return "<anonymous>"
        t = name_node.type
        if t == "identifier":
            return self._text(name_node)
        if t == "dot_index_expression":
            tbl = name_node.child_by_field_name("table")
            field = name_node.child_by_field_name("field")
            tbl_text = self._text(tbl) if tbl else ""
            f_text = self._text(field) if field else ""
            if tbl_text and f_text:
                return f"{tbl_text}.{f_text}"
        if t == "method_index_expression":
            tbl = name_node.child_by_field_name("table")
            method = name_node.child_by_field_name("method")
            tbl_text = self._text(tbl) if tbl else ""
            m_text = self._text(method) if method else ""
            if tbl_text and m_text:
                return f"{tbl_text}:{m_text}"
        return self._text(name_node) or "<anonymous>"

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

        # ── B1 structural: for (numeric or generic) ──
        if t == "for_statement":
            inc = 1 + nesting
            self._add_detail(node, "for", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            # Visit clause's expressions for any nested structures
            clause = node.child_by_field_name("clause")
            if clause:
                c += self._visit_children(clause, nesting)
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

        # ── B1 structural: repeat-until ──
        if t == "repeat_statement":
            inc = 1 + nesting
            self._add_detail(node, "repeat", 1, nesting)
            c = inc
            cond = node.child_by_field_name("condition")
            if cond:
                c += self._visit(cond, nesting)
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── B1 fundamental: goto (p.8) ──
        if t == "goto_statement":
            self._add_detail(node, "goto", 1, 0)
            return 1

        # ── B1 fundamental: logical operators (and / or) ──
        if t == "binary_expression":
            op = node.child_by_field_name("operator")
            if op and op.type in ("and", "or"):
                return self._handle_boolean(node, nesting)
            return self._visit_children(node, nesting)

        # ── B2: nested function_declaration → nesting (p.9) ──
        if t == "function_declaration":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── B2: function_definition (anonymous) → nesting (p.9) ──
        if t == "function_definition":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── default: recurse ──
        return self._visit_children(node, nesting)

    # ── if / elseif / else chain ──

    def _handle_if_chain(self, if_node, nesting):
        c = 0
        # B1 structural: if → +1, receives nesting
        inc = 1 + nesting
        self._add_detail(if_node, "if", 1, nesting)
        c += inc

        # condition
        cond = if_node.child_by_field_name("condition")
        if cond:
            c += self._visit(cond, nesting)

        # consequence
        consequence = if_node.child_by_field_name("consequence")
        if consequence:
            c += self._visit_children(consequence, nesting + 1)

        # In tree-sitter-lua, elseif_statement and else_statement are
        # SIBLING children of if_statement, both with field name
        # 'alternative'. We must walk all children to find them all
        # (child_by_field_name returns only the first match).
        for i, child in enumerate(if_node.children):
            fn = if_node.field_name_for_child(i)
            if fn != "alternative":
                continue
            t = child.type
            if t == "elseif_statement":
                c += 1
                self._add_detail(child, "elseif", 1, 0)
                cond2 = child.child_by_field_name("condition")
                if cond2:
                    c += self._visit(cond2, nesting)
                cons2 = child.child_by_field_name("consequence")
                if cons2:
                    c += self._visit_children(cons2, nesting + 1)
            elif t == "else_statement":
                c += 1
                self._add_detail(child, "else", 1, 0)
                body = child.child_by_field_name("body")
                if body:
                    c += self._visit_children(body, nesting + 1)
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
        op_text = op_node.type  # 'and' or 'or'
        if op_text not in ("and", "or"):
            return

        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")

        if left and left.type == "binary_expression":
            lo = left.child_by_field_name("operator")
            if lo and lo.type in ("and", "or"):
                self._collect_boolean_ops(left, ops)

        ops.append(op_text)

        if right and right.type == "binary_expression":
            ro = right.child_by_field_name("operator")
            if ro and ro.type in ("and", "or"):
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
            if fname.endswith(".lua"):
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
    print("Lua Cognitive Complexity Calculator")
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
