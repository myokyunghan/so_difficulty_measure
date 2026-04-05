"""
Julia Cognitive Complexity Calculator
Based on Campbell 2018 (ICSE TechDebt '18)
Dependencies: pip install tree-sitter tree-sitter-julia
"""
import os
from tree_sitter import Language, Parser

def create_parser():
    """tree-sitter-language-pack 우선, 개별 패키지 fallback"""
    # 1. tree-sitter-language-pack
    try:
        from tree_sitter_language_pack import get_parser
        return get_parser("julia")
    except Exception:
        pass
    # 2. 개별 패키지
    try:
        import tree_sitter_julia as _mod
        return Parser(Language(_mod.language()))
    except ImportError:
        raise ImportError(
            "Install one of:\n"
            "  pip install tree-sitter-language-pack\n"
            "  pip install tree-sitter-julia")


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
            if ch.type in ("function_definition","short_function_definition"): self._proc(ch)
        return self.results

    def _proc(self, fn):
        # Julia: function name(args) ... end
        # Children: function, signature, body..., end
        name="<anon>"
        for ch in fn.children:
            if ch.type=="signature":
                # signature contains call_expression with function name
                for sub in ch.children:
                    if sub.type in ("call_expression","identifier"):
                        name=self._t(sub).split("(")[0]; break
                break
            elif ch.type=="identifier": name=self._t(ch); break
        self.details=[]
        # Body is inline children between signature and end
        c=0; in_body=False
        for ch in fn.children:
            if ch.type in ("signature","function"): in_body=True; continue
            if ch.type=="end": break
            if in_body: c+=self._v(ch,0)
        self.results.append({"function":name,"complexity":c,"start_line":fn.start_point[0]+1,"end_line":fn.end_point[0]+1,"details":list(self.details)})

    def _vc(self,n,ne):
        t=0
        for ch in n.children: t+=self._v(ch,ne)
        return t
    def _v(self,n,ne):
        t=n.type
        if t=="if_statement": return self._hif(n,ne)
        if t in ("for_statement","while_statement"):
            self._a(n,t.split("_")[0],1,ne); c=1+ne
            body=n.child_by_field_name("body")
            if body: c+=self._vc(body,ne+1)
            else:
                in_body=False; 
                for ch in n.children:
                    if ch.type in ("for","while","in"): in_body=True; continue
                    if ch.type=="end": break
                    if in_body and ch.type not in ("binary_expression","identifier","call_expression","range_expression"):
                        c+=self._v(ch,ne+1)
                    elif in_body and ch.type in ("binary_expression",):
                        # Could be condition for while
                        pass
                # Fallback: visit all non-keyword children
                for ch in n.children:
                    if ch.type not in ("for","while","in","end","do") and ch.child_by_field_name("condition") is None:
                        c+=self._v(ch,ne+1)
            return c
        if t=="try_statement": return self._vc(n,ne)
        if t=="catch_clause":
            self._a(n,"catch",1,ne); c=1+ne
            for ch in n.children:
                if ch.type not in ("catch","identifier"): c+=self._v(ch,ne+1)
            return c
        if t=="finally_clause":
            for ch in n.children:
                if ch.type not in ("finally",): return self._v(ch,ne)
            return 0
        if t=="ternary_expression":
            self._a(n,"ternary",1,ne); return 1+ne
        if t=="binary_expression": return self._hbin(n,ne)
        if t in ("function_expression",):
            return self._vc(n,ne+1)
        return self._vc(n,ne)

    def _hif(self,n,ne):
        c=1+ne; self._a(n,"if",1,ne)
        cond=n.child_by_field_name("condition")
        if cond: c+=self._v(cond,ne)
        # Julia if: children are if, cond, body..., [elseif_clause...], [else_clause], end
        in_body=False
        for ch in n.children:
            if ch.type in ("if",): continue
            if ch==cond: in_body=True; continue
            if ch.type in ("elseif_clause","else_clause","end"): in_body=False
            if in_body: c+=self._v(ch,ne+1)
        for ch in n.children:
            if ch.type=="elseif_clause":
                c+=1; self._a(ch,"elseif",1,0)
                econd=ch.child_by_field_name("condition")
                if econd: c+=self._v(econd,ne)
                ein=False
                for sub in ch.children:
                    if sub==econd: ein=True; continue
                    if sub.type in ("elseif","end"): continue
                    if ein: c+=self._v(sub,ne+1)
            elif ch.type=="else_clause":
                c+=1; self._a(ch,"else",1,0)
                for sub in ch.children:
                    if sub.type not in ("else",): c+=self._v(sub,ne+1)
        return c

    def _hbin(self,n,ne):
        ops=[]; self._cops(n,ops)
        if not ops: return self._vc(n,ne)
        c=0; prev=None
        for op in ops:
            if prev is None or op!=prev: c+=1; self._ar(f"logical sequence '{op}'" if prev is None else f"logical change to '{op}'",1); prev=op
        return c
    def _cops(self,n,ops):
        if n.type!="binary_expression": return
        op=n.child_by_field_name("operator")
        if not op: return
        ot=self._t(op)
        if ot not in ("&&","||"): return
        left=n.child_by_field_name("left")
        if left and left.type=="binary_expression":
            lo=left.child_by_field_name("operator")
            if lo and self._t(lo) in ("&&","||"): self._cops(left,ops)
        ops.append(ot)
        right=n.child_by_field_name("right")
        if right and right.type=="binary_expression":
            ro=right.child_by_field_name("operator")
            if ro and self._t(ro) in ("&&","||"): self._cops(right,ops)

def calculate_file(fp):
    with open(fp,"r",encoding="utf-8") as f: return CognitiveComplexityCalculator(f.read()).calculate()
def calculate_source(code): return CognitiveComplexityCalculator(code).calculate()
def calculate_directory(d):
    r=[]
    for root,_,files in os.walk(d):
        for f in sorted(files):
            if f.endswith(".jl"):
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