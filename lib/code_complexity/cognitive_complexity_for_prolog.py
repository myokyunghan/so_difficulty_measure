r"""
Prolog Cognitive Complexity Calculator
========================================
Based on:
  - G. Ann Campbell. 2018. "Cognitive Complexity: An Overview and Evaluation."
    TechDebt '18, ICSE, Gothenburg, Sweden.
    https://doi.org/10.1145/3194164.3194186
  - SonarSource. "Cognitive Complexity - a new way of measuring understandability."
    Version 1.7, 29 August 2023.
    https://www.sonarsource.com/docs/CognitiveComplexity.pdf

═══════════════════════════════════════════════════════════════════
PHILOSOPHY: Why Prolog is fundamentally different
═══════════════════════════════════════════════════════════════════

Prolog is a logic programming language with no imperative control flow
in the traditional sense. The Cognitive Complexity guide assumes
imperative/functional patterns (if/else, for, while, switch, try/catch,
ternary, &&/|| sequences). NONE of these have direct syntactic equivalents
in Prolog. Instead, control flow emerges from:

  • Pattern matching across multiple predicate clauses (like switch)
  • Backtracking on goal failure (no syntactic equivalent)
  • Recursion (the only "loop")
  • Conjunction (`,`) and disjunction (`;`) operators
  • The ISO if-then-else operator `(Cond -> Then ; Else)` (soft cut)
  • Cuts (`!`) which prune backtracking

To preserve the SPIRIT of the white paper, this calculator maps Prolog
constructs to the spec's categories using these heuristics:

═══════════════════════════════════════════════════════════════════
Specification (Appendix B, adapted for Prolog)
═══════════════════════════════════════════════════════════════════

B1. Increments (+1 each)
────────────────────────
  Structural (B):  +1, receives nesting penalty, increases nesting level
    - if-then-else                        → Prolog: (Cond -> Then ; Else)
                                            ISO standard soft-cut idiom
    - if-then (no else)                   → Prolog: (Cond -> Then)
    - multi-clause predicate              → Prolog: a predicate with 2+
                                            clauses dispatches by pattern
                                            matching (switch-equivalent).
                                            Single +1 for the predicate
                                            (per p.7 switch rule). Single-
                                            clause predicates get 0.
    - catch                               → Prolog: catch/3 call
                                            (catch(Goal, Error, Handler))
    - findall / bagof / setof             → "loop-like" meta-predicates
                                            that iterate over solutions
    - forall                              → loop-like universal quantifier

  Hybrid (D):  +1, NO nesting penalty, but increases nesting level
    - else                                → Prolog: the `; Else` part of
                                            an if-then-else triple

  Fundamental (C):  +1, NO nesting penalty, no nesting change
    - sequences of disjunction (;)        → Prolog: chained `;` operators
                                            outside if-then-else patterns
    - each method in a recursion cycle    → Not implemented

  NOT counted (idiomatic Prolog control flow that's "always there"):
    - conjunction (,) — comma between goals is the default; counting it
      would be like counting every statement in C
    - cut (!) — control flow pruning, but not user-visible branching
    - negation as failure (\+ G) — unary; not a binary boolean operator
      sequence in the spec's sense
    - unification (=, =..) — pattern matching, not branching

  Not applicable in Prolog:
    - traditional for/while/do            → Prolog uses recursion or
                                            findall/forall meta-predicates;
                                            see above
    - goto                                → No goto in Prolog
    - break LABEL, continue LABEL         → Not applicable
    - ternary                             → Not applicable as syntax

B2. Nesting level
────────────────────────────────────────────────────────────────────────
    - if-then, if-then-else
    - findall, bagof, setof, forall
    - catch (the Goal and Handler bodies)
    - nested function bodies — not strictly applicable; lambda-style
      goals (yall library `[X]>>Body`) are uncommon and not detected.

B3. Nesting increments (receive +nesting_level penalty)
────────────────────────────────────────────────────────────────────────
    - if-then, if-then-else
    - findall, bagof, setof, forall
    - catch

═══════════════════════════════════════════════════════════════════
Prolog-specific notes
═══════════════════════════════════════════════════════════════════

  - The tree-sitter-prolog grammar uses a uniform `operator_notation`
    node for all binary/prefix operators. The actual operator (`:-`,
    `->`, `;`, `,`, `=`, etc.) appears as either:
      • A `binary_operator` node whose text we read from the source
      • A specific token type: `comma`, `semicolon`
    We dispatch based on the operator text/type.

  - The if-then-else idiom in Prolog is:
        ( Cond -> Then ; Else )
    which the parser sees as: ((Cond -> Then) ; Else). We detect this
    pattern by looking for a `;` whose left side is a `->` operation.
    The whole construct counts as one if (+1 + nesting), the else part
    adds +1 hybrid.

    A bare `( Cond -> Then )` is if-then without else.

  - Multi-clause predicates: in Prolog, defining the same predicate
    multiple times creates pattern-matching dispatch. For example:
        factorial(0, 1).
        factorial(N, F) :- N > 0, N1 is N - 1, factorial(N1, F1),
                           F is N * F1.
    These two `factorial/2` clauses together form one predicate. We
    treat this as switch-equivalent: single +1 if 2+ clauses, 0 if 1.
    Each clause is reported under the predicate name.

  - Disjunction (`;`) outside an if-then-else is treated as a logical
    sequence of `;` operators: each `;` chain contributes fundamental
    increments per the spec's logical operator rule.

  - Conjunction (`,`) is NOT counted. In Prolog, comma is the default
    "and then" for sequencing goals — equivalent to `;` in C between
    statements. Counting commas would inflate every clause.

  - `catch(Goal, Error, Handler)` is Prolog's exception handling. We
    detect calls to the `catch/3` predicate by name. The Goal is visited
    at the same nesting; the Handler at +1 nesting (analogous to a catch
    block). The catch itself is +1 structural (per p.7 catch rule).

  - `findall/3`, `bagof/3`, `setof/3`, `forall/2` are meta-predicates
    that effectively iterate over solutions. They're the closest Prolog
    has to loops, and we count each as a structural +1 with nesting,
    visiting their Goal argument at +1 nesting.

  - Cut (`!`), negation-as-failure (`\+`), and call/1 are NOT counted.
    They affect control flow but don't introduce new branches in the
    cognitive sense.

  - Predicate identity is `name/arity` (e.g., `factorial/2`). We use
    this format in function names.

═══════════════════════════════════════════════════════════════════
Extension: directive handling
═══════════════════════════════════════════════════════════════════

  Prolog files contain `directive_term`s (lines starting with `:-`)
  for module declarations, imports, etc. These don't add complexity
  and are skipped.

Dependencies: tree-sitter, plus tree-sitter-prolog built from source
"""
import os
import sys
import json
import ctypes
from tree_sitter import Language, Parser


def create_parser():
    try:
        from tree_sitter_language_pack import get_parser
        return get_parser("prolog")
    except Exception:
        pass
    so_paths = [
        os.path.join(os.path.dirname(__file__), "build", "prolog.so"),
        os.path.join(os.path.dirname(__file__), "prolog.so"),
        "/home/claude/build/prolog.so",
    ]
    for so_path in so_paths:
        if os.path.exists(so_path):
            try:
                lib = ctypes.cdll.LoadLibrary(so_path)
                func = lib.tree_sitter_prolog
                func.restype = ctypes.c_void_p
                return Parser(Language(func()))
            except Exception:
                continue
    raise ImportError(
        "Prolog parser not found. Build from source:\n"
        "  git clone https://github.com/foxyseta/tree-sitter-prolog.git\n"
        "  gcc -shared -fPIC -O2 -I tree-sitter-prolog/grammars/prolog/src \\\n"
        "      tree-sitter-prolog/grammars/prolog/src/parser.c \\\n"
        "      -o build/prolog.so")


# Loop-like meta-predicates (B1 structural)
_LOOP_META_PREDICATES = frozenset([
    "findall", "bagof", "setof", "forall", "aggregate_all",
])


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

    def _named_children(self, node):
        return [c for c in node.children if c.is_named]

    # ── Top-level traversal ──

    def calculate(self):
        self.results = []
        # Group clauses by predicate name/arity
        predicates = {}  # (name, arity) → list of clause_term nodes
        order = []  # preserve declaration order

        for child in self.tree.root_node.children:
            if child.type == "clause_term":
                pred_key = self._extract_predicate_key(child)
                if pred_key is None:
                    continue
                if pred_key not in predicates:
                    predicates[pred_key] = []
                    order.append(pred_key)
                predicates[pred_key].append(child)
            # directive_term: ignore (module decls, imports, etc.)

        for key in order:
            self._process_predicate(key, predicates[key])

        return self.results

    def _extract_predicate_key(self, clause_term):
        """From a clause_term, extract (name, arity) for the head."""
        # clause_term has one named child: either functional_notation
        # (fact) or operator_notation with `:-` (rule)
        for child in clause_term.children:
            if not child.is_named:
                continue
            if child.type == "functional_notation":
                # Fact: foo(a, b).
                return self._extract_from_functional(child)
            if child.type == "operator_notation":
                # Rule: head :- body. Or atom rule: head. (but no parens)
                # Find the head — leftmost atom or functional_notation
                head = self._extract_head_from_operator(child)
                if head is None:
                    return None
                if head.type == "functional_notation":
                    return self._extract_from_functional(head)
                if head.type == "atom":
                    name = self._text(head).strip()
                    return (name, 0)
            if child.type == "atom":
                # Bare atom fact: foo.
                return (self._text(child).strip(), 0)
        return None

    def _extract_from_functional(self, func_node):
        """Get (name, arity) from a functional_notation node."""
        name_node = func_node.child_by_field_name("function")
        if name_node is None:
            for c in func_node.children:
                if c.type == "atom":
                    name_node = c
                    break
        if name_node is None:
            return None
        name = self._text(name_node).strip()
        # Count arguments in arg_list
        arity = 0
        for c in func_node.children:
            if c.type == "arg_list":
                # Count comma-separated args (named children excluding separators)
                arity = self._count_args(c)
                break
        return (name, arity)

    def _count_args(self, arg_list):
        """Count top-level arguments in an arg_list (separators are
        arg_list_separator nodes)."""
        count = 0
        for c in arg_list.children:
            if c.is_named and c.type != "arg_list_separator":
                count += 1
        return count

    def _extract_head_from_operator(self, op_node):
        """Find the head of a `head :- body` operator_notation, by
        identifying the leftmost operand of the topmost `:-` operator."""
        # Check if this op_node's operator is :-
        if not self._is_clause_operator(op_node, ":-"):
            # Maybe it's a DCG rule (-->) or just a complex expression;
            # treat the whole thing's leftmost named child as the head.
            children = self._named_children(op_node)
            return children[0] if children else None
        children = self._named_children(op_node)
        return children[0] if children else None

    def _is_clause_operator(self, op_node, op_text):
        """Check if an operator_notation node's main operator matches op_text."""
        for c in op_node.children:
            if c.type == "binary_operator":
                if self._text(c).strip() == op_text:
                    return True
                return False
        return False

    def _get_operator_text(self, op_node):
        """Get the operator text of an operator_notation node."""
        for c in op_node.children:
            if c.type == "binary_operator":
                return self._text(c).strip()
            if c.type == "comma":
                return ","
            if c.type == "semicolon":
                return ";"
        return ""

    def _get_operator_kind(self, op_node):
        """Return one of: 'comma', 'semicolon', 'arrow', 'clause',
        'binary', or '' for the operator of an operator_notation node."""
        for c in op_node.children:
            if c.type == "comma":
                return "comma"
            if c.type == "semicolon":
                return "semicolon"
            if c.type == "binary_operator":
                txt = self._text(c).strip()
                if txt == ":-":
                    return "clause"
                if txt == "-->":
                    return "dcg"
                if txt == "->":
                    return "arrow"
                if txt == "*->":
                    return "soft_arrow"
                return "binary"
        return ""

    # ── Predicate processing ──

    def _process_predicate(self, key, clauses):
        """Process all clauses of a single predicate."""
        name, arity = key
        pred_name = f"{name}/{arity}"

        self.details = []
        complexity = 0

        # Multi-clause predicate gets +1 (switch-equivalent, p.7)
        if len(clauses) > 1:
            self._add_detail(clauses[0], "multi-clause predicate", 1, 0)
            complexity += 1

        # Each clause's body contributes its own complexity
        for clause in clauses:
            complexity += self._process_clause_body(clause)

        first = clauses[0]
        last = clauses[-1]
        self.results.append({
            "function": pred_name,
            "complexity": complexity,
            "start_line": first.start_point[0] + 1,
            "end_line": last.end_point[0] + 1,
            "details": list(self.details),
        })

    def _process_clause_body(self, clause_term):
        """Visit a clause_term's body (the part after `:-`).
        For facts (no `:-`), there's no body."""
        c = 0
        for child in clause_term.children:
            if not child.is_named:
                continue
            if child.type == "functional_notation":
                # Fact: no body
                continue
            if child.type == "atom":
                # Bare atom fact
                continue
            if child.type == "operator_notation":
                kind = self._get_operator_kind(child)
                if kind == "clause":
                    # head :- body  → visit body (rightmost named child)
                    children = self._named_children(child)
                    if len(children) >= 2:
                        body = children[-1]
                        c += self._visit_goal(body, 0)
                elif kind == "dcg":
                    # DCG rule: head --> body
                    children = self._named_children(child)
                    if len(children) >= 2:
                        body = children[-1]
                        c += self._visit_goal(body, 0)
                else:
                    # Some other top-level op? Visit it
                    c += self._visit_goal(child, 0)
        return c

    # ── Goal visitor (within a clause body) ──

    def _visit_goal(self, node, nesting):
        """Visit a Prolog goal (an expression that runs).
        Recognizes if-then-else patterns, disjunction sequences, etc."""
        if node is None:
            return 0
        t = node.type

        # operator_notation: dispatch based on operator
        if t == "operator_notation":
            return self._handle_operator(node, nesting)

        # functional_notation: a predicate call. Check for special meta-preds.
        if t == "functional_notation":
            return self._handle_functional_call(node, nesting)

        # prefix_operator usage (e.g. \+ Goal) — visit children but don't count
        # the prefix as a logical sequence
        # Wrappers and parens
        if t in ("open", "close", "open_ct", "open_list", "close_list",
                 "binary_operator", "prefix_operator", "comma", "semicolon"):
            return 0

        # default: recurse over named children
        c = 0
        for child in node.children:
            if child.is_named:
                c += self._visit_goal(child, nesting)
        return c

    def _handle_operator(self, node, nesting):
        """Handle an operator_notation node."""
        kind = self._get_operator_kind(node)

        # Detect if-then-else pattern: a `;` whose LEFT operand is a `->` op.
        # The whole `(Cond -> Then ; Else)` parses as ((Cond -> Then) ; Else).
        if kind == "semicolon":
            return self._handle_semicolon(node, nesting)

        # Bare `->` (if-then without else)
        if kind == "arrow":
            return self._handle_if_then(node, nesting)

        # `,` (conjunction): just visit both sides without counting
        if kind == "comma":
            c = 0
            for child in self._named_children(node):
                c += self._visit_goal(child, nesting)
            return c

        # Other binary operators (=, is, >, <, etc.): visit both sides
        c = 0
        for child in self._named_children(node):
            c += self._visit_goal(child, nesting)
        return c

    def _handle_semicolon(self, sem_node, nesting):
        """Handle `(A ; B)`. Detect if-then-else vs plain disjunction.

        If A is a `->` op, this is if-then-else: +1 structural for the if,
        +1 hybrid for the else.
        Otherwise, this is a disjunction sequence: count `;` operators
        as logical sequence (fundamental, +1 each as we change ops, but
        since they're all `;`, the whole sequence is just +1)."""
        children = self._named_children(sem_node)
        if len(children) < 2:
            return 0
        left, right = children[0], children[-1]

        # Check if left is `->` (or another semicolon containing one — chain)
        if self._contains_arrow_at_top(left):
            return self._handle_if_then_else_chain(sem_node, nesting)

        # Plain disjunction: collect chained `;` and count as logical sequence
        return self._handle_disjunction_sequence(sem_node, nesting)

    def _contains_arrow_at_top(self, node):
        """True iff `node` is an operator_notation whose top operator is `->`."""
        if node is None or node.type != "operator_notation":
            return False
        return self._get_operator_kind(node) == "arrow"

    def _handle_if_then_else_chain(self, sem_node, nesting):
        """Handle `(Cond1 -> Then1 ; Cond2 -> Then2 ; ... ; Else)`.

        Each `Cond -> Then` is treated similarly to if/elseif:
          - First branch: structural +1+nesting (the "if")
          - Subsequent `Cond -> Then`: hybrid +1 (the "else if")
          - Final non-arrow expression: hybrid +1 (the "else")
        Bodies are visited at +1 nesting."""
        c = 0

        # Flatten the right-leaning `;` chain into a list of branches
        branches = []
        cur = sem_node
        while (cur is not None and cur.type == "operator_notation"
                and self._get_operator_kind(cur) == "semicolon"):
            children = self._named_children(cur)
            if len(children) < 2:
                break
            branches.append(children[0])
            cur = children[-1]
        if cur is not None:
            branches.append(cur)

        first_arrow_seen = False
        for i, br in enumerate(branches):
            if self._contains_arrow_at_top(br):
                arrow_children = self._named_children(br)
                cond = arrow_children[0] if arrow_children else None
                then_part = arrow_children[-1] if len(arrow_children) >= 2 else None
                if not first_arrow_seen:
                    inc = 1 + nesting
                    self._add_detail(br, "if-then-else", 1, nesting)
                    c += inc
                    first_arrow_seen = True
                else:
                    self._add_detail(br, "elseif (->)", 1, 0)
                    c += 1
                # Visit cond at current nesting
                if cond is not None:
                    c += self._visit_goal(cond, nesting)
                # Visit then body at +1 nesting
                if then_part is not None:
                    c += self._visit_goal(then_part, nesting + 1)
            else:
                # Final else branch (non-arrow)
                self._add_detail(br, "else", 1, 0)
                c += 1
                c += self._visit_goal(br, nesting + 1)
        return c

    def _handle_if_then(self, arrow_node, nesting):
        """Handle bare `(Cond -> Then)` without else."""
        c = 0
        inc = 1 + nesting
        self._add_detail(arrow_node, "if-then", 1, nesting)
        c += inc
        children = self._named_children(arrow_node)
        if len(children) >= 1:
            c += self._visit_goal(children[0], nesting)  # cond
        if len(children) >= 2:
            c += self._visit_goal(children[-1], nesting + 1)  # then
        return c

    def _handle_disjunction_sequence(self, sem_node, nesting):
        """Handle a chain of `;` (disjunction) outside if-then-else.
        Treat as a logical sequence: the whole chain counts as a single
        fundamental increment (since all operators are `;`)."""
        # Count of `;` chained together at this level
        # Per the spec's logical-sequence rule, a sequence of the same
        # operator counts as one fundamental increment.
        c = 1
        self._add_detail_raw("disjunction sequence ';'", 1)

        # Visit all sub-expressions at the same nesting (they're alternatives)
        cur = sem_node
        while (cur is not None and cur.type == "operator_notation"
                and self._get_operator_kind(cur) == "semicolon"):
            children = self._named_children(cur)
            if len(children) < 2:
                break
            c += self._visit_goal(children[0], nesting)
            cur = children[-1]
        if cur is not None:
            c += self._visit_goal(cur, nesting)
        return c

    def _handle_functional_call(self, func_node, nesting):
        """Handle a functional_notation call. Check for catch/3, findall/3,
        forall/2, etc., otherwise just visit the arguments."""
        # Get the predicate name
        name_node = func_node.child_by_field_name("function")
        if name_node is None:
            for c in func_node.children:
                if c.type == "atom":
                    name_node = c
                    break
        name = self._text(name_node).strip() if name_node else ""

        # Get the argument list
        arg_list_node = None
        for c in func_node.children:
            if c.type == "arg_list":
                arg_list_node = c
                break

        # Special handling: catch/3
        if name == "catch":
            return self._handle_catch(func_node, arg_list_node, nesting)

        # Special handling: findall/3, bagof/3, setof/3, aggregate_all/3
        if name in _LOOP_META_PREDICATES and name != "forall":
            return self._handle_findall_like(func_node, arg_list_node,
                                              name, nesting)

        # forall/2 — Goal at +1, Cond at same level
        if name == "forall":
            return self._handle_forall(func_node, arg_list_node, nesting)

        # Default: visit all arguments at the same nesting
        c = 0
        if arg_list_node is not None:
            for c2 in arg_list_node.children:
                if c2.is_named and c2.type != "arg_list_separator":
                    c += self._visit_goal(c2, nesting)
        return c

    def _handle_catch(self, func_node, arg_list, nesting):
        """catch(Goal, Error, Handler):
          - +1 structural with nesting (analogous to try/catch)
          - Goal visited at same nesting
          - Handler visited at +1 nesting
        """
        if arg_list is None:
            return 0
        args = [c for c in arg_list.children
                if c.is_named and c.type != "arg_list_separator"]
        if len(args) < 3:
            # Not the standard catch/3 form
            c = 0
            for a in args:
                c += self._visit_goal(a, nesting)
            return c

        c = 1 + nesting
        self._add_detail(func_node, "catch", 1, nesting)
        # Goal: visit at same nesting (the protected code)
        c += self._visit_goal(args[0], nesting)
        # Error pattern: just a term, no complexity
        # Handler: visit at +1 nesting
        c += self._visit_goal(args[2], nesting + 1)
        return c

    def _handle_findall_like(self, func_node, arg_list, name, nesting):
        """findall(Template, Goal, List): iterate Goal solutions.
        +1 structural with nesting, visit Goal at +1 nesting."""
        if arg_list is None:
            return 0
        args = [c for c in arg_list.children
                if c.is_named and c.type != "arg_list_separator"]
        if len(args) < 2:
            c = 0
            for a in args:
                c += self._visit_goal(a, nesting)
            return c

        c = 1 + nesting
        self._add_detail(func_node, name, 1, nesting)
        # Template (arg 0) is just a term: no complexity
        # Goal (arg 1) is the iterated goal: visit at +1 nesting
        if len(args) >= 2:
            c += self._visit_goal(args[1], nesting + 1)
        # List (arg 2) is just a variable
        return c

    def _handle_forall(self, func_node, arg_list, nesting):
        """forall(Cond, Action): for every Cond solution, Action must hold.
        +1 structural with nesting; both Cond and Action visited at +1."""
        if arg_list is None:
            return 0
        args = [c for c in arg_list.children
                if c.is_named and c.type != "arg_list_separator"]
        if len(args) < 2:
            c = 0
            for a in args:
                c += self._visit_goal(a, nesting)
            return c

        c = 1 + nesting
        self._add_detail(func_node, "forall", 1, nesting)
        c += self._visit_goal(args[0], nesting + 1)
        c += self._visit_goal(args[1], nesting + 1)
        return c


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
            if fname.endswith((".pl", ".pro", ".prolog", ".plt")):
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
        print(f"Predicate: {r['function']} "
              f"(lines {r['start_line']}-{r['end_line']})")
        print(f"Cognitive Complexity: {r['complexity']}")
        if verbose and r["details"]:
            print("Details:")
            for d in r["details"]:
                print(d)

    print(f"\n{'='*60}")
    print(f"Total Cognitive Complexity: {total}")
    print(f"Number of predicates: {len(results)}")
    if results:
        print(f"Average per predicate: {total / len(results):.1f}")


if __name__ == "__main__":
    print("Prolog Cognitive Complexity Calculator")
    print("SonarSource Specification v1.7 (29 August 2023) - heuristic mapping")
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