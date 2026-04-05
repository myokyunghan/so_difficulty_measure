"""
Haskell Cognitive Complexity Calculator
Based on Campbell 2018 (ICSE TechDebt '18)

Haskell is very different from imperative languages.
Guards (|) are treated as if/else if.
Case expressions are treated as switch.
Pattern matching complexity is counted per guard/case.

Dependencies: pip install tree-sitter tree-sitter-haskell
"""
import os
from tree_sitter import Language, Parser

def create_parser():
    """tree-sitter-language-pack 우선, 개별 패키지 fallback"""
    # 1. tree-sitter-language-pack
    try:
        from tree_sitter_language_pack import get_parser
        return get_parser("haskell")
    except Exception:
        pass
    # 2. 개별 패키지
    try:
        import tree_sitter_haskell as _mod
        return Parser(Language(_mod.language()))
    except ImportError:
        raise ImportError(
            "Install one of:\n"
            "  pip install tree-sitter-language-pack\n"
            "  pip install tree-sitter-haskell")


class CognitiveComplexityCalculator:
    def __init__(self, src):
        self.src=src; self.p = create_parser(); self.tree=self.p.parse(bytes(src,"utf-8"))
        self.results=[]; self.details=[]
    def _t(self,n): return "" if n is None else self.src[n.start_byte:n.end_byte]
    def _l(self,n): return n.start_point[0]+1
    def _a(self,n,k,s,ne):
        l=self._l(n);t=s+ne
        self.details.append(f"  Line {l:>4}: +{t} ({k}: +{s} structural, +{ne} nesting)" if ne else f"  Line {l:>4}: +{t} ({k})")
    def _ar(self,d,i): self.details.append(f"          +{i} ({d})")

    def calculate(self):
        self.results=[]
        for ch in self.tree.root_node.children:
            if ch.type in ("function","bind"):
                self._proc(ch)
            elif ch.type == "declarations":
                for sub in ch.children:
                    if sub.type in ("function","bind"):
                        self._proc(sub)
        return self.results

    def _proc(self, fn):
        nn=fn.child_by_field_name("name")
        name=self._t(nn) if nn else "<anon>"
        self.details=[]
        c=0
        # Haskell function has multiple 'match' children (one per guard group)
        first_guard = True
        for ch in fn.children:
            if ch.type == "match":
                # Each match has: |, guards, =, expression
                for sub in ch.children:
                    if sub.type == "guards":
                        for g in sub.children:
                            if g.type in ("boolean", "guard"):
                                if first_guard:
                                    c += 1; self._a(g, "guard (if)", 1, 0)
                                    first_guard = False
                                else:
                                    c += 1; self._a(g, "guard (else if)", 1, 0)
                                # Check for && || inside guard
                                c += self._v(g, 0)
        self.results.append({"function":name,"complexity":c,"start_line":fn.start_point[0]+1,"end_line":fn.end_point[0]+1,"details":list(self.details)})

    def _vc(self,n,ne):
        t=0
        for ch in n.children: t+=self._v(ch,ne)
        return t
    def _v(self,n,ne):
        t=n.type
        if t=="guards":
            c=0
            first=True
            for ch in n.children:
                if ch.type=="guard":
                    if first: c+=1+ne; self._a(ch,"guard (if)",1,ne); first=False
                    else: c+=1; self._a(ch,"guard (else if)",1,0)
            return c
        if t=="conditional":
            self._a(n,"if-then-else",1,ne); return 1+ne
        if t in ("case","case_expression"):
            self._a(n,"case",1,ne); c=1+ne
            c+=self._vc(n,ne+1)
            return c
        if t=="do":
            return self._vc(n,ne)
        if t in ("lambda","lambda_expression"):
            return self._vc(n,ne+1)
        if t=="infix":
            op=n.child_by_field_name("operator")
            if op and self._t(op) in ("&&","||"):
                ops=[]; self._cops(n,ops)
                if ops:
                    c=0; prev=None
                    for o in ops:
                        if prev is None or o!=prev: c+=1; self._ar(f"logical sequence '{o}'" if prev is None else f"logical change to '{o}'",1); prev=o
                    return c
            return self._vc(n,ne)
        return self._vc(n,ne)

    def _cops(self,n,ops):
        if n.type!="infix": return
        op=n.child_by_field_name("operator")
        if not op: return
        ot=self._t(op)
        if ot not in ("&&","||"): return
        # Left
        children=list(n.children)
        if len(children)>=3:
            left=children[0]; right=children[2]
            if left.type=="infix":
                lo_children=list(left.children)
                if len(lo_children)>=2 and self._t(lo_children[1]) in ("&&","||"):
                    self._cops(left,ops)
            ops.append(ot)
            if right.type=="infix":
                ro_children=list(right.children)
                if len(ro_children)>=2 and self._t(ro_children[1]) in ("&&","||"):
                    self._cops(right,ops)

def calculate_file(fp):
    with open(fp,"r",encoding="utf-8") as f: return CognitiveComplexityCalculator(f.read()).calculate()
def calculate_source(code): return CognitiveComplexityCalculator(code).calculate()
def calculate_directory(d):
    r=[]
    for root,_,files in os.walk(d):
        for f in sorted(files):
            if f.endswith(".hs"):
                p=os.path.join(root,f)
                try: res=calculate_file(p);[x.update(file=p) for x in res];r.extend(res)
                except Exception as e: print(f"Error {p}: {e}")
    return r
def print_results(results, verbose=True):
    total=sum(r["complexity"] for r in results)
    for r in results:
        print(f"\n{'='*60}")
        if r.get("file"): print(f"File: {r['file']}")
        print(f"Function: {r['function']} (lines {r['start_line']}-{r['end_line']})")
        print(f"Cognitive Complexity: {r['complexity']}")
        if verbose:
            for d in r.get("details",[]): print(d)
    print(f"\n{'='*60}\nTotal: {total}, Functions: {len(results)}")
    if results: print(f"Average: {total/len(results):.1f}")