"""
Ruby Cognitive Complexity Calculator
======================================
Based on:
  - G. Ann Campbell. 2018. "Cognitive Complexity: An Overview and Evaluation."
    TechDebt '18, ICSE, Gothenburg, Sweden.
    https://doi.org/10.1145/3194164.3194186
  - SonarSource. "Cognitive Complexity - a new way of measuring understandability."
    Version 1.7, 29 August 2023.
    https://www.sonarsource.com/docs/CognitiveComplexity.pdf

═══════════════════════════════════════════════════════════════════
Specification (Appendix B, adapted for Ruby)
═══════════════════════════════════════════════════════════════════

B1. Increments (+1 each)
────────────────────────
  Structural (B):  +1, receives nesting penalty, increases nesting level
    - if                                  → Ruby: if
    - unless                              → Ruby: unless (treated like if)
    - if/unless modifier (postfix)        → Ruby: if_modifier, unless_modifier
    - case/when (switch equivalent)       → Ruby: case (single +1, p.7)
    - for                                 → Ruby: for
    - while, until                        → Ruby: while, until
    - rescue (catch equivalent)           → Ruby: rescue clause inside begin (single +1, p.7)
    - ternary operator                    → Ruby: conditional

  Hybrid (D):  +1, NO nesting penalty, but increases nesting level
    - elsif                               → Ruby: elsif as alternative of if
    - else                                → Ruby: else as alternative of if/unless

  Fundamental (C):  +1, NO nesting penalty, does NOT increase nesting level
    - sequences of binary logical ops     → Ruby: binary with && / || / and / or
    - each method in a recursion cycle    → Not implemented

  Not applicable in Ruby:
    - goto                                → Ruby has no goto
    - break LABEL, continue LABEL         → Ruby has no labeled break/continue

  Ignored (p.6 "Ignore shorthand"):
    - safe navigation (&.)                → No increment

B2. Nesting level
────────────────────────────────────────────────────────────────────────
    - if, unless, elsif, else, ternary, if/unless modifier
    - case
    - for, while, until
    - rescue
    - nested methods/blocks: do_block, brace block, lambda, nested method

B3. Nesting increments (receive +nesting_level penalty)
────────────────────────────────────────────────────────────────────────
    - if, unless, ternary       (NOT elsif, NOT else)
    - case
    - for, while, until
    - rescue

═══════════════════════════════════════════════════════════════════
Ruby-specific notes
═══════════════════════════════════════════════════════════════════

  - Ruby has many ways to express conditionals/loops:
      if/unless (statement and modifier forms), while/until,
      case/when, ternary (?:), and many block-taking methods (each, map).
  - `unless` is treated like `if` (it's just `if` with negated condition).
  - `until` is treated like `while`.
  - Postfix modifiers (`x if cond`, `x unless cond`) are full structural
    increments per the spec — they break linear flow just like prefix forms.
  - case/when: entire case + all when clauses = single structural +1 (p.7).
  - begin/rescue/ensure: begin and ensure are ignored (like try/finally,
    p.7). Each rescue clause = +1 structural + nesting penalty.
  - Ruby's `and`/`or` are lower-precedence aliases for `&&`/`||`. Both
    forms count for logical operator sequences (normalized to `&&`/`||`).
  - Blocks (do...end and { }), lambdas (-> { }), and Proc.new/proc { }
    all act as nested methods → no structural increment, increases nesting.
    This includes blocks passed to .each, .map, .select, etc.
  - Ruby has no goto, no labeled break/continue, no try/catch keyword.

═══════════════════════════════════════════════════════════════════
Extension: Bare code fallback
═══════════════════════════════════════════════════════════════════

  For snippets without method/class definitions:
    Wraps the source in `def __top__\n ... \nend` and re-parses.

Dependencies: pip install tree-sitter tree-sitter-ruby
"""
import os
import re
import sys
import json
from tree_sitter import Language, Parser


def create_parser():
    try:
        from tree_sitter_language_pack import get_parser
        _p = get_parser("ruby")
        try:
            _p.timeout_micros = 5_000_000
        except (AttributeError, TypeError):
            pass
        return _p
    except Exception:
        pass
    try:
        import tree_sitter_ruby as _mod
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
            "  pip install tree-sitter-ruby")


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
            if t == "method":
                self._process_function(child)
            elif t == "singleton_method":
                self._process_function(child)
            elif t in ("class", "module"):
                self._walk_class(child)

    def _walk_class(self, class_node):
        body = class_node.child_by_field_name("body")
        if body is None:
            return
        for child in body.children:
            t = child.type
            if t == "method":
                self._process_function(child)
            elif t == "singleton_method":
                self._process_function(child)
            elif t in ("class", "module"):
                self._walk_class(child)

    def _process_function(self, func_node):
        name_node = func_node.child_by_field_name("name")
        func_name = self._text(name_node) if name_node else "<anonymous>"

        # For singleton_method (def self.foo), prefix with self.
        if func_node.type == "singleton_method":
            obj = func_node.child_by_field_name("object")
            if obj:
                func_name = f"{self._text(obj)}.{func_name}"

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
        # Distinguish if statement node from `if` keyword token: the
        # statement has children, the keyword token is a leaf.
        if t == "if" and node.child_count > 0:
            return self._handle_if_chain(node, nesting, is_elsif=False, kind="if")

        # ── B1 structural: unless (treated like if) ──
        if t == "unless" and node.child_count > 0:
            return self._handle_if_chain(node, nesting, is_elsif=False, kind="unless")

        # if_modifier / unless_modifier: removed (postfix forms not in
        # White Paper Appendix B). Just recurse without counting.
        if t in ("if_modifier", "unless_modifier"):
            return self._visit_children(node, nesting)

        # ── B1 structural: while ──
        if t == "while" and node.child_count > 0:
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

        # ── B1 structural: until (negated while) ──
        if t == "until" and node.child_count > 0:
            inc = 1 + nesting
            self._add_detail(node, "until", 1, nesting)
            c = inc
            cond = node.child_by_field_name("condition")
            if cond:
                c += self._visit(cond, nesting)
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # while_modifier / until_modifier: removed (postfix forms).
        if t in ("while_modifier", "until_modifier"):
            return self._visit_children(node, nesting)

        # ── B1 structural: for ──
        if t == "for" and node.child_count > 0:
            inc = 1 + nesting
            self._add_detail(node, "for", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── B1 structural: case (single +1 for entire case, p.7) ──
        if t == "case":
            inc = 1 + nesting
            self._add_detail(node, "case", 1, nesting)
            c = inc
            # Visit the case value (may contain method calls)
            value = node.child_by_field_name("value")
            if value:
                c += self._visit(value, nesting)
            # Visit when/else clauses (no additional increment)
            for child in node.children:
                if child.type == "when":
                    body = child.child_by_field_name("body")
                    if body:
                        c += self._visit_children(body, nesting + 1)
                elif child.type == "else":
                    for sub in child.children:
                        if sub.type != "else":
                            c += self._visit(sub, nesting + 1)
            return c

        # ── B1 structural: ternary (conditional) ──
        if t == "conditional":
            inc = 1 + nesting
            self._add_detail(node, "ternary", 1, nesting)
            c = inc
            cond = node.child_by_field_name("condition")
            if cond:
                c += self._visit(cond, nesting)
            consequence = node.child_by_field_name("consequence")
            if consequence:
                c += self._visit(consequence, nesting + 1)
            alt = node.child_by_field_name("alternative")
            if alt:
                c += self._visit(alt, nesting + 1)
            return c

        # ── begin/rescue/ensure: begin and ensure are ignored (p.7) ──
        if t == "begin":
            c = 0
            for child in node.children:
                if child.type == "rescue":
                    c += self._handle_rescue(child, nesting)
                elif child.type == "ensure":
                    # ensure body: visit normally without increment
                    for sub in child.children:
                        if sub.type != "ensure":
                            c += self._visit(sub, nesting)
                elif child.type not in ("begin", "end"):
                    c += self._visit(child, nesting)
            return c

        # ── B1 fundamental: logical operators (binary &&, ||, and, or) ──
        if t == "binary":
            op = node.child_by_field_name("operator")
            if op and self._text(op) in ("&&", "||", "and", "or"):
                return self._handle_boolean(node, nesting)
            return self._visit_children(node, nesting)

        # ── B2: do_block (e.g. items.each do |x| ... end) → nesting (p.9) ──
        if t == "do_block":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── B2: brace block (e.g. items.each { |x| ... }) → nesting (p.9) ──
        if t == "block":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── B2: lambda (-> { ... }) → nesting (p.9) ──
        if t == "lambda":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                # body is a block { ... }
                c += self._visit_children(body, nesting + 1)
            return c

        # ── B2: nested method definition → nesting (p.9) ──
        if t == "method":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        if t == "singleton_method":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── parenthesized statements: unwrap ──
        if t == "parenthesized_statements":
            return self._visit_children(node, nesting)

        # ── default: recurse ──
        return self._visit_children(node, nesting)

    # ── if / elsif / else chain ──

    def _handle_if_chain(self, if_node, nesting, is_elsif, kind="if"):
        c = 0

        if is_elsif:
            # B1 hybrid: elsif → +1, NO nesting penalty, increases nesting level
            c += 1
            self._add_detail(if_node, "elsif", 1, 0)
        else:
            # B1 structural: if/unless → +1, receives nesting
            inc = 1 + nesting
            self._add_detail(if_node, kind, 1, nesting)
            c += inc

        # condition
        cond = if_node.child_by_field_name("condition")
        if cond:
            c += self._visit(cond, nesting)

        # consequence (then body)
        consequence = if_node.child_by_field_name("consequence")
        if consequence:
            # consequence may be a `then` node wrapping the body
            for child in consequence.children:
                if child.type != "then":
                    c += self._visit(child, nesting + 1)

        # alternative: elsif or else
        alt = if_node.child_by_field_name("alternative")
        if alt:
            if alt.type == "elsif":
                c += self._handle_if_chain(alt, nesting, is_elsif=True)
            elif alt.type == "else":
                c += 1
                self._add_detail(alt, "else", 1, 0)
                for child in alt.children:
                    if child.type != "else":
                        c += self._visit(child, nesting + 1)

        return c

    # ── rescue clause handler ──

    def _handle_rescue(self, rescue_node, nesting):
        inc = 1 + nesting
        self._add_detail(rescue_node, "rescue", 1, nesting)
        c = inc
        # rescue body (then) - use body field which points to the then node
        body = rescue_node.child_by_field_name("body")
        if body:
            # body is a 'then' wrapper containing the actual statements
            for child in body.children:
                if child.type != "then":
                    c += self._visit(child, nesting + 1)
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
            # Normalize: and→&&, or→||
            norm = "&&" if op in ("&&", "and") else "||"
            if prev is None or norm != prev:
                c += 1
                desc = (f"logical sequence '{op}'"
                        if prev is None
                        else f"logical change to '{op}'")
                self._add_detail_raw(desc, 1)
                prev = norm
        return c

    def _collect_boolean_ops(self, node, ops):
        if node.type != "binary":
            return
        op_node = node.child_by_field_name("operator")
        if op_node is None:
            return
        op_text = self._text(op_node)
        if op_text not in ("&&", "||", "and", "or"):
            return

        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")

        if left and left.type == "binary":
            lo = left.child_by_field_name("operator")
            if lo and self._text(lo) in ("&&", "||", "and", "or"):
                self._collect_boolean_ops(left, ops)

        ops.append(op_text)

        if right and right.type == "binary":
            ro = right.child_by_field_name("operator")
            if ro and self._text(ro) in ("&&", "||", "and", "or"):
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
            if fname.endswith(".rb"):
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
    print("Ruby Cognitive Complexity Calculator")
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
