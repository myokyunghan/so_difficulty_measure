"""
Assembly Cognitive Complexity Calculator
==========================================
Based on:
  - G. Ann Campbell. 2018. "Cognitive Complexity: An Overview and Evaluation."
    TechDebt '18, ICSE, Gothenburg, Sweden.
    https://doi.org/10.1145/3194164.3194186
  - SonarSource. "Cognitive Complexity - a new way of measuring understandability."
    Version 1.7, 29 August 2023.
    https://www.sonarsource.com/docs/CognitiveComplexity.pdf

═══════════════════════════════════════════════════════════════════
PHILOSOPHY: Why assembly is fundamentally different
═══════════════════════════════════════════════════════════════════

The Cognitive Complexity metric was designed for high-level languages with
structured control flow (if/else, for, while, switch, try/catch, ternary,
short-circuit && / ||). NONE of these constructs exist in assembly. At the
machine-code level, every conditional/unconditional branch is essentially
a labeled goto.

A naïve "count every jump as +1" approach yields essentially Cyclomatic
Complexity, which is precisely the metric the spec set out to replace.
To preserve the SPIRIT of the white paper, this calculator uses static
heuristics to RECONSTRUCT high-level control structures from jump patterns:

  • Backward conditional jump   →  loop (B1 structural, +1 + nesting)
  • Forward conditional jump    →  if   (B1 structural, +1 + nesting)
  • The "skip-the-else" pattern →  else (B1 hybrid, +1, no nesting)
       (an unconditional forward jump immediately before the if-target,
        skipping past additional code)
  • Unconditional jump (other)  →  goto (B1 fundamental, +1)
  • Repeated forward jumps from
    a single compare to the same
    target                      →  short-circuit && / || sequence
                                   (B1 fundamental, +1 per change)

Nesting:
  When a loop or if is entered, nesting increases by 1 for instructions
  located between the branch and its target label. Nesting stacks naturally
  when multiple control structures' "scopes" overlap.

═══════════════════════════════════════════════════════════════════
Specification mapping (Appendix B → assembly)
═══════════════════════════════════════════════════════════════════

B1. Increments
  Structural (B):  +1, receives nesting penalty, increases nesting level
    - if      ←  forward conditional jump
    - loop    ←  backward conditional jump
    (switch and try/catch have no reliable assembly signature → not detected)

  Hybrid (D):  +1, NO nesting penalty, but increases nesting level
    - else    ←  the "skip-the-else" pattern: an unconditional jump from
                 the end of the if-then body, jumping past additional code
                 to land at the if-merge point. The skipped region is the
                 else body and gets nesting+1 for its contents.

  Fundamental (C):  +1, NO nesting penalty, no nesting change
    - goto                  ←  unconditional jump that doesn't fit the
                                else pattern
    - logical op sequences  ←  multiple forward conditional jumps from
                                a contiguous compare-then-branch chain
                                that all target the same label. The first
                                jump establishes the if (already counted
                                as structural); each ADDITIONAL jump adds
                                +1 fundamental.

B2. Nesting level
    Loops and ifs increase nesting level for instructions within their
    span (between the jump and its target).

B3. Nesting increments
    Loops and ifs RECEIVE the current nesting penalty when their structure
    is detected.

═══════════════════════════════════════════════════════════════════
Architecture support
═══════════════════════════════════════════════════════════════════

This calculator is architecture-neutral and recognizes branch instructions
by mnemonic patterns covering common ISAs:

  • x86 / x86-64:  jmp, je, jne, jz, jnz, jl, jg, jle, jge, ja, jb, jae, jbe,
                    jc, jnc, jo, jno, js, jns, jp, jnp, jcxz, jecxz, jrcxz,
                    loop, loope, loopne, call, ret
  • ARM / AArch64: b, bl, blx, bx, beq, bne, blt, bgt, ble, bge, bhi, blo,
                    bhs, blt, bcs, bcc, bvs, bvc, bmi, bpl, cbz, cbnz,
                    tbz, tbnz
  • MIPS:          j, jal, jalr, jr, beq, bne, bgez, bgtz, blez, bltz,
                    beqz, bnez
  • RISC-V:        j, jal, jalr, beq, bne, blt, bge, bltu, bgeu, beqz, bnez,
                    blez, bgez, bltz, bgtz, ble, bgt, bgtu, bleu

Both Intel and AT&T x86 syntaxes are supported (target operand parsing).

═══════════════════════════════════════════════════════════════════
Function detection
═══════════════════════════════════════════════════════════════════

Assembly has no formal function concept. We detect function-like spans by:

  1. Labels marked with `.global` / `.globl` directives.
  2. Labels followed by typical prologue patterns (push rbp; mov rbp,rsp,
     stp x29,x30, etc.).
  3. Labels at file scope (top-level, non-numeric, non-local).

A function spans from its label to the next ret/return-like instruction
or the next function-level label, whichever comes first. If no functions
are detected, the entire file is treated as one anonymous function.

═══════════════════════════════════════════════════════════════════
Known limitations (inherent to the problem, not the implementation)
═══════════════════════════════════════════════════════════════════

  - switch/case (jump tables) cannot be reliably distinguished from
    arrays of pointers; not detected.
  - try/catch (exception handling) requires platform-specific unwind
    metadata (.eh_frame, SEH); not detected.
  - ternary operator collapses to a forward conditional jump, so it is
    counted as a regular if. This is OK because ternary's spec increment
    matches if anyway (+1 + nesting).
  - Tail calls (jmp to another function) may be counted as goto +1; this
    matches the white paper's treatment of goto as fundamental.
  - Computed jumps (`jmp rax`, `jmp [table+rax*8]`) are treated as goto +1
    since the target is unknown.
  - Compiler optimizations (loop unrolling, tail-call optimization, basic
    block reordering) may make the heuristics produce values different from
    what the original source would yield. This is unavoidable.

No external dependencies. Pure Python.
"""
import os
import re
import sys
import json


# ── Branch instruction patterns (broad ISA coverage) ──

# Unconditional jumps (jump only, no return address)
_UNCOND_JUMPS = frozenset([
    # x86
    "jmp", "jmpq", "jmpl", "jmpw", "jmpb",
    # ARM/AArch64
    "b", "bx",
    # MIPS / RISC-V
    "j", "jr",
])

# Calls (link register / push return address) — NOT control flow for our purposes
_CALL_INSTRS = frozenset([
    "call", "callq", "calll",            # x86
    "bl", "blx", "blr",                  # ARM
    "jal", "jalr",                       # MIPS / RISC-V
])

# Returns
_RET_INSTRS = frozenset([
    "ret", "retq", "retl", "retn", "iret", "iretq", "iretd",
    "leave",  # often immediately precedes ret
    "bx",     # ARM "bx lr" is a return; handled specially below
    "blr",    # caution: this is a call on AArch64, not a return
    "jr",     # MIPS "jr ra" is a return; handled specially below
    "ret.f",  # some toolchains
])

# Conditional jump prefixes/exact mnemonics
# We use a broad regex over a fixed set for safety.
_COND_JUMPS = frozenset([
    # x86 conditional jumps
    "je", "jne", "jz", "jnz", "jl", "jg", "jle", "jge",
    "ja", "jb", "jae", "jbe", "jna", "jnb", "jnae", "jnbe",
    "jc", "jnc", "jo", "jno", "js", "jns", "jp", "jnp",
    "jpe", "jpo", "jcxz", "jecxz", "jrcxz",
    # x86 loop instructions (decrement-and-branch)
    "loop", "loope", "loopne", "loopz", "loopnz",
    # ARM/AArch64 conditional branches (B + condition)
    "beq", "bne", "blt", "bgt", "ble", "bge",
    "bhi", "blo", "bhs", "bls", "bcs", "bcc",
    "bvs", "bvc", "bmi", "bpl", "bal",
    "cbz", "cbnz", "tbz", "tbnz",
    # MIPS conditional branches
    "bgez", "bgtz", "blez", "bltz",
    "beqz", "bnez",
    # RISC-V conditional branches
    "bltu", "bgeu", "bgtu", "bleu",
])

# Compare instructions (used to detect short-circuit logical sequences)
_COMPARE_INSTRS = frozenset([
    # x86
    "cmp", "cmpq", "cmpl", "cmpw", "cmpb",
    "test", "testq", "testl", "testw", "testb",
    # ARM
    "cmp", "cmn", "tst", "teq",
    # MIPS / RISC-V often fold compare into the branch itself
])


def _is_likely_return(mnemonic: str, operands: str) -> bool:
    """Detect a return instruction. Some mnemonics are ambiguous and
    only count as return given specific operands (e.g. ARM `bx lr`)."""
    m = mnemonic.lower()
    if m in ("ret", "retq", "retl", "retn", "iret", "iretq", "iretd",
             "ret.f"):
        return True
    op = operands.strip().lower().lstrip("$%")
    # ARM: `bx lr` is a return; `blr` (Branch with Link to Register) is a CALL
    if m == "bx" and op in ("lr", "x30"):
        return True
    # MIPS: `jr ra` (or `jr $ra`) is a return
    if m == "jr" and op == "ra":
        return True
    return False


def _is_call(mnemonic: str) -> bool:
    return mnemonic.lower() in _CALL_INSTRS


def _is_uncond_jump(mnemonic: str, operands: str) -> bool:
    m = mnemonic.lower()
    if m in _UNCOND_JUMPS:
        # ARM `bx lr` is a return, not a jump. Same for MIPS `jr ra`.
        if _is_likely_return(m, operands):
            return False
        return True
    return False


def _is_cond_jump(mnemonic: str) -> bool:
    return mnemonic.lower() in _COND_JUMPS


def _is_compare(mnemonic: str) -> bool:
    return mnemonic.lower() in _COMPARE_INSTRS


# ── Line parsing ──

# A reasonably permissive line tokenizer covering Intel & AT&T x86, ARM,
# MIPS, RISC-V. Comments may start with ;, #, //, or @ (ARM).
_COMMENT_RE = re.compile(r"(;|//|@(?!\w)).*$|#(?!\d).*$")
_LABEL_RE = re.compile(r"^([A-Za-z_.$][\w.$]*|\d+):")


def _strip_comment(line: str) -> str:
    # Remove trailing comment but preserve string literals if any.
    # Assembly rarely has strings on instruction lines, so a simple strip is OK.
    return _COMMENT_RE.sub("", line).rstrip()


def _parse_line(line: str):
    """Parse a single assembly line.
    Returns dict with: 'label' (or None), 'mnemonic' (or None),
    'operands' (str), 'directive' (or None), 'raw' (original)."""
    raw = line
    text = _strip_comment(line).strip()
    if not text:
        return {"label": None, "mnemonic": None, "operands": "",
                "directive": None, "raw": raw}

    label = None
    m = _LABEL_RE.match(text)
    if m:
        label = m.group(1)
        text = text[m.end():].strip()
        if not text:
            return {"label": label, "mnemonic": None, "operands": "",
                    "directive": None, "raw": raw}

    # Directive: starts with '.'
    if text.startswith("."):
        # e.g. ".global foo", ".section .text", ".p2align 4"
        parts = text.split(None, 1)
        return {"label": label, "mnemonic": None, "operands": "",
                "directive": parts[0],
                "directive_args": parts[1] if len(parts) > 1 else "",
                "raw": raw}

    # Otherwise: mnemonic + operands
    parts = text.split(None, 1)
    mnemonic = parts[0]
    operands = parts[1].strip() if len(parts) > 1 else ""
    return {"label": label, "mnemonic": mnemonic, "operands": operands,
            "directive": None, "raw": raw}


# ── Branch target extraction ──

# Drop typical prefixes (AT&T immediate `$`), trailing comma, etc.
# NOTE: Don't strip from comma onward — multi-operand branches like
# `cbz r0, .Lend` or `beq $a0, $a1, label` use commas to separate operands.


def _extract_branch_target(operands: str) -> str:
    """Extract the target label from branch operands.

    Handles:
      - x86 Intel:   `jmp foo`
      - x86 AT&T:    `jmp foo`  (also `jmp *%rax` → returns '' for indirect)
      - ARM:         `b foo` or `b.eq foo`
      - cbz/tbz:     `cbz x0, foo`  (last operand)
      - MIPS/RISC-V: `beq $a0, $a1, foo`  (last operand)

    Returns the bare label name, or empty string for computed/indirect jumps.
    """
    if not operands:
        return ""
    op = operands.strip()
    if not op:
        return ""

    # For multi-operand branches, the label is the LAST comma-separated token.
    tokens = [t.strip() for t in op.split(",")]
    target = tokens[-1] if tokens else op

    # Strip AT&T-style indirect/immediate prefixes
    target = target.lstrip("$*")

    # If it starts with '%' (AT&T register) or '[' (Intel memory), it's an
    # indirect/computed jump — we cannot resolve the target.
    if not target or target[0] in ("%", "[", "(", "{"):
        return ""

    # Strip any trailing operand artifacts
    target = target.split()[0] if target else ""

    # Reject pure register names (very common short ones) → indirect
    _REG_NAMES = {
        "rax", "rbx", "rcx", "rdx", "rsi", "rdi", "rsp", "rbp",
        "r8", "r9", "r10", "r11", "r12", "r13", "r14", "r15",
        "eax", "ebx", "ecx", "edx", "esi", "edi", "esp", "ebp",
        "ax", "bx", "cx", "dx", "si", "di", "sp", "bp",
        "lr", "pc", "sp",
    }
    if target.lower() in _REG_NAMES:
        return ""
    if re.match(r"^[xwrb]\d+$", target.lower()):  # ARM/AArch64 reg
        return ""

    # Numeric local labels (e.g. AT&T `1f`/`1b`, GAS `.L0`)
    return target


# ── Function detection ──

_PROLOGUE_PATTERNS = (
    re.compile(r"^\s*push\s+%?[er]?bp", re.IGNORECASE),
    re.compile(r"^\s*pushq?\s+%?rbp", re.IGNORECASE),
    re.compile(r"^\s*stp\s+x29\s*,\s*x30", re.IGNORECASE),
    re.compile(r"^\s*sub\s+sp\s*,\s*sp\s*,", re.IGNORECASE),
    re.compile(r"^\s*addiu?\s+\$?sp", re.IGNORECASE),
    re.compile(r"^\s*addi\s+sp\s*,\s*sp\s*,", re.IGNORECASE),  # RISC-V
)


def _is_local_label(name: str) -> bool:
    """Local labels are typically prefixed with '.' (GAS) or '.L' or are
    purely numeric. They are NOT function entry points."""
    if not name:
        return True
    if name[0].isdigit():
        return True
    if name.startswith("."):
        return True
    return False


# ── Calculator ──

class CognitiveComplexityCalculator:

    def __init__(self, source_code: str):
        self.source_code = source_code
        self.lines = source_code.splitlines()
        self.parsed = [_parse_line(ln) for ln in self.lines]
        self.results = []
        self.details = []

    # ── Helpers ──

    def _add_detail(self, line_no, kind, structural, nesting):
        total = structural + nesting
        if nesting > 0:
            self.details.append(
                f"  Line {line_no:>4}: +{total} ({kind}: "
                f"+{structural} structural, +{nesting} nesting)")
        else:
            self.details.append(f"  Line {line_no:>4}: +{total} ({kind})")

    # ── Function detection ──

    def _find_functions(self):
        """Find function spans in the parsed lines.
        Returns list of (name, start_idx, end_idx) tuples."""
        # Pass 1: collect labels marked global/.globl/.type ... @function
        global_labels = set()
        function_typed = set()
        for i, p in enumerate(self.parsed):
            d = p.get("directive")
            if d in (".global", ".globl"):
                args = p.get("directive_args", "").strip()
                if args:
                    # may be "name1, name2"
                    for n in args.split(","):
                        global_labels.add(n.strip())
            elif d == ".type":
                args = p.get("directive_args", "")
                # ".type foo, @function"
                m = re.match(r"\s*([\w.$]+)\s*,\s*[%@]function", args)
                if m:
                    function_typed.add(m.group(1))

        # Pass 2: walk lines, find function-entry labels
        functions = []
        i = 0
        n = len(self.parsed)
        while i < n:
            p = self.parsed[i]
            label = p.get("label")
            if label and not _is_local_label(label):
                is_func = False
                if label in global_labels or label in function_typed:
                    is_func = True
                else:
                    # Check next few lines for prologue pattern
                    for j in range(i, min(i + 4, n)):
                        raw = self.parsed[j].get("raw", "")
                        if any(pat.search(raw) for pat in _PROLOGUE_PATTERNS):
                            is_func = True
                            break
                    # Or accept any top-level label as a function
                    if not is_func:
                        is_func = True

                if is_func:
                    # Find end: next ret instruction or next function label
                    end = i
                    for j in range(i + 1, n):
                        pj = self.parsed[j]
                        # Stop at next function-entry label
                        lj = pj.get("label")
                        if lj and not _is_local_label(lj):
                            if lj in global_labels or lj in function_typed:
                                end = j - 1
                                break
                            # Prologue check
                            if any(pat.search(self.parsed[k].get("raw", ""))
                                   for k in range(j, min(j + 4, n))
                                   for pat in _PROLOGUE_PATTERNS):
                                end = j - 1
                                break
                        # Stop at ret
                        mn = pj.get("mnemonic") or ""
                        if _is_likely_return(mn, pj.get("operands", "")):
                            end = j
                            break
                        end = j
                    functions.append((label, i, end))
                    i = end + 1
                    continue
            i += 1

        return functions

    # ── Label index ──

    def _build_label_index(self, start, end):
        """Map label name → line index, restricted to [start, end]."""
        idx = {}
        for i in range(start, end + 1):
            label = self.parsed[i].get("label")
            if label:
                idx[label] = i
        return idx

    # ── Main analysis ──

    def calculate(self):
        self.results = []
        functions = self._find_functions()

        if not functions:
            # Treat the entire file as one anonymous function
            n = len(self.parsed)
            if n > 0:
                self._analyze_function("<top-level>", 0, n - 1)
            return self.results

        for name, start, end in functions:
            self._analyze_function(name, start, end)
        return self.results

    def _analyze_function(self, name, start, end):
        self.details = []
        labels = self._build_label_index(start, end)

        # Pre-compute loop spans and loop exits BEFORE logical sequence
        # detection so we can exclude loop-exit conditional jumps from
        # being classified as logical-sequence members.
        loop_spans = self._compute_loop_spans(start, end, labels)
        loop_exits = self._find_loop_exits(start, end, labels, loop_spans)

        # Pass 1: classify each branch and determine its "scope" span.
        # A scope is a (start_line, end_line) range during which nesting is
        # incremented. We open a scope when entering a structural construct
        # and close it at the merge point.
        events = []  # list of (line_idx, kind, target_idx, span_end_idx)

        # Detect short-circuit logical sequences first.
        # Heuristic: if multiple consecutive `compare → cond_jump` pairs
        # all branch to the same label, treat them as a logical sequence.
        # (Each additional jump after the first is +1 fundamental.)
        # NOTE: Loop-exit conditional jumps are excluded — they're not
        # logical operator sequences, they're loop termination checks.
        logical_sequence_jumps = set()  # line indices that are part of seq

        i = start
        while i <= end:
            if i in loop_exits:
                i += 1
                continue
            p = self.parsed[i]
            mn = p.get("mnemonic")
            if mn and _is_cond_jump(mn):
                tgt = _extract_branch_target(p.get("operands", ""))
                if tgt and tgt in labels:
                    # Look back for compare; look forward for additional
                    # cmp+jcc to the same target
                    seq = [i]
                    j = i + 1
                    while j <= end:
                        # Skip blank/label/directive lines
                        pj = self.parsed[j]
                        mnj = pj.get("mnemonic")
                        if mnj is None:
                            j += 1
                            continue
                        if _is_compare(mnj):
                            # Look for the next cond jump
                            k = j + 1
                            while k <= end:
                                pk = self.parsed[k]
                                mnk = pk.get("mnemonic")
                                if mnk is None:
                                    k += 1
                                    continue
                                if _is_cond_jump(mnk) and k not in loop_exits:
                                    tgtk = _extract_branch_target(
                                        pk.get("operands", ""))
                                    if tgtk == tgt:
                                        seq.append(k)
                                        j = k + 1
                                        break
                                # Different jump or other instruction breaks the seq
                                break
                            else:
                                break
                            if seq[-1] != k:
                                break
                            continue
                        break
                    if len(seq) >= 2:
                        # All but the first are sequence members
                        for s in seq[1:]:
                            logical_sequence_jumps.add(s)
            i += 1

        # Pass 2: classify branches and detect "skip-the-else" patterns.
        # An unconditional `jmp X` immediately preceding a label that is
        # itself the target of a forward conditional jump is the classic
        # "end of if-then, jump over the else" pattern.

        # First find all forward cond jump targets (so we can recognize
        # else-skip patterns).
        forward_if_targets = {}  # target_line_idx → branch_line_idx
        for i in range(start, end + 1):
            p = self.parsed[i]
            mn = p.get("mnemonic")
            if mn and _is_cond_jump(mn):
                tgt = _extract_branch_target(p.get("operands", ""))
                if tgt and tgt in labels:
                    tgt_idx = labels[tgt]
                    if tgt_idx > i:
                        forward_if_targets.setdefault(tgt_idx, i)

        # Identify lines that are unconditional `jmp X` where X is past
        # the next label, AND the label being passed-over is itself a
        # forward-cond-jump target. These are "else" markers; the
        # forward cond jump target then represents the start of the else
        # body, and the jmp's own target is the merge point.
        else_jumps = {}  # line_idx → (else_start_idx, merge_idx)
        for i in range(start, end + 1):
            p = self.parsed[i]
            mn = p.get("mnemonic")
            if not mn or not _is_uncond_jump(mn, p.get("operands", "")):
                continue
            tgt = _extract_branch_target(p.get("operands", ""))
            if not tgt or tgt not in labels:
                continue
            merge_idx = labels[tgt]
            if merge_idx <= i:
                continue  # backward — that's a goto, not else
            # Look at the next non-blank line. If it's a label that is a
            # forward-conditional-jump target, this is "skip the else".
            next_label_idx = None
            for j in range(i + 1, min(merge_idx, end + 1)):
                if self.parsed[j].get("label"):
                    next_label_idx = j
                    break
            if (next_label_idx is not None
                    and next_label_idx in forward_if_targets):
                # This jmp is an "else" marker
                else_jumps[i] = (next_label_idx, merge_idx)

        # Pass 3: walk linearly, maintaining a stack of "open scopes" and
        # producing the cognitive complexity events with proper nesting.
        complexity = 0
        scope_stack = []  # list of (close_line_idx, kind)

        def current_nesting():
            return len(scope_stack)

        def close_scopes_at(line_idx):
            """Pop any scopes whose close line is reached."""
            while scope_stack and scope_stack[-1][0] <= line_idx:
                scope_stack.pop()

        for i in range(start, end + 1):
            close_scopes_at(i)
            p = self.parsed[i]
            mn = p.get("mnemonic")
            if not mn:
                continue
            line_no = i + 1

            # Skip lines marked as logical sequence members; they're added
            # below as a separate fundamental increment.
            if i in logical_sequence_jumps:
                complexity += 1
                self._add_detail(line_no, "logical sequence", 1, 0)
                continue

            if _is_cond_jump(mn):
                tgt = _extract_branch_target(p.get("operands", ""))
                if tgt and tgt in labels:
                    tgt_idx = labels[tgt]
                    nest = current_nesting()
                    if tgt_idx <= i:
                        # Backward → loop
                        complexity += 1 + nest
                        self._add_detail(line_no, "loop", 1, nest)
                        # Loop scope: from the loop target back-edge to here.
                        # We've already passed it, so we don't push a new scope
                        # (loop body is BEFORE this jump). Instead, we should
                        # have opened a scope at the target. Handle that with
                        # a one-pass pre-scan below.
                        # For now, treat the loop body retroactively by not
                        # opening a scope here; nesting for the loop body
                        # was already in effect via the second pass below.
                    else:
                        # Forward → if
                        complexity += 1 + nest
                        self._add_detail(line_no, "if", 1, nest)
                        # Open an if scope until the target line
                        scope_stack.append((tgt_idx, "if"))
                else:
                    # Indirect/computed cond jump → treat as goto
                    complexity += 1
                    self._add_detail(line_no, "goto (computed)", 1, 0)
                continue

            if _is_uncond_jump(mn, p.get("operands", "")):
                if i in else_jumps:
                    # else marker: +1 hybrid (no nesting penalty)
                    complexity += 1
                    self._add_detail(line_no, "else", 1, 0)
                    # Pop the if scope (we're at the end of the then body)
                    # and push an else scope until merge
                    if scope_stack and scope_stack[-1][1] == "if":
                        scope_stack.pop()
                    _, merge_idx = else_jumps[i]
                    scope_stack.append((merge_idx, "else"))
                    continue
                # Plain unconditional jump → goto fundamental
                tgt = _extract_branch_target(p.get("operands", ""))
                if tgt and tgt in labels:
                    complexity += 1
                    self._add_detail(line_no, "goto", 1, 0)
                else:
                    complexity += 1
                    self._add_detail(line_no, "goto (computed)", 1, 0)
                continue

        # We undercount loop body nesting in the linear pass because the
        # backward jump's "scope" extends backward, not forward. Fix this
        # by recomputing in a second pass that uses both forward (if) scopes
        # and backward (loop) spans.
        if loop_spans or loop_exits:
            extra_penalty = self._recompute_with_loops(
                start, end, labels, loop_spans, logical_sequence_jumps,
                else_jumps, loop_exits)
            complexity = extra_penalty["total"]
            self.details = extra_penalty["details"]

        self.results.append({
            "function": name,
            "complexity": complexity,
            "start_line": start + 1,
            "end_line": end + 1,
            "details": list(self.details),
        })

    def _compute_loop_spans(self, start, end, labels):
        """Find all loop spans in the function.

        A loop span is identified by a backward jump (conditional or
        unconditional). Returns list of (target_line, branch_line, branch_kind)
        where branch_kind is 'cond' or 'uncond'.
        """
        spans = []
        for i in range(start, end + 1):
            p = self.parsed[i]
            mn = p.get("mnemonic")
            if not mn:
                continue
            is_cond = _is_cond_jump(mn)
            is_uncond = _is_uncond_jump(mn, p.get("operands", ""))
            if not (is_cond or is_uncond):
                continue
            tgt = _extract_branch_target(p.get("operands", ""))
            if not tgt or tgt not in labels:
                continue
            tgt_idx = labels[tgt]
            if tgt_idx <= i:
                spans.append((tgt_idx, i, "cond" if is_cond else "uncond"))
        return spans

    def _find_loop_exits(self, start, end, labels, loop_spans):
        """For each unconditional-backward-jump loop, identify the matching
        forward conditional jump that exits the loop.

        Pattern (while loop):
            .Ltop:           <- target of backward jmp
                cmp ...
                je .Lend     <- forward cond jump TO the line right after
                ...               the backward jmp = loop exit
                jmp .Ltop    <- backward uncond jump
            .Lend:           <- exit point

        Heuristic: only the FIRST conditional jump immediately following
        the loop entry label (skipping setup like cmp/test) is the loop
        exit. Later conditional jumps to the same exit label are `break`
        statements and should be counted as if-statements with break.

        Returns set of line indices that are loop-exit conditional jumps
        and should NOT be counted as separate ifs.
        """
        exits = set()
        for tgt_idx, branch_idx, kind in loop_spans:
            if kind != "uncond":
                continue
            # The exit label is the line right AFTER the backward jmp.
            exit_label_idx = None
            for j in range(branch_idx + 1, end + 1):
                if self.parsed[j].get("label"):
                    exit_label_idx = j
                    break
                if self.parsed[j].get("mnemonic"):
                    break
            if exit_label_idx is None:
                continue
            # Find the FIRST conditional jump after loop entry (tgt_idx)
            # that targets exit_label_idx. Stop scanning at the first
            # conditional jump regardless of target — only the immediate
            # condition check counts as the loop exit.
            for k in range(tgt_idx + 1, branch_idx):
                pk = self.parsed[k]
                mnk = pk.get("mnemonic")
                if not mnk:
                    continue
                if _is_cond_jump(mnk):
                    tgtk = _extract_branch_target(pk.get("operands", ""))
                    if tgtk and labels.get(tgtk) == exit_label_idx:
                        exits.add(k)
                    # Either way, stop after the first cond jump —
                    # subsequent ones are break/continue, not loop exits.
                    break
        return exits

    def _line_loop_depth(self, line_idx, loop_spans):
        """How many loop bodies enclose this line."""
        return sum(1 for s, e, _ in loop_spans if s <= line_idx <= e)

    def _recompute_with_loops(self, start, end, labels, loop_spans,
                              logical_sequence_jumps, else_jumps,
                              loop_exits):
        """Re-walk producing accurate complexity/details accounting for both
        forward (if) scopes AND backward (loop) spans."""
        details = []
        complexity = 0

        scope_stack = []

        # Pre-compute the "exit labels" of all loops — labels that mark
        # the line immediately after a loop's backward edge. Forward
        # conditional jumps to these labels from inside the loop body are
        # break statements: they get +1 (if) but do NOT open an if-scope
        # (because their consequence is just the jump itself).
        loop_exit_labels = set()
        for tgt_idx, branch_idx, _ in loop_spans:
            for j in range(branch_idx + 1, end + 1):
                pj = self.parsed[j]
                if pj.get("label"):
                    loop_exit_labels.add(j)
                    break
                if pj.get("mnemonic"):
                    break

        def add_detail(line_no, kind, structural, nesting):
            total = structural + nesting
            if nesting > 0:
                details.append(
                    f"  Line {line_no:>4}: +{total} ({kind}: "
                    f"+{structural} structural, +{nesting} nesting)")
            else:
                details.append(f"  Line {line_no:>4}: +{total} ({kind})")

        def current_nesting(line_idx):
            return len(scope_stack) + self._line_loop_depth(line_idx, loop_spans)

        def is_break_jump(line_idx, target_idx):
            """A forward conditional jump is a 'break' if its target is
            a loop exit label AND the jump is inside the corresponding
            loop body (but is not the loop's own primary exit, which is
            already in loop_exits)."""
            if target_idx not in loop_exit_labels:
                return False
            # Must be inside SOME loop span that exits at target_idx
            for tgt_idx, branch_idx, _ in loop_spans:
                if tgt_idx <= line_idx <= branch_idx:
                    # Check this loop's exit label matches target_idx
                    for j in range(branch_idx + 1, end + 1):
                        pj = self.parsed[j]
                        if pj.get("label"):
                            if j == target_idx:
                                return True
                            break
                        if pj.get("mnemonic"):
                            break
            return False

        for i in range(start, end + 1):
            # Pop if-scopes whose close line is reached
            while scope_stack and scope_stack[-1][0] <= i:
                scope_stack.pop()

            p = self.parsed[i]
            mn = p.get("mnemonic")
            if not mn:
                continue
            line_no = i + 1

            if i in logical_sequence_jumps:
                complexity += 1
                add_detail(line_no, "logical sequence", 1, 0)
                continue

            # Loop-exit conditional jumps are absorbed into the loop and
            # not counted separately.
            if i in loop_exits:
                continue

            if _is_cond_jump(mn):
                tgt = _extract_branch_target(p.get("operands", ""))
                if tgt and tgt in labels:
                    tgt_idx = labels[tgt]
                    if tgt_idx <= i:
                        # Backward conditional → loop. Use full nesting
                        # (loop depth + open if scopes), minus 1 for self.
                        nest = current_nesting(i) - 1
                        if nest < 0:
                            nest = 0
                        complexity += 1 + nest
                        add_detail(line_no, "loop", 1, nest)
                    else:
                        # Forward → if. Check for break-style.
                        nest = current_nesting(i)
                        complexity += 1 + nest
                        add_detail(line_no, "if", 1, nest)
                        if not is_break_jump(i, tgt_idx):
                            scope_stack.append((tgt_idx, "if"))
                        # break-style: don't open a scope (the "consequence"
                        # is just the implicit jump itself)
                else:
                    complexity += 1
                    add_detail(line_no, "goto (computed)", 1, 0)
                continue

            if _is_uncond_jump(mn, p.get("operands", "")):
                tgt = _extract_branch_target(p.get("operands", ""))
                if tgt and tgt in labels:
                    tgt_idx = labels[tgt]
                    if tgt_idx <= i:
                        # Backward unconditional → loop back-edge.
                        nest = current_nesting(i) - 1
                        if nest < 0:
                            nest = 0
                        complexity += 1 + nest
                        add_detail(line_no, "loop", 1, nest)
                        continue
                if i in else_jumps:
                    complexity += 1
                    add_detail(line_no, "else", 1, 0)
                    if scope_stack and scope_stack[-1][1] == "if":
                        scope_stack.pop()
                    _, merge_idx = else_jumps[i]
                    scope_stack.append((merge_idx, "else"))
                    continue
                if tgt and tgt in labels:
                    complexity += 1
                    add_detail(line_no, "goto", 1, 0)
                else:
                    complexity += 1
                    add_detail(line_no, "goto (computed)", 1, 0)
                continue

        return {"total": complexity, "details": details}


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
            if fname.endswith((".s", ".S", ".asm")):
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
    print("Assembly Cognitive Complexity Calculator")
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