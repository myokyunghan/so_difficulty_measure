"""
MATLAB Cognitive Complexity Calculator
========================================
Based on:
  - G. Ann Campbell. 2018. "Cognitive Complexity: An Overview and Evaluation."
    TechDebt '18, ICSE, Gothenburg, Sweden.
    https://doi.org/10.1145/3194164.3194186
  - SonarSource. "Cognitive Complexity - a new way of measuring understandability."
    Version 1.7, 29 August 2023.
    https://www.sonarsource.com/docs/CognitiveComplexity.pdf

═══════════════════════════════════════════════════════════════════
Specification (Appendix B, adapted for MATLAB)
═══════════════════════════════════════════════════════════════════

B1. Increments (+1 each)
────────────────────────
  Structural (B):  +1, receives nesting penalty, increases nesting level
    - if                                  → MATLAB: if_statement
    - switch                              → MATLAB: switch_statement (single +1, p.7)
    - for                                 → MATLAB: for_statement
    - while                               → MATLAB: while_statement
    - catch                               → MATLAB: catch_clause (single +1, p.7)

  Hybrid (D):  +1, NO nesting penalty, but increases nesting level
    - elseif                              → MATLAB: elseif_clause
    - else                                → MATLAB: else_clause

  Fundamental (C):  +1, NO nesting penalty, does NOT increase nesting level
    - sequences of binary logical ops     → MATLAB: boolean_operator (&& / ||)
                                                     and binary_operator (& / |)
    - each method in a recursion cycle    → Not implemented

  Not applicable in MATLAB:
    - goto                                → MATLAB has no goto
    - labeled break/continue              → MATLAB has no labeled break/continue
    - ternary operator                    → MATLAB has no ternary (uses if-else)
    - do-while                            → MATLAB has no do-while

B2. Nesting level (these structures increase nesting for their children)
────────────────────────────────────────────────────────────────────────
    - if, elseif, else
    - switch
    - for, while
    - catch
    - nested functions: lambda (anonymous func @(x)), nested function_definition

B3. Nesting increments (these structures RECEIVE +nesting_level penalty)
────────────────────────────────────────────────────────────────────────
    - if                (NOT elseif, NOT else)
    - switch
    - for, while
    - catch

═══════════════════════════════════════════════════════════════════
MATLAB-specific notes
═══════════════════════════════════════════════════════════════════

  - MATLAB has TWO classes of logical operators:
      • Short-circuit (`&&`, `||`)  → boolean_operator nodes
      • Element-wise (`&`, `|`)     → binary_operator nodes (used in conditions
                                       too, just less common)
    Both forms count for logical operator sequences per the spec.
    The spec says "binary boolean operators" so both qualify.

  - if/elseif/else: MATLAB uses one-word `elseif` (not `else if`).
    Tree-sitter parses elseif_clause and else_clause as children of
    if_statement.

  - switch/case/otherwise: MATLAB uses `otherwise` instead of `default`.
    Single +1 for entire switch (per p.7 "Switches"), no per-case increment.

  - try/catch: MATLAB has try/catch but no `finally`. catch_clause = +1
    structural per p.7.

  - Anonymous functions: `@(x) expr`. Parsed as `lambda` node. Treated as
    nested function (no structural increment, increases nesting per p.9).

  - MATLAB scripts: A .m file may be a script (no function definition) or
    a function file. The bare-code fallback handles scripts.

  - classdef: MATLAB classes use `classdef` with `methods` blocks containing
    `function_definition` nodes. The walker descends into methods blocks.

  - Function file with no `end`: MATLAB allows function files where the
    function definition has no closing `end` (legacy syntax). The parser
    handles this; we extract body via `block` child or direct children.

  - Multiple top-level functions in one file: MATLAB allows multiple
    function definitions in the same file. The walker processes each.

═══════════════════════════════════════════════════════════════════
Extension: Bare code fallback
═══════════════════════════════════════════════════════════════════

  If the source has no function_definition, treat the entire script body
  as a top-level pseudo-function. We do this by walking source_file
  directly when no functions are found.

Dependencies: pip install tree-sitter tree-sitter-matlab
"""
import os
import re
import sys
import json
from tree_sitter import Language, Parser


def create_parser():
    try:
        from tree_sitter_language_pack import get_parser
        return get_parser("matlab")
    except Exception:
        pass
    try:
        import tree_sitter_matlab as _mod
        return Parser(Language(_mod.language()))
    except ImportError:
        raise ImportError(
            "Install one of:\n"
            "  pip install tree-sitter-language-pack\n"
            "  pip install tree-sitter-matlab")


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

        # Bare code fallback (script): no function found
        if not self.results:
            self._process_script(self.tree.root_node)

        # If still nothing and tree had errors, try wrapping the source in a
        # function and re-parsing (handles single-statement scripts that the
        # parser misinterprets as malformed function bodies).
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
                        r["function"] = "<script>"
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
            elif t == "class_definition":
                self._walk_class(child)
            elif t == "ERROR":
                # MATLAB nested functions confuse the parser; try recovery
                for sub in child.children:
                    if sub.type == "function_definition":
                        self._process_function(sub)
                    elif sub.type == "class_definition":
                        self._walk_class(sub)

    def _walk_class(self, class_node):
        # classdef has methods blocks containing function_definitions
        for child in class_node.children:
            if child.type == "methods":
                for sub in child.children:
                    if sub.type == "function_definition":
                        self._process_function(sub)
            elif child.type == "class_definition":
                self._walk_class(child)

    def _process_function(self, func_node):
        name_node = func_node.child_by_field_name("name")
        func_name = self._text(name_node) if name_node else "<anonymous>"

        self.details = []
        complexity = 0

        # MATLAB function body: typically a `block` child after the signature.
        # Walk all children except the function keyword/name/args/end.
        for child in func_node.children:
            if child.type in ("function", "function_output", "identifier",
                              "function_arguments", "end", "\n", ","):
                # Skip header parts. Note: 'identifier' here is the function
                # name field; sibling identifiers inside the body would be
                # inside expression nodes, not direct children.
                continue
            complexity += self._visit(child, 0)

        self.results.append({
            "function": func_name,
            "complexity": complexity,
            "start_line": func_node.start_point[0] + 1,
            "end_line": func_node.end_point[0] + 1,
            "details": list(self.details),
        })

    def _process_script(self, root_node):
        """Treat the entire file as a top-level script (no function wrapper)."""
        self.details = []
        complexity = 0
        for child in root_node.children:
            complexity += self._visit(child, 0)

        if complexity > 0 or self.details:
            self.results.append({
                "function": "<script>",
                "complexity": complexity,
                "start_line": root_node.start_point[0] + 1,
                "end_line": root_node.end_point[0] + 1,
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
            return self._handle_if_chain(node, nesting)

        # ── B1 structural: for ──
        if t == "for_statement":
            inc = 1 + nesting
            self._add_detail(node, "for", 1, nesting)
            c = inc
            # Body = block child or other children except keywords
            for child in node.children:
                if child.type in ("for", "iterator", "end", "\n"):
                    continue
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
                if child.type in ("while", "end", "\n") or child == cond:
                    continue
                c += self._visit(child, nesting + 1)
            return c

        # ── B1 structural: switch (single +1, p.7) ──
        if t == "switch_statement":
            inc = 1 + nesting
            self._add_detail(node, "switch", 1, nesting)
            c = inc
            # Visit the switch condition (may contain function calls etc.)
            cond = node.child_by_field_name("condition")
            if cond:
                c += self._visit(cond, nesting)
            # Visit case_clause and otherwise_clause bodies
            # No additional increment per case
            for child in node.children:
                if child.type in ("case_clause", "otherwise_clause"):
                    # Each case has its own block; visit at nesting+1
                    for sub in child.children:
                        if sub.type in ("case", "otherwise", "\n"):
                            continue
                        # Skip the case condition (number/identifier/...)
                        sub_field = self._field_name(child, sub)
                        if sub_field == "condition":
                            continue
                        c += self._visit(sub, nesting + 1)
            return c

        # ── try: no increment, no nesting change (p.7) ──
        if t == "try_statement":
            c = 0
            for child in node.children:
                if child.type in ("try", "end", "\n"):
                    continue
                c += self._visit(child, nesting)
            return c

        # ── B1 structural: catch (p.7) ──
        if t == "catch_clause":
            inc = 1 + nesting
            self._add_detail(node, "catch", 1, nesting)
            c = inc
            # catch [varname] body
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
                if child.type == "\n":
                    continue
                seen_var = True  # any other node = body starts
                c += self._visit(child, nesting + 1)
            return c

        # ── B1 fundamental: short-circuit logical (&&, ||) ──
        if t == "boolean_operator":
            return self._handle_boolean(node, nesting, types=("boolean_operator",),
                                         valid_ops=("&&", "||"))

        # ── B1 fundamental: element-wise logical (&, |) ──
        if t == "binary_operator":
            # Only count if it's a logical operator (& or |)
            op = self._operator_text(node)
            if op in ("&", "|"):
                return self._handle_boolean(node, nesting,
                                             types=("binary_operator",),
                                             valid_ops=("&", "|"))
            return self._visit_children(node, nesting)

        # ── B2: lambda (anonymous function) → nesting (p.9) ──
        if t == "lambda":
            c = 0
            # Visit the expression part (after @(args))
            expr = node.child_by_field_name("expression")
            if expr:
                c += self._visit(expr, nesting + 1)
            else:
                # Fallback: visit non-header children
                for child in node.children:
                    if child.type in ("@", "(", ")", "arguments"):
                        continue
                    c += self._visit(child, nesting + 1)
            return c

        # ── B2: nested function_definition → nesting (p.9) ──
        if t == "function_definition":
            c = 0
            for child in node.children:
                if child.type in ("function", "function_output", "identifier",
                                  "function_arguments", "end", "\n"):
                    continue
                c += self._visit(child, nesting + 1)
            return c

        # ── block: just visit children at same nesting ──
        if t == "block":
            return self._visit_children(node, nesting)

        # ── ERROR node: try to recover by visiting children ──
        if t == "ERROR":
            return self._visit_children(node, nesting)

        # ── Skip pure whitespace/punctuation nodes ──
        if t in ("\n", ",", ";"):
            return 0

        # ── default: recurse ──
        return self._visit_children(node, nesting)

    def _field_name(self, parent, child):
        for i, c in enumerate(parent.children):
            if c == child:
                return parent.field_name_for_child(i)
        return None

    def _operator_text(self, node):
        """Find the operator text inside a binary_operator/boolean_operator node."""
        for child in node.children:
            t = child.type
            if t in ("&&", "||", "&", "|", "+", "-", "*", "/", "<", ">",
                     "==", "~=", "<=", ">=", ".*", "./", ".^", "^"):
                return t
        return ""

    # ── if / elseif / else chain ──

    def _handle_if_chain(self, if_node, nesting):
        c = 0
        # B1 structural: if → +1, receives nesting
        inc = 1 + nesting
        self._add_detail(if_node, "if", 1, nesting)
        c += inc

        # condition (may contain logical operators)
        cond = if_node.child_by_field_name("condition")
        if cond:
            c += self._visit(cond, nesting)

        # Body and elseif/else clauses
        for child in if_node.children:
            if child.type in ("if", "end", "\n"):
                continue
            if child == cond:
                continue
            if child.type == "elseif_clause":
                c += self._handle_elseif(child, nesting)
            elif child.type == "else_clause":
                c += self._handle_else(child, nesting)
            else:
                # body content (block or direct statements)
                c += self._visit(child, nesting + 1)
        return c

    def _handle_elseif(self, node, nesting):
        c = 1
        self._add_detail(node, "elseif", 1, 0)
        cond = node.child_by_field_name("condition")
        if cond:
            c += self._visit(cond, nesting)
        for child in node.children:
            if child.type in ("elseif", "\n") or child == cond:
                continue
            c += self._visit(child, nesting + 1)
        return c

    def _handle_else(self, node, nesting):
        c = 1
        self._add_detail(node, "else", 1, 0)
        for child in node.children:
            if child.type in ("else", "\n"):
                continue
            c += self._visit(child, nesting + 1)
        return c

    # ── Boolean operator sequences (B1 fundamental, p.7-8) ──

    def _handle_boolean(self, node, nesting, types, valid_ops):
        ops = []
        self._collect_boolean_ops(node, ops, types, valid_ops)
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

    def _collect_boolean_ops(self, node, ops, types, valid_ops):
        if node.type not in types:
            return
        op_text = self._operator_text(node)
        if op_text not in valid_ops:
            return

        # Find left and right children (left/right fields)
        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")

        if left and left.type in types:
            lo = self._operator_text(left)
            if lo in valid_ops:
                self._collect_boolean_ops(left, ops, types, valid_ops)

        ops.append(op_text)

        if right and right.type in types:
            ro = self._operator_text(right)
            if ro in valid_ops:
                self._collect_boolean_ops(right, ops, types, valid_ops)


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
            if fname.endswith(".m"):
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
    print("MATLAB Cognitive Complexity Calculator")
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