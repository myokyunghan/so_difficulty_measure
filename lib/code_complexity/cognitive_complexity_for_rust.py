"""
Rust Cognitive Complexity Calculator
======================================
Based on:
  - G. Ann Campbell. 2018. "Cognitive Complexity: An Overview and Evaluation."
    TechDebt '18, ICSE, Gothenburg, Sweden.
    https://doi.org/10.1145/3194164.3194186
  - SonarSource. "Cognitive Complexity - a new way of measuring understandability."
    Version 1.7, 29 August 2023.
    https://www.sonarsource.com/docs/CognitiveComplexity.pdf

═══════════════════════════════════════════════════════════════════
Specification (Appendix B, adapted for Rust)
═══════════════════════════════════════════════════════════════════

B1. Increments (+1 each)
────────────────────────
  Structural (B):  +1, receives nesting penalty, increases nesting level
    - if                                  → Rust: if_expression
    - if let                              → Rust: if_expression with let_condition
    - match (switch equivalent)           → Rust: match_expression (single +1, p.7)
    - for                                 → Rust: for_expression
    - while                               → Rust: while_expression
    - while let                           → Rust: while_expression with let_condition
    - loop                                → Rust: loop_expression (infinite loop)

  Hybrid (D):  +1, NO nesting penalty, but increases nesting level
    - else if                             → Rust: if_expression as alternative of if_expression
    - else                                → Rust: block as alternative of if_expression

  Fundamental (C):  +1, NO nesting penalty, does NOT increase nesting level
    - break 'LABEL, continue 'LABEL       → Rust: break_expression/continue_expression with label
    - sequences of binary logical ops     → Rust: binary_expression with && / ||
    - each method in a recursion cycle    → Not implemented

  Not applicable in Rust:
    - try / catch                         → Rust uses Result<T, E> + ? operator
    - goto                                → Rust has no goto
    - ternary operator                    → Rust uses if as expression
    - do-while                            → Rust has loop + break

  Ignored (p.6 "Ignore shorthand" / early return, p.8):
    - ? operator (try_expression)         → No increment (it's an early-return shortcut)

B2. Nesting level (these structures increase nesting for their children)
────────────────────────────────────────────────────────────────────────
    - if, else if, else
    - match
    - for, while, loop
    - nested functions: closure_expression, nested function_item

B3. Nesting increments (these structures RECEIVE +nesting_level penalty)
────────────────────────────────────────────────────────────────────────
    - if                (NOT else if, NOT else)
    - match
    - for, while, loop

═══════════════════════════════════════════════════════════════════
Rust-specific notes
═══════════════════════════════════════════════════════════════════

  - Rust has 3 distinct loop forms, all treated as structural +1:
      • for x in iter { ... }   → for_expression
      • while cond { ... }      → while_expression
      • loop { ... }            → loop_expression (Rust's infinite loop)
    Note: Rust has no `do-while`. The idiom is `loop { ...; if cond { break; } }`.

  - if and match are EXPRESSIONS in Rust (can return values):
      `let x = if a { 1 } else { 0 };`
      `let y = match x { 1 => "one", _ => "other" };`
    They are still treated as structural increments per the spec.

  - if let / while let: pattern matching variants. Treated as regular if/while.
    Tree-sitter wraps the condition in a `let_condition` node.

  - match: single +1 for the entire match (per p.7 "Switches"). No additional
    increment per arm. Match arm guards (`Some(n) if n > 0 =>`) do NOT add
    increments per the spec — they're part of the match's pattern matching.

  - break/continue with label: Rust uses `'label` syntax (e.g. `'outer: loop`).
    Plain break/continue have no increment; labeled forms = +1 fundamental (p.8).

  - closures: `|x| expr`, `move |x| { ... }`. No structural increment,
    increases nesting level (p.9).

  - The `?` operator (try_expression): treated as ignored shorthand, similar
    to the spirit of early return (p.8). It's a control-flow simplification,
    not an additional break in linear flow worth penalizing.

  - Rust has no try/catch. Error handling uses Result<T, E> and ?. There is
    a nightly `try { }` block (try_block node) which we ignore for complexity.

  - impl blocks, trait blocks, mod blocks: walked recursively to find functions.

═══════════════════════════════════════════════════════════════════
Extension: Bare code fallback
═══════════════════════════════════════════════════════════════════

  For snippets without function definitions:
    Wraps in `fn __top__() { ... }` and re-parses.

Dependencies: pip install tree-sitter tree-sitter-rust
"""
import os
import re
import sys
import json
from tree_sitter import Language, Parser


def create_parser():
    try:
        from tree_sitter_language_pack import get_parser
        return get_parser("rust")
    except Exception:
        pass
    try:
        import tree_sitter_rust as _mod
        return Parser(Language(_mod.language()))
    except ImportError:
        raise ImportError(
            "Install one of:\n"
            "  pip install tree-sitter-language-pack\n"
            "  pip install tree-sitter-rust")


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
            wrapped = "fn __top__() {\n" + self.source_code + "\n}"
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
            if t == "function_item":
                self._process_function(child)
            elif t in ("impl_item", "trait_item"):
                self._walk_impl_or_trait(child)
            elif t == "mod_item":
                # Modules can contain functions/impls
                body = child.child_by_field_name("body")
                if body:
                    self._walk_top_level(body)

    def _walk_impl_or_trait(self, node):
        body = node.child_by_field_name("body")
        if body is None:
            return
        # Build context name (Type or Trait)
        ctx_name = ""
        type_node = node.child_by_field_name("type")
        if type_node:
            ctx_name = self._text(type_node)
        else:
            name_node = node.child_by_field_name("name")
            if name_node:
                ctx_name = self._text(name_node)

        for child in body.children:
            if child.type == "function_item":
                self._process_function(child, ctx_name)

    def _process_function(self, func_node, ctx_name=""):
        name_node = func_node.child_by_field_name("name")
        func_name = self._text(name_node) if name_node else "<anonymous>"
        if ctx_name:
            func_name = f"{ctx_name}::{func_name}"

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

        # ── B1 structural: if (and if let) ──
        if t == "if_expression":
            return self._handle_if_chain(node, nesting, is_else_if=False)

        # ── B1 structural: for ──
        if t == "for_expression":
            inc = 1 + nesting
            self._add_detail(node, "for", 1, nesting)
            c = inc
            value = node.child_by_field_name("value")
            if value:
                c += self._visit(value, nesting)
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── B1 structural: while (and while let) ──
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

        # ── B1 structural: loop (Rust's infinite loop) ──
        if t == "loop_expression":
            inc = 1 + nesting
            self._add_detail(node, "loop", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── B1 structural: match (single +1 for entire match, p.7) ──
        if t == "match_expression":
            inc = 1 + nesting
            self._add_detail(node, "match", 1, nesting)
            c = inc
            # Visit the value being matched (may contain calls/logic)
            value = node.child_by_field_name("value")
            if value:
                c += self._visit(value, nesting)
            # Visit match_block: each match_arm
            body = node.child_by_field_name("body")
            if body:
                for child in body.children:
                    if child.type == "match_arm":
                        # No additional increment per arm.
                        # Match arm guards are part of pattern matching, no +1.
                        # Visit only the arm value (RHS), not the pattern.
                        for sub in child.children:
                            if sub.type not in (
                                "match_pattern", "=>", ",",
                                "tuple_struct_pattern", "tuple_pattern",
                                "struct_pattern", "or_pattern",
                                "range_pattern", "captured_pattern",
                                "reference_pattern", "remaining_field_pattern",
                                "literal_pattern", "identifier", "_",
                                "scoped_identifier",
                            ):
                                c += self._visit(sub, nesting + 1)
            return c

        # ── B1 fundamental: logical operators (p.7-8) ──
        if t == "binary_expression":
            op_text = ""
            for child in node.children:
                if child.type in ("&&", "||"):
                    op_text = child.type
                    break
            if op_text in ("&&", "||"):
                return self._handle_boolean(node, nesting)
            return self._visit_children(node, nesting)

        # ── B1 fundamental: break 'LABEL / continue 'LABEL (p.8) ──
        if t == "break_expression":
            for child in node.children:
                if child.type == "label":
                    self._add_detail(node, "break to label", 1, 0)
                    return 1
            # Plain break: no increment. But may have a value to visit.
            return self._visit_children(node, nesting)

        if t == "continue_expression":
            for child in node.children:
                if child.type == "label":
                    self._add_detail(node, "continue to label", 1, 0)
                    return 1
            return 0

        # ── ? operator (try_expression): ignored (p.6/p.8) ──
        if t == "try_expression":
            # Don't increment, but visit children (the inner expression
            # may contain method calls that need to be examined)
            return self._visit_children(node, nesting)

        # ── try_block (nightly): ignored ──
        if t == "try_block":
            for child in node.children:
                if child.type == "block":
                    return self._visit_children(child, nesting)
            return 0

        # ── B2: closure → no increment, increases nesting (p.9) ──
        if t == "closure_expression":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                # body may be a block { ... } or a single expression
                if body.type == "block":
                    c += self._visit_children(body, nesting + 1)
                else:
                    c += self._visit(body, nesting + 1)
            return c

        # ── B2: nested function_item → no increment, increases nesting (p.9) ──
        if t == "function_item":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
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
            # B1 hybrid: else if → +1, NO nesting penalty, increases nesting
            c += 1
            self._add_detail(if_node, "else if", 1, 0)
        else:
            # B1 structural: if → +1, receives nesting
            inc = 1 + nesting
            self._add_detail(if_node, "if", 1, nesting)
            c += inc

        # condition (may include let_condition for if let, or logical exprs)
        cond = if_node.child_by_field_name("condition")
        if cond:
            c += self._visit(cond, nesting)

        # consequence (then block)
        consequence = if_node.child_by_field_name("consequence")
        if consequence:
            c += self._visit_children(consequence, nesting + 1)

        # alternative: else_clause containing if_expression (else if) or block (else)
        alt = if_node.child_by_field_name("alternative")
        if alt and alt.type == "else_clause":
            for child in alt.children:
                if child.type == "if_expression":
                    c += self._handle_if_chain(child, nesting, is_else_if=True)
                elif child.type == "block":
                    c += 1
                    self._add_detail(child, "else", 1, 0)
                    c += self._visit_children(child, nesting + 1)

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
        # In Rust tree-sitter, the operator is a child node (not a field)
        op_text = ""
        left = None
        right = None
        for i, child in enumerate(node.children):
            if child.type in ("&&", "||"):
                op_text = child.type
            elif left is None:
                left = child
            else:
                right = child
        if op_text not in ("&&", "||"):
            return

        if left and left.type == "binary_expression":
            lo = ""
            for child in left.children:
                if child.type in ("&&", "||"):
                    lo = child.type
                    break
            if lo in ("&&", "||"):
                self._collect_boolean_ops(left, ops)

        ops.append(op_text)

        if right and right.type == "binary_expression":
            ro = ""
            for child in right.children:
                if child.type in ("&&", "||"):
                    ro = child.type
                    break
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
    print("Rust Cognitive Complexity Calculator")
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