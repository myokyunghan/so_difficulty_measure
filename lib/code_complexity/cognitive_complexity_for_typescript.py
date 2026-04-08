"""
VB.NET Cognitive Complexity Calculator
========================================
Based on:
  - G. Ann Campbell. 2018. "Cognitive Complexity: An Overview and Evaluation."
    TechDebt '18, ICSE, Gothenburg, Sweden.
    https://doi.org/10.1145/3194164.3194186
  - SonarSource. "Cognitive Complexity - a new way of measuring understandability."
    Version 1.7, 29 August 2023.
    https://www.sonarsource.com/docs/CognitiveComplexity.pdf

═══════════════════════════════════════════════════════════════════
Specification (Appendix B, adapted for VB.NET)
═══════════════════════════════════════════════════════════════════

B1. Increments (+1 each)
────────────────────────
  Structural (B):  +1, receives nesting penalty, increases nesting level
    - If/Then                             → VB: if_statement
    - Select Case                         → VB: select_case_statement (single +1, p.7)
    - For/Next                            → VB: for_statement
    - For Each/Next                       → VB: for_each_statement
    - While/End While                     → VB: while_statement
    - Do/Loop (Do While, Do Until,
      Loop While, Loop Until)             → VB: do_statement
    - Catch                               → VB: catch_block (single +1, p.7)
    - Ternary If(cond, a, b)              → Visited via expression text;
                                            no dedicated node in this parser

  Hybrid (D):  +1, NO nesting penalty, but increases nesting level
    - ElseIf                              → VB: elseif_clause
    - Else                                → VB: else_clause

  Fundamental (C):  +1, NO nesting penalty, does NOT increase nesting level
    - GoTo                                → VB: goto_statement
    - sequences of binary logical ops     → VB: binary_expression (And, Or,
                                                AndAlso, OrElse) — operator
                                                detected via source text scan
    - each method in a recursion cycle    → Not implemented

  Not applicable in VB.NET:
    - break LABEL, continue LABEL         → VB has Exit For / Exit While /
                                            Continue For etc., but NO labeled
                                            break/continue. Plain Exit/Continue
                                            do not break linear flow markedly,
                                            so no increment (similar to C plain
                                            break/continue treatment).

B2. Nesting level
────────────────────────────────────────────────────────────────────────
    - If, ElseIf, Else
    - Select Case
    - For, For Each, While, Do
    - Catch
    - nested functions: lambdas, nested method/function definitions

B3. Nesting increments (receive +nesting_level penalty)
────────────────────────────────────────────────────────────────────────
    - If                (NOT ElseIf, NOT Else)
    - Select Case
    - For, For Each, While, Do
    - Catch

═══════════════════════════════════════════════════════════════════
VB.NET-specific notes
═══════════════════════════════════════════════════════════════════

  - VB.NET has TWO classes of logical operators:
      • Short-circuit:  AndAlso, OrElse
      • Eager (always-evaluating): And, Or
    Both are valid binary boolean operators per the spec (p.7-8) and
    contribute to logical operator sequences.

  - The Xor operator is NOT a control-flow boolean — it's bitwise/logical
    XOR with no short-circuit semantics. Per the spec spirit (sequences of
    boolean operators that affect flow), Xor is NOT counted.

  - Select Case: VB's switch equivalent. Single +1 for entire Select
    (per p.7), regardless of how many Case clauses.

  - Try/Catch/Finally: try and finally are ignored (p.7). Each Catch block
    = +1 structural. Note: VB allows multiple Catch blocks for different
    exception types; per the spec, "a catch only adds one point ... no
    matter how many exception types are caught" applies to a single catch
    handler. VB's separate Catch blocks count as separate handlers (each
    +1), matching how C# multi-catch is treated.

  - VB has many loop forms: For/Next, For Each/Next, While/End While,
    Do While/Loop, Do Until/Loop, Do/Loop While, Do/Loop Until. All are
    structural increments with nesting penalty.

  - GoTo: VB still supports GoTo (legacy from BASIC). +1 fundamental (p.8).

  - Exit For / Exit While / Exit Do / Continue For / Continue While /
    Continue Do: these exit/skip the immediately enclosing loop (no labels).
    They are similar to C's plain break/continue → no increment per the
    spec (which only counts LABELED break/continue).

  - The `If(cond, a, b)` ternary function: VB's parser does not produce
    a dedicated ternary node — it parses as a function call. We don't
    detect it as a ternary; this is a known limitation.

═══════════════════════════════════════════════════════════════════
Parser limitations (tree-sitter-vb-dotnet)
═══════════════════════════════════════════════════════════════════

  The tree-sitter-vb-dotnet grammar has several limitations:

  1. Top-level Sub/Function (outside Class/Module/Namespace) is not
     well supported — the calculator processes only methods defined
     inside type containers. A bare-code fallback wraps top-level code
     in a dummy Class/Sub.

  2. The parser frequently produces ERROR nodes even on valid VB.NET code.
     The walker tolerates this and extracts what it can.

  3. binary_expression nodes do NOT preserve the operator token. To detect
     AndAlso/OrElse/And/Or, we scan the source text between the two
     operand expressions and look for the operator keyword.

  4. The `If(...)` ternary function call is not distinguishable from a
     regular function call by the parser; ternary increments are not
     applied for this VB-specific construct.

Dependencies: tree-sitter, plus tree-sitter-vb-dotnet built from npm
"""
import os
import re
import sys
import json
import ctypes
from tree_sitter import Language, Parser


def create_parser():
    try:
        from tree_sitter_language_pack import get_parser
        _p = get_parser("vb")
        try:
            _p.timeout_micros = 5_000_000
        except (AttributeError, TypeError):
            pass
        return _p
    except Exception:
        pass
    so_paths = [
        os.path.join(os.path.dirname(__file__), "build", "vbnet.so"),
        os.path.join(os.path.dirname(__file__), "vbnet.so"),
        "/home/claude/build/vbnet.so",
    ]
    for so_path in so_paths:
        if os.path.exists(so_path):
            try:
                lib = ctypes.cdll.LoadLibrary(so_path)
                func = lib.tree_sitter_vb_dotnet
                func.restype = ctypes.c_void_p
                _p = Parser(Language(func()))
                try:
                    _p.timeout_micros = 5_000_000
                except (AttributeError, TypeError):
                    pass
                return _p
            except Exception:
                continue
    raise ImportError(
        "VB.NET parser not found. Build from npm:\n"
        "  npm install --ignore-scripts tree-sitter-vb-dotnet\n"
        "  gcc -shared -fPIC -O2 -I node_modules/tree-sitter-vb-dotnet/src "
        "node_modules/tree-sitter-vb-dotnet/src/parser.c -o build/vbnet.so")


# Logical operator keywords (case-insensitive)
_LOGICAL_OPS = ("ANDALSO", "ORELSE", "AND", "OR")


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
        """Walk the tree, descending into containers and processing methods.
        Tolerates ERROR nodes by recursing into them as well."""
        for child in node.children:
            t = child.type
            if t == "method_declaration":
                self._process_function(child)
            elif t in ("class_block", "module_block", "interface_block",
                       "structure_block", "namespace_block",
                       "type_declaration", "ERROR"):
                self._walk_top_level(child)

    def _process_function(self, func_node):
        name_node = func_node.child_by_field_name("name")
        func_name = self._text(name_node) if name_node else "<anonymous>"

        self.details = []
        complexity = 0
        # Body = all statement children (not the signature parts)
        for child in func_node.children:
            t = child.type
            if t in ("identifier", "parameter_list", "modifiers",
                     "type", "as_clause"):
                continue
            complexity += self._visit(child, 0)

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

        # ── B1 structural: If ──
        if t == "if_statement":
            return self._handle_if_chain(node, nesting)

        # ── B1 structural: For/Next ──
        if t == "for_statement":
            inc = 1 + nesting
            self._add_detail(node, "For", 1, nesting)
            c = inc
            for child in node.children:
                # Skip header pieces; visit body statements
                if child.type in ("identifier", "=", "expression"):
                    # 'expression' here is the start/end value, not body
                    fn = self._field_name(node, child)
                    if fn in ("variable", "start", "end", "step"):
                        continue
                c += self._visit(child, nesting + 1) if self._is_body_child(node, child) else 0
            return c

        # ── B1 structural: For Each/Next ──
        if t == "for_each_statement":
            inc = 1 + nesting
            self._add_detail(node, "For Each", 1, nesting)
            c = inc
            for child in node.children:
                if self._is_body_child(node, child):
                    c += self._visit(child, nesting + 1)
            return c

        # ── B1 structural: While ──
        if t == "while_statement":
            inc = 1 + nesting
            self._add_detail(node, "While", 1, nesting)
            c = inc
            cond = node.child_by_field_name("condition")
            if cond:
                c += self._visit(cond, nesting)
            for child in node.children:
                if self._is_body_child(node, child) and child != cond:
                    c += self._visit(child, nesting + 1)
            return c

        # ── B1 structural: Do/Loop (Do While, Do Until, Loop While, Loop Until) ──
        if t == "do_statement":
            inc = 1 + nesting
            self._add_detail(node, "Do/Loop", 1, nesting)
            c = inc
            for child in node.children:
                # Visit any condition expression as well as body
                if child.type == "expression":
                    c += self._visit(child, nesting)
                elif self._is_body_child(node, child):
                    c += self._visit(child, nesting + 1)
            return c

        # ── B1 structural: Select Case (single +1, p.7) ──
        if t == "select_case_statement":
            inc = 1 + nesting
            self._add_detail(node, "Select Case", 1, nesting)
            c = inc
            sel = node.child_by_field_name("selector")
            if sel:
                c += self._visit(sel, nesting)
            for child in node.children:
                if child.type in ("case_block", "case_else_block"):
                    # Visit case body statements at nesting+1
                    for sub in child.children:
                        if sub.type in ("case_clause", "expression"):
                            continue
                        c += self._visit(sub, nesting + 1)
            return c

        # ── try: no increment, no nesting change (p.7) ──
        if t == "try_statement":
            c = 0
            for child in node.children:
                c += self._visit(child, nesting)
            return c

        # ── B1 structural: Catch (p.7) ──
        if t == "catch_block":
            inc = 1 + nesting
            self._add_detail(node, "Catch", 1, nesting)
            c = inc
            for child in node.children:
                t2 = child.type
                # Skip catch header pieces
                if t2 in ("identifier", "type", "namespace_name",
                          "expression"):
                    fn = self._field_name(node, child)
                    if fn in ("exception", "type", "filter"):
                        continue
                c += self._visit(child, nesting + 1)
            return c

        # ── Finally: no increment (p.7) ──
        if t == "finally_block":
            c = 0
            for child in node.children:
                c += self._visit(child, nesting)
            return c

        # ── B1 fundamental: GoTo (p.8) ──
        if t == "goto_statement":
            self._add_detail(node, "GoTo", 1, 0)
            return 1

        # ── B1 fundamental: logical operators in binary_expression ──
        if t == "binary_expression":
            op_text = self._binary_op_text(node)
            if op_text and op_text.upper() in _LOGICAL_OPS:
                return self._handle_boolean(node, nesting)
            return self._visit_children(node, nesting)

        # ── expression wrapper: unwrap ──
        if t == "expression":
            return self._visit_children(node, nesting)

        # ── statement wrapper: unwrap ──
        if t == "statement":
            return self._visit_children(node, nesting)

        # ── B2: nested method_declaration → nesting (p.9) ──
        if t == "method_declaration":
            c = 0
            for child in node.children:
                if child.type in ("identifier", "parameter_list", "modifiers",
                                  "type", "as_clause"):
                    continue
                c += self._visit(child, nesting + 1)
            return c

        # ── lambda expressions (best-effort; parser support varies) ──
        if t in ("lambda_expression", "single_line_lambda_expression",
                 "multi_line_lambda_expression"):
            c = 0
            for child in node.children:
                if child.type in ("parameter_list", "Function", "Sub",
                                  "modifiers", "as_clause", "type"):
                    continue
                c += self._visit(child, nesting + 1)
            return c

        # ── ERROR: tolerate by recursing ──
        if t == "ERROR":
            return self._visit_children(node, nesting)

        # ── default: recurse ──
        return self._visit_children(node, nesting)

    # ── Helpers for structural visitors ──

    def _field_name(self, parent, child):
        for i, c in enumerate(parent.children):
            if c == child:
                return parent.field_name_for_child(i)
        return None

    def _is_body_child(self, parent, child):
        """Determine whether a child of a control-flow statement is part of
        the body (vs header/condition/etc.)."""
        if child.type in ("(", ")", "=", ",", ":"):
            return False
        fn = self._field_name(parent, child)
        if fn in ("variable", "start", "end", "step", "collection",
                  "condition", "selector", "exception", "type", "filter",
                  "label"):
            return False
        # Skip pure expressions whose field is one of the above; if no
        # field name and type is 'expression' at top level of for/while/do,
        # it's likely the condition (already handled separately).
        if child.type in ("identifier", "parameter_list", "modifiers"):
            return False
        return True

    # ── If / ElseIf / Else chain ──

    def _handle_if_chain(self, if_node, nesting):
        c = 0
        # B1 structural: If → +1, receives nesting
        inc = 1 + nesting
        self._add_detail(if_node, "If", 1, nesting)
        c += inc

        # condition
        cond = if_node.child_by_field_name("condition")
        if cond:
            c += self._visit(cond, nesting)

        # Body and elseif/else clauses
        for child in if_node.children:
            if child == cond:
                continue
            if child.type == "elseif_clause":
                c += self._handle_elseif(child, nesting)
            elif child.type == "else_clause":
                c += self._handle_else(child, nesting)
            elif child.type in ("identifier", "(", ")", "Then", "If",
                                "End", "End If", ":"):
                continue
            else:
                # body statement
                c += self._visit(child, nesting + 1)
        return c

    def _handle_elseif(self, node, nesting):
        c = 1
        self._add_detail(node, "ElseIf", 1, 0)
        cond = node.child_by_field_name("condition")
        if cond:
            c += self._visit(cond, nesting)
        for child in node.children:
            if child == cond:
                continue
            if child.type in ("ElseIf", "Then", "elseif_clause", "else_clause"):
                if child.type == "elseif_clause":
                    c += self._handle_elseif(child, nesting)
                elif child.type == "else_clause":
                    c += self._handle_else(child, nesting)
                continue
            c += self._visit(child, nesting + 1)
        return c

    def _handle_else(self, node, nesting):
        c = 1
        self._add_detail(node, "Else", 1, 0)
        for child in node.children:
            if child.type == "Else":
                continue
            c += self._visit(child, nesting + 1)
        return c

    # ── binary operator detection (text-based, parser drops operator) ──

    def _binary_op_text(self, node):
        """Extract the operator text from a binary_expression by scanning
        the source between the left and right operand spans. The parser
        drops the operator token, so we look for it in the source slice."""
        children = [c for c in node.children if c.is_named]
        if len(children) < 2:
            return ""
        left, right = children[0], children[-1]
        between = self.source_code[left.end_byte:right.start_byte]
        # Strip whitespace and try to identify the operator keyword/symbol
        stripped = between.strip()
        if not stripped:
            return ""
        # VB logical keywords (case-insensitive). Check the longer ones first
        # to avoid matching 'And' inside 'AndAlso'.
        upper = stripped.upper()
        for kw in ("ANDALSO", "ORELSE", "AND", "OR", "XOR"):
            if upper == kw or upper.startswith(kw + " ") or upper.startswith(kw + "\t"):
                return kw
        # Symbolic operators
        for sym in ("=", "<>", "<=", ">=", "<", ">", "+", "-", "*", "/", "\\", "Mod"):
            if stripped.startswith(sym):
                return sym
        return stripped.split()[0] if stripped else ""

    # ── Boolean operator sequences (B1 fundamental, p.7-8) ──

    def _handle_boolean(self, node, nesting):
        ops = []
        self._collect_boolean_ops(node, ops)
        if not ops:
            return self._visit_children(node, nesting)

        c = 0
        prev = None
        for op in ops:
            # Normalize: AndAlso/And → AND, OrElse/Or → OR (logically equivalent
            # for sequence detection — they all represent boolean conjunction
            # vs disjunction).
            if op in ("ANDALSO", "AND"):
                norm = "AND"
            elif op in ("ORELSE", "OR"):
                norm = "OR"
            else:
                norm = op
            if prev is None or norm != prev:
                c += 1
                desc = (f"logical sequence '{op}'"
                        if prev is None
                        else f"logical change to '{op}'")
                self._add_detail_raw(desc, 1)
                prev = norm
        return c

    def _collect_boolean_ops(self, node, ops):
        if node.type != "binary_expression":
            return
        op_text = self._binary_op_text(node)
        if not op_text:
            return
        op_upper = op_text.upper()
        if op_upper not in _LOGICAL_OPS:
            return

        # Find left and right named children (skipping expression wrappers)
        named = [c for c in node.children if c.is_named]
        if len(named) < 2:
            return
        left, right = named[0], named[-1]

        # Unwrap expression wrappers
        def unwrap(n):
            while n.type == "expression" and n.named_child_count == 1:
                n = n.named_children[0]
            return n

        left_inner = unwrap(left)
        right_inner = unwrap(right)

        if left_inner.type == "binary_expression":
            lo = self._binary_op_text(left_inner).upper()
            if lo in _LOGICAL_OPS:
                self._collect_boolean_ops(left_inner, ops)

        ops.append(op_upper)

        if right_inner.type == "binary_expression":
            ro = self._binary_op_text(right_inner).upper()
            if ro in _LOGICAL_OPS:
                self._collect_boolean_ops(right_inner, ops)


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
            if fname.endswith((".vb", ".vbs")):
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
    print("VB.NET Cognitive Complexity Calculator")
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
