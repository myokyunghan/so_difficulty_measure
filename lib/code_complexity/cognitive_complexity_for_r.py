"""
R Cognitive Complexity Calculator
===================================
Based on:
  - G. Ann Campbell. 2018. "Cognitive Complexity: An Overview and Evaluation."
    TechDebt '18, ICSE, Gothenburg, Sweden.
    https://doi.org/10.1145/3194164.3194186
  - SonarSource. "Cognitive Complexity - a new way of measuring understandability."
    Version 1.7, 29 August 2023.
    https://www.sonarsource.com/docs/CognitiveComplexity.pdf

═══════════════════════════════════════════════════════════════════
Specification (Appendix B, adapted for R)
═══════════════════════════════════════════════════════════════════

B1. Increments (+1 each)
────────────────────────
  Structural (B):  +1, receives nesting penalty, increases nesting level
    - if                                  → R: if_statement
    - for                                 → R: for_statement
    - while                               → R: while_statement
    - repeat (do-while equivalent)        → R: repeat_statement
    - switch()                            → R: call with function name "switch" (single +1, p.7)
    - tryCatch() error/warning handlers   → R: treated as catch (p.7)

  Hybrid (D):  +1, NO nesting penalty, but increases nesting level
    - else if                             → R: if_statement as alternative of if_statement
    - else                                → R: braced_expression as alternative of if_statement

  Fundamental (C):  +1, NO nesting penalty, does NOT increase nesting level
    - sequences of logical operators      → R: binary_operator with && / || / & / |
    - each method in a recursion cycle    → Not implemented

  Not applicable in R:
    - goto, labeled break/continue (not in R)
    - ternary operator (R uses ifelse() which is a function call)

B2. Nesting level
────────────────────────────────────────────────────────────────────────
    - if, else if, else
    - for, while, repeat
    - switch, tryCatch error/warning handlers
    - nested functions: function_definition inside another function

B3. Nesting increments (receive +nesting_level penalty)
────────────────────────────────────────────────────────────────────────
    - if               (NOT else if, NOT else)
    - for, while, repeat
    - switch
    - tryCatch error/warning handlers

═══════════════════════════════════════════════════════════════════
R-specific notes
═══════════════════════════════════════════════════════════════════

  - R functions are defined as: name <- function(...) { ... }
    The calculator finds function_definition nodes in assignments.
  - switch() in R is a function call, not a keyword. Parsed as a call node
    with function name "switch". Treated as single +1 structural (p.7).
  - tryCatch() is a function call. error/warning handler arguments that
    contain function(e){...} are treated like catch clauses (+1 each).
    The first positional argument (the "try" body) gets no increment.
    "finally" argument: no increment.
  - repeat {} is R's equivalent of do-while (infinite loop with break).
  - R uses && / || (short-circuit) and & / | (vectorized). Both count
    for logical operator sequences per the spec.
  - Anonymous functions passed as arguments (e.g. lapply(x, function(i) ...))
    increase nesting level like nested methods (p.9).

═══════════════════════════════════════════════════════════════════
Extension: Bare code fallback
═══════════════════════════════════════════════════════════════════

  For snippets without function definitions:
    Wraps in `__top__ <- function() { ... }` and re-parses.

Dependencies: pip install tree-sitter
              tree-sitter-r built from https://github.com/r-lib/tree-sitter-r
"""
import os
import re
import sys
import json
import ctypes
from tree_sitter import Language, Parser


def create_parser():
    """R parser 생성. tree-sitter-r shared library 필요."""
    # 1. tree-sitter-language-pack
    try:
        from tree_sitter_language_pack import get_parser
        return get_parser("r")
    except Exception:
        pass
    # 2. Pre-built shared library
    so_paths = [
        os.path.join(os.path.dirname(__file__), "build", "r.so"),
        os.path.join(os.path.dirname(__file__), "r.so"),
        "/home/claude/build/r.so",
    ]
    for so_path in so_paths:
        if os.path.exists(so_path):
            try:
                lib = ctypes.cdll.LoadLibrary(so_path)
                func = lib.tree_sitter_r
                func.restype = ctypes.c_void_p
                lang = Language(func())
                parser = Parser(lang)
                return parser
            except Exception:
                continue
    raise ImportError(
        "R parser not found. Build tree-sitter-r:\n"
        "  git clone https://github.com/r-lib/tree-sitter-r\n"
        "  gcc -shared -fPIC -O2 -I tree-sitter-r/src "
        "tree-sitter-r/src/parser.c tree-sitter-r/src/scanner.c "
        "-o build/r.so")


# Names of tryCatch handler arguments that act as "catch"
_CATCH_HANDLER_NAMES = frozenset([
    "error", "warning", "message", "condition",
])


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
                f"  Line {line:>4}: +{total} ({kind}: "
                f"+{structural} structural, +{nesting} nesting)")
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
            wrapped = "__top__ <- function() {\n" + self.source_code + "\n}"
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
                            re.sub(r"  Line\s+(\d+):",
                                   lambda m: f"  Line {max(1, int(m.group(1))-1):>4}:", d)
                            if d.startswith("  Line ") else d
                            for d in r["details"]
                        ]
            except Exception:
                pass
        return self.results

    def _walk_top_level(self, node):
        """Find top-level function definitions: name <- function() { ... }"""
        for child in node.children:
            if child.type == "binary_operator":
                op = child.child_by_field_name("operator")
                rhs = child.child_by_field_name("rhs")
                if op and self._text(op) in ("<-", "=", "<<-"):
                    if rhs and rhs.type == "function_definition":
                        lhs = child.child_by_field_name("lhs")
                        func_name = self._text(lhs) if lhs else "<anonymous>"
                        self._process_function(rhs, func_name)
            elif child.type == "function_definition":
                self._process_function(child, "<anonymous>")

    def _process_function(self, func_node, func_name):
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

        # ── B1 structural: for ──
        if t == "for_statement":
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

        # ── B1 structural: repeat (do-while equivalent) ──
        if t == "repeat_statement":
            inc = 1 + nesting
            self._add_detail(node, "repeat", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── call: check for switch() and tryCatch() ──
        if t == "call":
            return self._handle_call(node, nesting)

        # ── B1 fundamental: logical operators (&&, ||, &, |) ──
        if t == "binary_operator":
            op = node.child_by_field_name("operator")
            if op and self._text(op) in ("&&", "||", "&", "|"):
                return self._handle_boolean(node, nesting)
            # Check for nested function assignment: inner <- function() { ... }
            if op and self._text(op) in ("<-", "=", "<<-"):
                rhs = node.child_by_field_name("rhs")
                if rhs and rhs.type == "function_definition":
                    # Nested function: increases nesting level (p.9)
                    c = 0
                    body = rhs.child_by_field_name("body")
                    if body:
                        c += self._visit_children(body, nesting + 1)
                    return c
            return self._visit_children(node, nesting)

        # ── B2: anonymous function_definition (in arguments etc) → nesting (p.9) ──
        if t == "function_definition":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── parenthesized expressions: unwrap ──
        if t in ("parenthesized_expression", "braced_expression"):
            return self._visit_children(node, nesting)

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

        cond = if_node.child_by_field_name("condition")
        if cond:
            c += self._visit(cond, nesting)

        consequence = if_node.child_by_field_name("consequence")
        if consequence:
            c += self._visit_children(consequence, nesting + 1)

        alt = if_node.child_by_field_name("alternative")
        if alt:
            if alt.type == "if_statement":
                c += self._handle_if_chain(alt, nesting, is_else_if=True)
            elif alt.type == "braced_expression":
                c += 1
                self._add_detail(alt, "else", 1, 0)
                c += self._visit_children(alt, nesting + 1)
            else:
                # single statement else (no braces)
                c += 1
                self._add_detail(alt, "else", 1, 0)
                c += self._visit(alt, nesting + 1)
        return c

    # ── call handler: switch() and tryCatch() ──

    def _handle_call(self, node, nesting):
        func_name_node = node.child_by_field_name("function")
        if func_name_node is None:
            return self._visit_children(node, nesting)

        func_name = self._text(func_name_node)

        # ── switch(): single +1 structural (p.7) ──
        if func_name == "switch":
            inc = 1 + nesting
            self._add_detail(node, "switch", 1, nesting)
            c = inc
            # Visit arguments for nested control flow inside case values
            args = node.child_by_field_name("arguments")
            if args:
                for child in args.children:
                    if child.type == "argument":
                        c += self._visit_children(child, nesting + 1)
            return c

        # ── tryCatch(): error/warning handlers as catch (p.7) ──
        if func_name == "tryCatch":
            c = 0
            args = node.child_by_field_name("arguments")
            if args is None:
                return 0
            first_arg = True
            for child in args.children:
                if child.type != "argument":
                    continue
                # Check if named argument
                arg_name = child.child_by_field_name("name")
                if arg_name is None and first_arg:
                    # First positional arg = try body → no increment (like try)
                    first_arg = False
                    c += self._visit_children(child, nesting)
                    continue
                first_arg = False

                name_text = self._text(arg_name) if arg_name else ""
                if name_text == "finally":
                    # finally: no increment, no nesting change
                    c += self._visit_children(child, nesting)
                elif name_text in _CATCH_HANDLER_NAMES:
                    # error/warning/message/condition handler → +1 catch
                    inc = 1 + nesting
                    self._add_detail(child, f"tryCatch {name_text}", 1, nesting)
                    c += inc
                    # The handler value is typically function(e) { ... }
                    # Visit inside at nesting + 1
                    value = child.child_by_field_name("value")
                    if value:
                        if value.type == "function_definition":
                            body = value.child_by_field_name("body")
                            if body:
                                c += self._visit_children(body, nesting + 1)
                        else:
                            c += self._visit(value, nesting + 1)
                else:
                    # Other named args: visit normally
                    c += self._visit_children(child, nesting)
            return c

        # ── Other function calls: recurse into arguments ──
        return self._visit_children(node, nesting)

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
                desc = (f"logical sequence '{op}'" if prev is None
                        else f"logical change to '{op}'")
                self._add_detail_raw(desc, 1)
                prev = op
        return c

    def _collect_boolean_ops(self, node, ops):
        if node.type != "binary_operator":
            return
        op_node = node.child_by_field_name("operator")
        if op_node is None:
            return
        op_text = self._text(op_node)
        if op_text not in ("&&", "||", "&", "|"):
            return
        left = node.child_by_field_name("lhs")
        right = node.child_by_field_name("rhs")
        if left and left.type == "binary_operator":
            lo = left.child_by_field_name("operator")
            if lo and self._text(lo) in ("&&", "||", "&", "|"):
                self._collect_boolean_ops(left, ops)
        ops.append(op_text)
        if right and right.type == "binary_operator":
            ro = right.child_by_field_name("operator")
            if ro and self._text(ro) in ("&&", "||", "&", "|"):
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
            if fname.endswith((".R", ".r")):
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
    print("R Cognitive Complexity Calculator")
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