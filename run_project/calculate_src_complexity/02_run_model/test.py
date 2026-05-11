"""
RCA 테스트용 샘플 파일.
다양한 cognitive complexity 패턴을 의도적으로 포함.
"""


# ============================================================
# 1. 단순 함수 (cognitive = 0)
# ============================================================
def simple_add(a, b):
    """제어 흐름 없음 → cognitive 0"""
    return a + b


# ============================================================
# 2. 단일 if (cognitive = 1)
# ============================================================
def is_positive(x):
    if x > 0:           # +1
        return True
    return False


# ============================================================
# 3. 중첩 if (nesting penalty 확인용)
# ============================================================
def nested_check(x, y):
    if x > 0:               # +1
        if y > 0:           # +2 (nesting)
            if x > y:       # +3 (nesting)
                return "x bigger"
            return "y bigger or equal"
    return "non-positive"


# ============================================================
# 4. 논리 연산자 시퀀스 (cognitive = 1 per sequence)
# ============================================================
def logical_ops(a, b, c, d):
    # 연속된 같은 연산자는 +1로 합산되는지 확인
    if a and b and c and d:     # +1 (if) +1 (and chain) = +2
        return 1
    if a or b or c:             # +1 (if) +1 (or chain) = +2
        return 2
    if a and b or c and d:      # +1 (if) +2 (mixed)   = +3
        return 3
    return 0


# ============================================================
# 5. 반복문 + break/continue
# ============================================================
def loop_with_breaks(items):
    result = []
    for item in items:                # +1
        if item is None:              # +2 (nesting)
            continue                  # +1
        if item < 0:                  # +2 (nesting)
            break                     # +1
        result.append(item)
    return result


# ============================================================
# 6. while + 중첩 for + try/except
# ============================================================
def complex_processing(data):
    i = 0
    while i < len(data):              # +1
        try:                          # +1
            for item in data[i]:      # +2 (nesting)
                if item % 2 == 0:     # +3 (nesting)
                    print(item)
                else:                 # +1
                    print(-item)
        except (TypeError, ValueError):  # +2 (nesting)
            pass
        i += 1
    return i


# ============================================================
# 7. 재귀 함수 (recursion +1)
# ============================================================
def factorial(n):
    if n <= 1:           # +1
        return 1
    return n * factorial(n - 1)   # +1 (recursion)


# ============================================================
# 8. 클래스 + 메서드 (메서드별로 별도 측정되는지 확인)
# ============================================================
class DataProcessor:
    """클래스 단위로 묶이는지, 메서드별로 분리되는지 확인용"""

    def __init__(self, threshold):
        self.threshold = threshold
        self.history = []

    def process(self, items):
        """중간 복잡도 메서드"""
        results = []
        for item in items:                    # +1
            if item > self.threshold:         # +2 (nesting)
                if item % 2 == 0:             # +3 (nesting)
                    results.append(item * 2)
                else:                         # +1
                    results.append(item * 3)
            elif item < 0:                    # +1
                results.append(0)
        return results

    def validate(self, x):
        """단순 메서드"""
        return x is not None and x > 0        # +1 (and)


# ============================================================
# 9. 중첩 함수 / 클로저 (parent-child 카운트 검증용)
# ============================================================
def outer_function(items):
    """outer의 cognitive.sum이 inner까지 합산되는지 확인"""
    total = 0

    def inner_filter(x):
        if x > 0:                # +1 (inner 기준)
            if x % 2 == 0:       # +2 (nesting)
                return True
        return False

    for item in items:           # +1 (outer 기준)
        if inner_filter(item):   # +2 (nesting)
            total += item
    return total


# ============================================================
# 10. 매우 복잡한 함수 (high cognitive)
# ============================================================
def very_complex(matrix, mode):
    """일부러 복잡하게 - cognitive 15+ 예상"""
    result = []
    if mode == "filter":                          # +1
        for row in matrix:                        # +2
            for val in row:                       # +3
                if val is not None:               # +4
                    if val > 0 and val < 100:     # +5 + 1 (and)
                        result.append(val)
                    elif val < 0:                 # +1
                        result.append(-val)
    elif mode == "sum":                           # +1
        for row in matrix:                        # +2
            s = 0
            for val in row:                       # +3
                if val:                           # +4
                    s += val
            result.append(s)
    else:                                         # +1
        result = matrix
    return result


# ============================================================
# 11. switch 유사 (Python의 dict dispatch는 cognitive 안 잡힘)
# ============================================================
def dispatch_handler(action, value):
    """Python엔 switch 없지만 elif 체인으로 흉내"""
    if action == "add":          # +1
        return value + 1
    elif action == "sub":        # +1
        return value - 1
    elif action == "mul":        # +1
        return value * 2
    elif action == "div":        # +1
        return value / 2
    else:                        # +1
        return value


if __name__ == "__main__":
    print(simple_add(1, 2))
    print(nested_check(5, 3))
    print(very_complex([[1, 2], [3, -1]], "filter"))