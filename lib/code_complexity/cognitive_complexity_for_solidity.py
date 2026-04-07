"""
Solidity Cognitive Complexity Calculator
==========================================
Based on:
  - G. Ann Campbell. 2018. "Cognitive Complexity: An Overview and Evaluation."
    TechDebt '18, ICSE, Gothenburg, Sweden.
    https://doi.org/10.1145/3194164.3194186
  - SonarSource. "Cognitive Complexity - a new way of measuring understandability."
    Version 1.7, 29 August 2023.
    https://www.sonarsource.com/docs/CognitiveComplexity.pdf

═══════════════════════════════════════════════════════════════════
Specification (Appendix B, adapted for Solidity)
═══════════════════════════════════════════════════════════════════

Solidity is a statically-typed, contract-oriented language designed for
the Ethereum Virtual Machine (EVM). Its syntax is inspired by JavaScript
and C++, with imperative control flow structures that map cleanly to
the Cognitive Complexity spec.

B1. Increments (+1 each)
────────────────────────
  Structural (B):  +1, receives nesting penalty, increases nesting level
    - if                                  → Solidity: if_statement
    - for                                 → Solidity: for_statement
    - while                               → Solidity: while_statement
    - do-while                            → Solidity: do_while_statement
    - try/catch                           → Solidity: try_statement. Each
                                            catch_clause counts as one
                                            structural increment (since
                                            Solidity allows multiple catches
                                            like C#'s catch Error(...)
                                            catch (bytes memory)).
    - ternary                             → Solidity: ternary_expression

  Hybrid (D):  +1, NO nesting penalty, but increases nesting level
    - else if                             → Solidity: the `else` branch
                                            of an if_statement that is
                                            itself another if_statement
    - else                                → Solidity: the `else` branch
                                            of an if_statement (any other
                                            kind of statement)

  Fundamental (C):  +1, NO nesting penalty, no nesting change
    - sequences of binary logical ops     → Solidity: binary_expression
                                            with && / || operators
    - each method in a recursion cycle    → Not implemented

  Not applicable in Solidity:
    - goto                                → No goto in Solidity
    - switch                              → Solidity has no switch/case
                                            (the assembly `switch` exists
                                            in Yul inline assembly but is
                                            not detected in this calculator)
    - break LABEL, continue LABEL         → Solidity has unlabeled
                                            break/continue only. Plain
                                            forms add no complexity.

B2. Nesting level
────────────────────────────────────────────────────────────────────────
    - if, else, else-if
    - for, while, do-while
    - try body, catch body
    - ternary
    - nested function-like entities (modifiers inside contracts are
      reported as separate functions, not nested)

B3. Nesting increments (receive +nesting_level penalty)
────────────────────────────────────────────────────────────────────────
    - if (NOT else, NOT else-if)
    - for, while, do-while
    - try + each catch
    - ternary

═══════════════════════════════════════════════════════════════════
Solidity-specific notes
═══════════════════════════════════════════════════════════════════

  - Solidity uses `&&` and `||` for short-circuit boolean operators,
    following C/JavaScript conventions. Both contribute to fundamental
    logical operator sequences. `!` is unary and not counted.

  - `require(cond, msg)`, `assert(cond)`, and `revert(reason)` are
    library functions that halt execution on failure. They are regular
    function calls and are NOT counted as control flow. The Solidity
    style is to use them for preconditions, but they're not structural
    branches in the spec's sense.

  - `try/catch`: Solidity's try-catch is unusual because it can ONLY
    be applied to external function calls or contract creation. The
    syntax supports multiple catch clauses:
        try ext.call() returns (uint r) {
            // success handler
        } catch Error(string memory reason) {
            // revert with reason string
        } catch Panic(uint errorCode) {
            // panic (arithmetic overflow, etc.)
        } catch (bytes memory lowLevelData) {
            // catch-all
        }
    Each `catch_clause` gets +1 structural with nesting, similar to
    how C# and Java handle multiple catch blocks.

  - Solidity's `if-else` chain is represented as NESTED if_statements
    in the AST. An `else if` becomes the `body` (second one) of the
    `if_statement`, which is itself another `if_statement`. We walk
    the chain and apply hybrid increments for elseif and else.

  - **Important parser quirk**: `if_statement` uses the `body` field
    name TWICE — once for the then-branch and once for the else-branch
    (after the `else` keyword child). We walk children sequentially
    and track whether we've seen the `else` keyword to distinguish.

  - `modifier`: Solidity modifiers are reusable pieces of code that run
    before/after function bodies. They can contain control flow and
    the special `_;` placeholder (which represents where the modified
    function's body is inserted). We report each `modifier_definition`
    as a separate function and count its body's complexity normally.
    The `_;` placeholder is just an expression_statement with the `_`
    identifier — no control flow implications.

  - `constructor_definition`: a special function. Reported as
    `<ContractName>::constructor`.

  - `function_definition`: reported as `<ContractName>::<funcName>`.
    Free functions (at file level, outside any contract) are reported
    with no prefix.

  - `inheritance_specifier` / `override_specifier` / `virtual` are
    modifiers on contracts/functions. They affect inheritance but not
    complexity. The `is Base1, Base2` clause adds no complexity.

  - `interface` functions have no body (they end with `;`) — they're
    declarations only. Complexity is 0. We still report them as
    functions with complexity 0 (or skip them — we choose to skip).

  - `library` is like a contract but stateless. Its functions are
    reported with the library name prefix.

  - `emit EventName(args)`: event emission is not control flow — it's
    a library-level construct with no branching implications. Not
    counted.

  - `assembly { ... }` blocks contain Yul inline assembly. Yul has its
    own if/switch/for constructs. Since these are less common and add
    significant complexity to the calculator, we conservatively visit
    the contents but don't deeply interpret Yul control flow. Any
    if/for/while at the Solidity level within assembly is unreachable
    (assembly has its own language), so we simply skip assembly blocks
    for now and treat them as adding no complexity.

  - Solidity's `unchecked { ... }` block disables overflow checks for
    a region of code. It's NOT control flow — just a scope with
    different arithmetic semantics. We visit the contents at the same
    nesting level.

═══════════════════════════════════════════════════════════════════
Extension: Inheritance and multiple contracts
═══════════════════════════════════════════════════════════════════

  A Solidity file can contain multiple `contract_declaration`s (e.g.,
  a base contract and a derived contract). Each is walked and its
  functions are reported with the appropriate contract name prefix.

Dependencies: pip install tree-sitter tree-sitter-solidity
"""
import os
import sys
import json
from tree_sitter import Language, Parser


def create_parser():
    try:
        from tree_sitter_language_pack import get_parser
        return get_parser("solidity")
    except Exception:
        pass
    try:
        import tree_sitter_solidity as _mod
        return Parser(Language(_mod.language()))
    except ImportError:
        raise ImportError(
            "Install one of:\n"
            "  pip install tree-sitter-language-pack\n"
            "  pip install tree-sitter-solidity")


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

    def _field_name(self, parent, child):
        for i, c in enumerate(parent.children):
            if c == child:
                return parent.field_name_for_child(i)
        return None

    def _find_child(self, node, type_name):
        for c in node.children:
            if c.type == type_name:
                return c
        return None

    # ── Top-level traversal ──

    def calculate(self):
        self.results = []
        self._walk_top_level(self.tree.root_node)
        return self.results

    def _walk_top_level(self, node):
        for child in node.children:
            t = child.type
            if t == "contract_declaration":
                self._walk_contract(child, "contract")
            elif t == "library_declaration":
                self._walk_contract(child, "library")
            elif t == "interface_declaration":
                # Interfaces have only signatures; skip for reporting
                # unless they contain any implementation (they shouldn't).
                self._walk_contract(child, "interface")
            elif t == "function_definition":
                # Free function (file-level, outside any contract)
                self._process_function(child, "")

    def _walk_contract(self, contract_node, kind):
        # Get contract/library/interface name
        name_node = self._find_child(contract_node, "identifier")
        name = self._text(name_node) if name_node else "<anonymous>"
        prefix = f"{name}::"

        # Walk the contract_body
        body = None
        for child in contract_node.children:
            fn = self._field_name(contract_node, child)
            if fn == "body":
                body = child
                break
        if body is None:
            return

        for member in body.children:
            mt = member.type
            if mt == "function_definition":
                # Interface functions have no body — skip them
                if kind == "interface":
                    # Check if it has a function_body
                    if self._find_child(member, "function_body") is None:
                        continue
                self._process_function(member, prefix)
            elif mt == "constructor_definition":
                self._process_constructor(member, prefix)
            elif mt == "modifier_definition":
                self._process_modifier(member, prefix)
            elif mt == "fallback_receive_definition":
                # Fallback/receive functions (special Solidity functions)
                self._process_function(member, prefix,
                                         default_name="<fallback>")

    def _process_function(self, func_node, prefix, default_name="<anonymous>"):
        # Extract name
        name_node = self._find_child(func_node, "identifier")
        name = self._text(name_node) if name_node else default_name
        full_name = f"{prefix}{name}"

        # Find function_body
        body = None
        for child in func_node.children:
            fn = self._field_name(func_node, child)
            if fn == "body":
                body = child
                break

        if body is None:
            # Abstract / interface function (no body)
            return

        self.details = []
        complexity = self._visit_children(body, 0)

        self.results.append({
            "function": full_name,
            "complexity": complexity,
            "start_line": func_node.start_point[0] + 1,
            "end_line": func_node.end_point[0] + 1,
            "details": list(self.details),
        })

    def _process_constructor(self, ctor_node, prefix):
        full_name = f"{prefix}constructor"
        body = None
        for child in ctor_node.children:
            fn = self._field_name(ctor_node, child)
            if fn == "body":
                body = child
                break
        if body is None:
            return

        self.details = []
        complexity = self._visit_children(body, 0)

        self.results.append({
            "function": full_name,
            "complexity": complexity,
            "start_line": ctor_node.start_point[0] + 1,
            "end_line": ctor_node.end_point[0] + 1,
            "details": list(self.details),
        })

    def _process_modifier(self, mod_node, prefix):
        name_node = self._find_child(mod_node, "identifier")
        name = self._text(name_node) if name_node else "<anonymous>"
        full_name = f"{prefix}{name} (modifier)"

        body = None
        for child in mod_node.children:
            fn = self._field_name(mod_node, child)
            if fn == "body":
                body = child
                break
        if body is None:
            return

        self.details = []
        complexity = self._visit_children(body, 0)

        self.results.append({
            "function": full_name,
            "complexity": complexity,
            "start_line": mod_node.start_point[0] + 1,
            "end_line": mod_node.end_point[0] + 1,
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
            return self._handle_if(node, nesting, is_else_if=False)

        # ── B1 structural: for ──
        if t == "for_statement":
            inc = 1 + nesting
            self._add_detail(node, "for", 1, nesting)
            c = inc
            # Visit initial, condition, update, body
            for child in node.children:
                fn = self._field_name(node, child)
                if fn in ("initial", "condition", "update"):
                    c += self._visit(child, nesting)
                elif fn == "body":
                    c += self._visit(child, nesting + 1)
            return c

        # ── B1 structural: while ──
        if t == "while_statement":
            inc = 1 + nesting
            self._add_detail(node, "while", 1, nesting)
            c = inc
            for child in node.children:
                fn = self._field_name(node, child)
                if fn == "condition":
                    c += self._visit(child, nesting)
                elif fn == "body":
                    c += self._visit(child, nesting + 1)
            return c

        # ── B1 structural: do-while ──
        if t == "do_while_statement":
            inc = 1 + nesting
            self._add_detail(node, "do-while", 1, nesting)
            c = inc
            for child in node.children:
                fn = self._field_name(node, child)
                if fn == "condition":
                    c += self._visit(child, nesting)
                elif fn == "body":
                    c += self._visit(child, nesting + 1)
            return c

        # ── B1 structural: try/catch ──
        if t == "try_statement":
            return self._handle_try(node, nesting)

        # ── B1 structural: ternary ──
        if t == "ternary_expression":
            inc = 1 + nesting
            self._add_detail(node, "ternary", 1, nesting)
            c = inc
            # Visit all children except ?/: tokens
            for child in node.children:
                if child.type in ("?", ":"):
                    continue
                c += self._visit(child, nesting)
            return c

        # ── B1 fundamental: binary logical ops ──
        if t == "binary_expression":
            op = node.child_by_field_name("operator")
            if op is not None and op.type in ("&&", "||"):
                return self._handle_boolean(node, nesting)
            return self._visit_children(node, nesting)

        # ── assembly block: skip (Yul has its own semantics) ──
        if t == "assembly_statement":
            return 0

        # ── default: recurse ──
        return self._visit_children(node, nesting)

    # ── if / else / else-if chain handling ──

    def _handle_if(self, if_node, nesting, is_else_if):
        c = 0
        if is_else_if:
            # Hybrid: +1, no nesting penalty
            c += 1
            self._add_detail(if_node, "else if", 1, 0)
        else:
            # Structural: +1 + nesting
            inc = 1 + nesting
            self._add_detail(if_node, "if", 1, nesting)
            c += inc

        # Visit condition
        cond = if_node.child_by_field_name("condition")
        if cond:
            c += self._visit(cond, nesting)

        # if_statement uses `body` field TWICE: first for then, second
        # for else (after the `else` keyword). Walk sequentially.
        seen_else_kw = False
        then_body = None
        else_body = None
        for i, child in enumerate(if_node.children):
            if child.type == "else":
                seen_else_kw = True
                continue
            fn = if_node.field_name_for_child(i)
            if fn == "body":
                if not seen_else_kw:
                    then_body = child
                else:
                    else_body = child

        if then_body:
            c += self._visit(then_body, nesting + 1)

        if else_body is not None:
            if else_body.type == "if_statement":
                # else-if: recurse with hybrid treatment
                c += self._handle_if(else_body, nesting, is_else_if=True)
            elif (else_body.type == "statement"
                    and len(else_body.children) == 1
                    and else_body.children[0].type == "if_statement"):
                # else-if wrapped in a statement node
                c += self._handle_if(else_body.children[0], nesting,
                                       is_else_if=True)
            else:
                # Plain else
                c += 1
                self._add_detail(else_body, "else", 1, 0)
                c += self._visit(else_body, nesting + 1)

        return c

    # ── try/catch handling ──

    def _handle_try(self, try_node, nesting):
        """try_statement structure:
            try expr returns (params) body
              catch_clause*
        Per the spec (p.7) and consistent with Java/C#, the `try` itself
        is NOT counted — it's just a container. Each `catch_clause` is
        +1 structural with nesting. The try body is visited at the
        current nesting level (not incremented by the try).
        """
        c = 0

        # Visit the attempt expression and try body at current nesting
        for child in try_node.children:
            t = child.type
            if t in ("try", "returns", "(", ")", "parameter"):
                continue
            fn = self._field_name(try_node, child)
            if fn == "attempt":
                c += self._visit(child, nesting)
            elif fn == "body":
                c += self._visit(child, nesting)
            elif t == "catch_clause":
                c += self._handle_catch(child, nesting)

        return c

    def _handle_catch(self, catch_node, nesting):
        c = 0
        inc = 1 + nesting
        self._add_detail(catch_node, "catch", 1, nesting)
        c += inc

        body = None
        for child in catch_node.children:
            fn = self._field_name(catch_node, child)
            if fn == "body":
                body = child
                break
        if body is not None:
            c += self._visit(body, nesting + 1)
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
        # Unwrap expression wrappers
        while node.type == "expression" and len(node.children) == 1:
            node = node.children[0]
        if node.type != "binary_expression":
            return
        op_node = node.child_by_field_name("operator")
        if op_node is None:
            return
        if op_node.type not in ("&&", "||"):
            return
        op_text = op_node.type

        left = node.child_by_field_name("left")
        right = node.child_by_field_name("right")

        def unwrap(n):
            while n is not None and n.type == "expression" and len(n.children) == 1:
                n = n.children[0]
            return n

        left_inner = unwrap(left)
        right_inner = unwrap(right)

        if left_inner is not None and left_inner.type == "binary_expression":
            lo = left_inner.child_by_field_name("operator")
            if lo and lo.type in ("&&", "||"):
                self._collect_boolean_ops(left_inner, ops)

        ops.append(op_text)

        if right_inner is not None and right_inner.type == "binary_expression":
            ro = right_inner.child_by_field_name("operator")
            if ro and ro.type in ("&&", "||"):
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
            if fname.endswith(".sol"):
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
    print("Solidity Cognitive Complexity Calculator")
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