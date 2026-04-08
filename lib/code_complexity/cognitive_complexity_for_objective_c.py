"""
Objective-C Cognitive Complexity Calculator
=============================================
Based on:
  - G. Ann Campbell. 2018. "Cognitive Complexity: An Overview and Evaluation."
    TechDebt '18, ICSE, Gothenburg, Sweden.
    https://doi.org/10.1145/3194164.3194186
  - SonarSource. "Cognitive Complexity - a new way of measuring understandability."
    Version 1.7, 29 August 2023.
    https://www.sonarsource.com/docs/CognitiveComplexity.pdf

═══════════════════════════════════════════════════════════════════
Specification (Appendix B, adapted for Objective-C)
═══════════════════════════════════════════════════════════════════

B1. Increments (+1 each)
────────────────────────
  Structural (B):  +1, receives nesting penalty, increases nesting level
    - if                                  → ObjC: if_statement
    - switch                              → ObjC: switch_statement (single +1, p.7)
    - for                                 → ObjC: for_statement (classic and for-in)
    - while                               → ObjC: while_statement
    - do while                            → ObjC: do_statement
    - @catch                              → ObjC: catch_clause (single +1, p.7)
    - ternary operator                    → ObjC: conditional_expression

  Hybrid (D):  +1, NO nesting penalty, but increases nesting level
    - else if                             → ObjC: if_statement as alternative
    - else                                → ObjC: compound_statement as alternative

  Fundamental (C):  +1, NO nesting penalty, does NOT increase nesting level
    - goto                                → ObjC: goto_statement (inherited from C)
    - sequences of binary logical ops     → ObjC: binary_expression with && / ||
    - each method in a recursion cycle    → Not implemented

  Not applicable in Objective-C:
    - break LABEL, continue LABEL         → ObjC has no labeled break/continue
                                            (uses goto instead)

B2. Nesting level (these structures increase nesting for their children)
────────────────────────────────────────────────────────────────────────
    - if, else if, else, ternary
    - switch
    - for, while, do while
    - @catch
    - nested functions: block_literal (Objective-C blocks ^{ ... })
    - nested method/function definitions

B3. Nesting increments (these structures RECEIVE +nesting_level penalty)
────────────────────────────────────────────────────────────────────────
    - if, ternary       (NOT else if, NOT else)
    - switch
    - for, while, do while
    - @catch

═══════════════════════════════════════════════════════════════════
Objective-C-specific notes
═══════════════════════════════════════════════════════════════════

  - Objective-C is a strict superset of C, so all C control structures
    apply: if/else, for (classic), while, do-while, switch, goto, ternary.

  - Objective-C adds these constructs:

    • @interface / @implementation / @protocol — class declarations.
      Walked recursively to find member methods.

    • method_definition — `- (void)foo` (instance) or `+ (void)bar` (class).
      Multi-part selectors like `setName:age:` produce multiple identifier
      children separated by `method_parameter` nodes. We reconstruct the
      full selector for the function name.

    • @try / @catch / @finally — exception handling. Treated like Java's
      try/catch/finally per the spec: try and finally are ignored,
      @catch = +1 structural (p.7).

    • for-in loops: `for (NSString *s in items)` — same for_statement node
      as classic for, no special handling needed.

    • @synchronized(obj) { ... } — synchronization block. Lock acquisition,
      not control flow. Does not break linear flow per the spec, so the
      block contents are visited but no increment is added.

    • @autoreleasepool { ... } — memory management block. Same: visit
      contents without increment.

    • block_literal — ObjC blocks like `^(int x) { ... }` or `^{ ... }`.
      These are anonymous functions / closures. Treated as nested function
      per p.9: no structural increment, increases nesting level.

    • message_expression — `[obj method]` syntax. Just an expression, no
      increment. Trailing block arguments inside messages still get the
      block_literal nesting treatment.

    • property_declaration, protocol_declaration — declarations only,
      no executable code, no complexity.

═══════════════════════════════════════════════════════════════════
Extension: Bare code fallback
═══════════════════════════════════════════════════════════════════

  For snippets without function definitions:
    Wraps in `void __top__() { ... }` and re-parses.

Dependencies: pip install tree-sitter tree-sitter-objc
"""
import os
import re
import sys
import json
from tree_sitter import Language, Parser


def create_parser():
    try:
        from tree_sitter_language_pack import get_parser
        _p = get_parser("objc")
        try:
            _p.timeout_micros = 5_000_000
        except (AttributeError, TypeError):
            pass
        return _p
    except Exception:
        pass
    try:
        import tree_sitter_objc as _mod
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
            "  pip install tree-sitter-objc")


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
            if t == "function_definition":
                self._process_c_function(child)
            elif t in ("class_implementation", "category_implementation"):
                self._walk_implementation(child)
            elif t in ("class_interface", "category_interface",
                       "protocol_declaration"):
                # Interface/protocol declarations have no executable code,
                # only method declarations (no bodies). Skip.
                pass

    def _walk_implementation(self, impl_node):
        # Get class name for prefixing
        class_name = ""
        for child in impl_node.children:
            if child.type == "identifier" and not class_name:
                class_name = self._text(child)
                break

        for child in impl_node.children:
            if child.type == "implementation_definition":
                for sub in child.children:
                    if sub.type == "method_definition":
                        self._process_method(sub, class_name)
                    elif sub.type == "function_definition":
                        self._process_c_function(sub)

    def _process_c_function(self, func_node):
        """Process a C-style function (function_definition)."""
        declarator = func_node.child_by_field_name("declarator")
        func_name = self._extract_c_func_name(declarator) if declarator else "<anonymous>"

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

    def _extract_c_func_name(self, declarator):
        """Recursively extract identifier name from a function_declarator."""
        if declarator is None:
            return "<anonymous>"
        if declarator.type == "identifier":
            return self._text(declarator)
        if declarator.type == "function_declarator":
            inner = declarator.child_by_field_name("declarator")
            return self._extract_c_func_name(inner)
        if declarator.type == "pointer_declarator":
            inner = declarator.child_by_field_name("declarator")
            return self._extract_c_func_name(inner)
        # Fallback: search for first identifier
        for child in declarator.children:
            if child.type == "identifier":
                return self._text(child)
        return "<anonymous>"

    def _process_method(self, method_node, class_name=""):
        """Process an Objective-C method_definition (- or +).
        Reconstructs the multi-part selector if present."""
        # Determine + (class method) or - (instance method)
        prefix = "-"
        for child in method_node.children:
            if child.type == "+":
                prefix = "+"
                break
            if child.type == "-":
                prefix = "-"
                break

        # Extract selector parts. For `setName:age:`, the children include
        # multiple identifier nodes interleaved with method_parameter nodes.
        # The first identifier after method_type is the first selector part.
        selector_parts = []
        seen_method_type = False
        last_was_method_param = False
        for child in method_node.children:
            t = child.type
            if t == "method_type":
                seen_method_type = True
                continue
            if not seen_method_type:
                continue
            if t == "identifier":
                # First identifier OR identifier following a method_parameter
                # = a selector keyword
                if not selector_parts or last_was_method_param:
                    selector_parts.append(self._text(child))
                last_was_method_param = False
            elif t == "method_parameter":
                # method_parameter ends with `:` so the selector keyword
                # before it gets a colon
                if selector_parts:
                    selector_parts[-1] = selector_parts[-1] + ":"
                last_was_method_param = True

        selector = "".join(selector_parts) if selector_parts else "<anonymous>"
        if class_name:
            func_name = f"{prefix}[{class_name} {selector}]"
        else:
            func_name = f"{prefix}{selector}"

        self.details = []
        # Body is a compound_statement child
        body = None
        for child in method_node.children:
            if child.type == "compound_statement":
                body = child
                break

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

        # ── B1 structural: for (classic and for-in) ──
        if t == "for_statement":
            inc = 1 + nesting
            self._add_detail(node, "for", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            else:
                # Body may not have a field name; find compound_statement child
                for child in node.children:
                    if child.type == "compound_statement":
                        c += self._visit_children(child, nesting + 1)
                        break
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

        # ── B1 structural: do-while ──
        if t == "do_statement":
            inc = 1 + nesting
            self._add_detail(node, "do-while", 1, nesting)
            c = inc
            cond = node.child_by_field_name("condition")
            if cond:
                c += self._visit(cond, nesting)
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── B1 structural: switch (single +1, p.7) ──
        if t == "switch_statement":
            inc = 1 + nesting
            self._add_detail(node, "switch", 1, nesting)
            c = inc
            body = node.child_by_field_name("body")
            if body:
                # Visit case_statement bodies; no per-case increment
                for child in body.children:
                    if child.type == "case_statement":
                        for sub in child.children:
                            # Skip the case label (case/default keyword,
                            # case value, and trailing colon)
                            if sub.type in ("case", "default", ":",
                                            "number_literal", "char_literal",
                                            "string_literal", "identifier"):
                                continue
                            c += self._visit(sub, nesting + 1)
            return c

        # ── try: no increment, no nesting change (p.7) ──
        if t == "try_statement":
            c = 0
            for child in node.children:
                c += self._visit(child, nesting)
            return c

        # ── B1 structural: @catch (p.7) ──
        if t == "catch_clause":
            inc = 1 + nesting
            self._add_detail(node, "@catch", 1, nesting)
            c = inc
            for child in node.children:
                if child.type == "compound_statement":
                    c += self._visit_children(child, nesting + 1)
                    break
            return c

        # ── @finally: no increment (p.7) ──
        if t == "finally_clause":
            for child in node.children:
                if child.type == "compound_statement":
                    return self._visit_children(child, nesting)
            return 0

        # ── B1 structural: ternary ──
        if t == "conditional_expression":
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

        # ── B1 fundamental: goto (p.8) ──
        if t == "goto_statement":
            self._add_detail(node, "goto", 1, 0)
            return 1

        # ── B1 fundamental: logical operators (p.7-8) ──
        if t == "binary_expression":
            op = node.child_by_field_name("operator")
            if op and self._text(op) in ("&&", "||"):
                return self._handle_boolean(node, nesting)
            return self._visit_children(node, nesting)

        # ── B2: block_literal → no increment, increases nesting (p.9) ──
        if t == "block_literal":
            c = 0
            for child in node.children:
                if child.type == "compound_statement":
                    c += self._visit_children(child, nesting + 1)
                    break
            return c

        # ── B2: nested function_definition → nesting (p.9) ──
        if t == "function_definition":
            c = 0
            body = node.child_by_field_name("body")
            if body:
                c += self._visit_children(body, nesting + 1)
            return c

        # ── @synchronized: visit body without increment ──
        if t == "synchronized_statement":
            c = 0
            for child in node.children:
                if child.type == "compound_statement":
                    c += self._visit_children(child, nesting)
                else:
                    c += self._visit(child, nesting)
            return c

        # ── compound_statement: may be a regular block or @autoreleasepool ──
        # @autoreleasepool { ... } parses as compound_statement with
        # @autoreleasepool keyword child. Either way: visit children at same nesting.
        if t == "compound_statement":
            return self._visit_children(node, nesting)

        # ── labeled_statement: unwrap (label itself is not incremented) ──
        if t == "labeled_statement":
            c = 0
            for child in node.children:
                if child.type not in ("statement_identifier", ":"):
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

        # consequence
        consequence = if_node.child_by_field_name("consequence")
        if consequence:
            c += self._visit_children(consequence, nesting + 1) \
                if consequence.type == "compound_statement" \
                else self._visit(consequence, nesting + 1)

        # alternative: else_clause containing if_statement (else if) or
        # compound_statement (else)
        alt = if_node.child_by_field_name("alternative")
        if alt and alt.type == "else_clause":
            for child in alt.children:
                if child.type == "if_statement":
                    c += self._handle_if_chain(child, nesting, is_else_if=True)
                elif child.type == "compound_statement":
                    c += 1
                    self._add_detail(child, "else", 1, 0)
                    c += self._visit_children(child, nesting + 1)
                elif child.type not in ("else",):
                    # Single-statement else (no braces)
                    c += 1
                    self._add_detail(child, "else", 1, 0)
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
            if fname.endswith((".m", ".mm", ".h")):
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
    print("Objective-C Cognitive Complexity Calculator")
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
