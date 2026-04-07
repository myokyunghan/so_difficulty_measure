"""
Julia Cognitive Complexity Calculator
=======================================
Based on:
  - G. Ann Campbell. 2018. "Cognitive Complexity: An Overview and Evaluation."
    TechDebt '18, ICSE, Gothenburg, Sweden.
    https://doi.org/10.1145/3194164.3194186
  - SonarSource. "Cognitive Complexity - a new way of measuring understandability."
    Version 1.7, 29 August 2023.
    https://www.sonarsource.com/docs/CognitiveComplexity.pdf

═══════════════════════════════════════════════════════════════════
Specification (Appendix B, adapted for Julia)
═══════════════════════════════════════════════════════════════════

B1. Increments (+1 each)
────────────────────────
  Structural (B):  +1, receives nesting penalty, increases nesting level
    - if                                  → Julia: if_statement
    - for                                 → Julia: for_statement
    - while                               → Julia: while_statement
    - catch                               → Julia: catch_clause (single +1, p.7)
    - ternary operator                    → Julia: ternary_expression (a ? b : c)

  Hybrid (D):  +1, NO nesting penalty, but increases nesting level
    - elseif                              → Julia: elseif_clause
    - else                                → Julia: else_clause

  Fundamental (C):  +1, NO nesting penalty, does NOT increase nesting level
    - sequences of binary logical ops     → Julia: binary_expression with && / ||
    - each method in a recursion cycle    → Not implemented

  Not applicable in Julia:
    - switch / match                      → Julia uses if-elseif chains
    - goto                                → Julia has @goto/@label as macros, rarely used
    - labeled break/continue              → Julia has no labeled break/continue
    - do-while                            → Julia has no do-while

B2. Nesting level (these structures increase nesting for their children)
────────────────────────────────────────────────────────────────────────
    - if, elseif, else, ternary
    - for, while
    - catch
    - nested functions: arrow_function_expression, do_clause,
                        nested function_definition, short-form function

B3. Nesting increments (these structures RECEIVE +nesting_level penalty)
────────────────────────────────────────────────────────────────────────
    - if, ternary       (NOT elseif, NOT else)
    - for, while
    - catch

═══════════════════════════════════════════════════════════════════
Julia-specific notes
═══════════════════════════════════════════════════════════════════

  - Julia has NO switch/case construct. Multi-way branching uses
    if-elseif-elseif-else chains. Therefore there is no "single +1 for
    switch" rule to apply — each branch contributes its own increment.

  - Julia has TWO function definition forms:
      • Long form: `function f(x); ...; end`  → function_definition
      • Short form: `f(x) = expr`             → assignment with call on LHS
    The calculator detects both at the top level.

  - Julia function bodies are NOT a single block node — the function_definition
    contains [function, signature, ...body statements..., end] as direct
    children. The body is everything between signature and the final 'end'.

  - try/catch/finally: try block and finally block are ignored (p.7).
    catch_clause = +1 structural + nesting (single increment).

  - Anonymous functions:
      • `x -> expr`        → arrow_function_expression
      • `(x, y) -> expr`   → arrow_function_expression
      • `do x; ...; end`   → do_clause (block syntax for higher-order calls)
    All increase nesting level (p.9).

  - Comprehensions `[expr for x in xs if cond]` are NOT incremented.
    They are declarative set-builder notation, similar to how the spec
    treats Python comprehensions (no explicit rule, treated as expression).
    The `if_clause` inside a comprehension is part of the comprehension's
    filter and does not trigger structural increment per the spec.

  - Short-circuit logical patterns: `cond && action()` and `cond || action()`
    are common Julia idioms. They produce binary_expression nodes and contribute
    to logical operator sequences per the spec (p.7-8).

  - module/baremodule: walked recursively to find inner functions.
  - struct/mutable struct: walked but typically contains no executable code
    (only field declarations). Inner constructors (function inside struct)
    are picked up.

═══════════════════════════════════════════════════════════════════
Extension: Bare code fallback
═══════════════════════════════════════════════════════════════════

  For snippets without function definitions:
    Wraps in `function __top__()\n ... \nend` and re-parses.

Dependencies: pip install tree-sitter tree-sitter-julia
"""
import os
import re
import sys
import json
from tree_sitter import Language, Parser


def create_parser():
    try:
        from tree_sitter_language_pack import get_parser
        return get_parser("julia")
    except Exception:
        pass
    try:
        import tree_sitter_julia as _mod
        return Parser(Language(_mod.language()))
    except ImportError:
        raise ImportError(
            "Install one of:\n"
            "  pip install tree-sitter-language-pack\n"
            "  pip install tree-sitter-julia")


# Children of function_definition that are NOT body statements
_FUNC_NON_BODY = frozenset(["function", "signature", "end"])


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
            wrapped = "function __top__()\n" + self.source_code + "\nend"
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
        for child in node.children:
            t = child.type
            if t == "function_definition":
                self._process_function(child)
            elif t == "assignment":
                # Short-form function: f(x) = expr
                if self._is_short_function(child):
                    self._process_short_function(child)
            elif t in ("module_definition", "baremodule_definition"):
                self._walk_module(child)
            elif t == "struct_definition":
                self._walk_struct(child)
            elif t == "macro_definition":
                self._process_macro(child)
            elif t == "abstract_definition":
                pass  # No body

    def _walk_module(self, mod_node):
        # Walk children to find inner functions/modules
        for child in mod_node.children:
            t = child.type
            if t == "function_definition":
                self._process_function(child)
            elif t == "assignment":
                if self._is_short_function(child):
                    self._process_short_function(child)
            elif t in ("module_definition", "baremodule_definition"):
                self._walk_module(child)
            elif t == "struct_definition":
                self._walk_struct(child)
            elif t == "macro_definition":
                self._process_macro(child)

    def _walk_struct(self, struct_node):
        # Inner constructors inside struct
        for child in struct_node.children:
            if child.type == "function_definition":
                self._process_function(child)
            elif child.type == "assignment":
                if self._is_short_function(child):
                    self._process_short_function(child)

    def _is_short_function(self, assignment_node):
        """Detect short-form function: f(x) = expr (LHS is a call_expression)."""
        if not assignment_node.children:
            return False
        lhs = assignment_node.children[0]
        return lhs.type == "call_expression"

    def _process_function(self, func_node):
        # Extract function name from signature → call_expression → identifier
        func_name = self._extract_func_name(func_node)
        self.details = []

        # Body = all children except function/signature/end
        complexity = 0
        for child in func_node.children:
            if child.type not in _FUNC_NON_BODY:
                complexity += self._visit(child, 0)

        self.results.append({
            "function": func_name,
            "complexity": complexity,
            "start_line": func_node.start_point[0] + 1,
            "end_line": func_node.end_point[0] + 1,
            "details": list(self.details),
        })

    def _process_short_function(self, assign_node):
        """Process short-form function: f(x) = expr"""
        # LHS: call_expression with the function name
        lhs = assign_node.children[0]
        name_node = None
        for c in lhs.children:
            if c.type == "identifier":
                name_node = c
                break
        func_name = self._text(name_node) if name_node else "<anonymous>"

        self.details = []
        complexity = 0
        # Body = RHS (everything after the operator)
        seen_op = False
        for child in assign_node.children:
            if child.type == "operator":
                seen_op = True
                continue
            if seen_op:
                complexity += self._visit(child, 0)

        self.results.append({
            "function": func_name,
            "complexity": complexity,
            "start_line": assign_node.start_point[0] + 1,
            "end_line": assign_node.end_point[0] + 1,
            "details": list(self.details),
        })

    def _process_macro(self, macro_node):
        """Process macro_definition (similar structure to function_definition)"""
        func_name = "@" + self._extract_func_name(macro_node)
        self.details = []
        complexity = 0
        for child in macro_node.children:
            if child.type not in ("macro", "signature", "end"):
                complexity += self._visit(child, 0)
        self.results.append({
            "function": func_name,
            "complexity": complexity,
            "start_line": macro_node.start_point[0] + 1,
            "end_line": macro_node.end_point[0] + 1,
            "details": list(self.details),
        })

    def _extract_func_name(self, func_node):
        """Extract function name from `function NAME(...)` signature."""
        for child in func_node.children:
            if child.type == "signature":
                for sub in child.children:
                    if sub.type == "call_expression":
                        for grand in sub.children:
                            if grand.type == "identifier":
                                return self._text(grand)
                    elif sub.type == "identifier":
                        return self._text(sub)
        return "<anonymous>"

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

        # ── B1 structural: for ──
        if t == "for_statement":
            inc = 1 + nesting
            self._add_detail(node, "for", 1, nesting)
            c = inc
            # Body = children except for/for_binding/end/comma
            for child in node.children:
                if child.type not in ("for", "for_binding", "end", ","):
                    c += self._visit(child, nesting + 1)
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
                if child.type not in ("while", "end") and child != cond:
                    c += self._visit(child, nesting + 1)
            return c

        # ── B1 structural: ternary (a ? b : c) ──
        if t == "ternary_expression":
            inc = 1 + nesting
            self._add_detail(node, "ternary", 1, nesting)
            c = inc
            # Visit children — first is condition, then ?, then consequence,
            # then :, then alternative
            children = list(node.children)
            phase = 0  # 0=cond, 1=cons, 2=alt
            for child in children:
                if child.type == "?":
                    phase = 1
                    continue
                if child.type == ":":
                    phase = 2
                    continue
                if phase == 0:
                    c += self._visit(child, nesting)
                else:
                    c += self._visit(child, nesting + 1)
            return c

        # ── try: no increment (p.7) ──
        if t == "try_statement":
            c = 0
            for child in node.children:
                if child.type not in ("try", "end"):
                    c += self._visit(child, nesting)
            return c

        # ── B1 structural: catch (p.7) ──
        if t == "catch_clause":
            inc = 1 + nesting
            self._add_detail(node, "catch", 1, nesting)
            c = inc
            # Body = children except catch keyword and exception identifier
            seen_catch = False
            seen_var = False
            for child in node.children:
                if child.type == "catch":
                    seen_catch = True
                    continue
                if seen_catch and not seen_var and child.type == "identifier":
                    # exception variable name
                    seen_var = True
                    continue
                seen_var = True  # any other node = body starts
                c += self._visit(child, nesting + 1)
            return c

        # ── finally: no increment (p.7) ──
        if t == "finally_clause":
            c = 0
            for child in node.children:
                if child.type != "finally":
                    c += self._visit(child, nesting)
            return c

        # ── B1 fundamental: logical operators (p.7-8) ──
        if t == "binary_expression":
            op_text = self._binary_op_text(node)
            if op_text in ("&&", "||"):
                return self._handle_boolean(node, nesting)
            return self._visit_children(node, nesting)

        # ── B2: arrow function → no increment, increases nesting (p.9) ──
        if t == "arrow_function_expression":
            c = 0
            seen_arrow = False
            for child in node.children:
                if child.type == "->":
                    seen_arrow = True
                    continue
                if seen_arrow:
                    c += self._visit(child, nesting + 1)
            return c

        # ── B2: do_clause (do x; ...; end) → nesting (p.9) ──
        if t == "do_clause":
            c = 0
            seen_args = False
            for child in node.children:
                if child.type == "do":
                    continue
                if child.type == "argument_list":
                    seen_args = True
                    continue
                if child.type == "end":
                    continue
                # body statements
                c += self._visit(child, nesting + 1)
            return c

        # ── B2: nested function_definition → nesting (p.9) ──
        if t == "function_definition":
            c = 0
            for child in node.children:
                if child.type not in _FUNC_NON_BODY:
                    c += self._visit(child, nesting + 1)
            return c

        # ── B2: nested short-form function (assignment with call LHS) ──
        if t == "assignment" and self._is_short_function(node):
            c = 0
            seen_op = False
            for child in node.children:
                if child.type == "operator":
                    seen_op = True
                    continue
                if seen_op:
                    c += self._visit(child, nesting + 1)
            return c

        # ── compound_statement (begin ... end) — unwrap, no increment ──
        if t == "compound_statement":
            c = 0
            for child in node.children:
                if child.type not in ("begin", "end"):
                    c += self._visit(child, nesting)
            return c

        # ── let_statement: no increment, just visit body ──
        if t == "let_statement":
            c = 0
            for child in node.children:
                if child.type not in ("let", "let_binding", "end", ","):
                    c += self._visit(child, nesting)
            return c

        # ── Comprehensions: not in spec, ignore ──
        # Filter clauses (if_clause inside comprehension) don't add increments.
        if t in ("comprehension_expression", "generator_expression"):
            # Visit only the result expression, not the for_clause/if_clause
            return 0

        # ── parenthesized_expression: unwrap ──
        if t == "parenthesized_expression":
            return self._visit_children(node, nesting)

        # ── elseif_clause / else_clause: handled by _handle_if_chain ──
        if t in ("elseif_clause", "else_clause"):
            return 0

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

        # Body and elseif/else clauses
        # children: if, condition, ...body..., elseif_clause?, else_clause?, end
        for child in if_node.children:
            if child.type in ("if", "end"):
                continue
            if child == cond:
                continue
            if child.type == "elseif_clause":
                c += self._handle_elseif(child, nesting)
            elif child.type == "else_clause":
                c += self._handle_else(child, nesting)
            else:
                # body statement
                c += self._visit(child, nesting + 1)
        return c

    def _handle_elseif(self, node, nesting):
        c = 1
        self._add_detail(node, "elseif", 1, 0)
        cond = node.child_by_field_name("condition")
        if cond:
            c += self._visit(cond, nesting)
        for child in node.children:
            if child.type in ("elseif", "elseif_clause", "else_clause"):
                if child.type == "elseif_clause":
                    c += self._handle_elseif(child, nesting)
                elif child.type == "else_clause":
                    c += self._handle_else(child, nesting)
                continue
            if child == cond:
                continue
            if child.type == "elseif":
                continue
            c += self._visit(child, nesting + 1)
        return c

    def _handle_else(self, node, nesting):
        c = 1
        self._add_detail(node, "else", 1, 0)
        for child in node.children:
            if child.type == "else":
                continue
            c += self._visit(child, nesting + 1)
        return c

    # ── binary operator helper ──

    def _binary_op_text(self, node):
        """Extract operator text from a binary_expression."""
        for child in node.children:
            if child.type == "operator":
                return self._text(child)
        return ""

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
                desc = (f"logical sequence '{op}'"
                        if prev is None
                        else f"logical change to '{op}'")
                self._add_detail_raw(desc, 1)
                prev = op
        return c

    def _collect_boolean_ops(self, node, ops):
        if node.type != "binary_expression":
            return
        op_text = self._binary_op_text(node)
        if op_text not in ("&&", "||"):
            return

        # Find left and right children (not the operator)
        children = [c for c in node.children if c.type != "operator"]
        if len(children) < 2:
            return
        left, right = children[0], children[-1]

        if left.type == "binary_expression":
            lo = self._binary_op_text(left)
            if lo in ("&&", "||"):
                self._collect_boolean_ops(left, ops)

        ops.append(op_text)

        if right.type == "binary_expression":
            ro = self._binary_op_text(right)
            if ro in ("&&", "||"):
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
            if fname.endswith(".jl"):
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
    print("Julia Cognitive Complexity Calculator")
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