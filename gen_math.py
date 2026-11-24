"""1-11 sinflar uchun Matematika savollarini avtomatik yaratadi.

Ishlatish:  python gen_math.py
Natija:     questions/1_math.json ... questions/11_math.json (har biri 100 ta savol)
Savollar til talab qilmaydigan (raqam/belgi) ko'rinishda, shuning uchun 3 tilda bir xil.
"""
import json
import random
from pathlib import Path

random.seed(2026)
OUT = Path(__file__).parent / "questions"
OUT.mkdir(exist_ok=True)


def make_options(ans: int) -> list[str]:
    s = {ans}
    while len(s) < 4:
        d = random.choice([-10, -5, -3, -2, -1, 1, 2, 3, 5, 10, 11, -11])
        s.add(ans + d)
    opts = [str(ans)] + [str(x) for x in s if x != ans]
    return opts[:4]  # birinchisi to'g'ri javob


def g1():
    a = random.randint(1, 19)
    if random.random() < 0.5:
        b = random.randint(1, 20 - a)
        return f"{a} + {b} = ?", a + b
    b = random.randint(1, a)
    return f"{a} − {b} = ?", a - b


def g2():
    if random.random() < 0.5:
        a, b = random.randint(10, 80), random.randint(5, 19)
        return f"{a} + {b} = ?", a + b
    a, b = random.randint(30, 99), random.randint(5, 29)
    return f"{a} − {b} = ?", a - b


def g3():
    r = random.random()
    if r < 0.6:
        a, b = random.randint(2, 9), random.randint(2, 12)
        return f"{a} × {b} = ?", a * b
    a, b = random.randint(100, 600), random.randint(100, 390)
    return f"{a} + {b} = ?", a + b


def g4():
    r = random.random()
    if r < 0.5:
        a, b = random.randint(11, 99), random.randint(3, 9)
        return f"{a} × {b} = ?", a * b
    b, c = random.randint(3, 12), random.randint(5, 30)
    return f"{b * c} ÷ {b} = ?", c


def g5():
    r = random.random()
    if r < 0.5:
        a, b, c = random.randint(2, 12), random.randint(2, 12), random.randint(1, 40)
        return f"{a} × {b} + {c} = ?", a * b + c
    a, b, c = random.randint(2, 20), random.randint(2, 20), random.randint(2, 9)
    return f"({a} + {b}) × {c} = ?", (a + b) * c


def g6():
    r = random.random()
    if r < 0.5:
        p = random.choice([10, 20, 25, 30, 40, 50, 60, 75])
        n = random.choice([20, 40, 60, 80, 100, 120, 160, 200, 240, 400])
        return f"{n} × {p}% = ?", n * p // 100
    a, b = random.randint(1, 30), random.randint(1, 30)
    if random.random() < 0.5:
        return f"{a} + (−{b}) = ?", a - b
    return f"−{a} − {b} = ?", -a - b


def g7():
    x = random.randint(-9, 12)
    a = random.choice([2, 3, 4, 5, 6, 7, 8, 9])
    b = random.randint(-15, 20)
    c = a * x + b
    sign = "+" if b >= 0 else "−"
    return f"{a}x {sign} {abs(b)} = {c},  x = ?", x


def g8():
    r = random.random()
    if r < 0.5:
        n = random.randint(2, 25)
        return f"√{n * n} = ?", n
    a, b = random.randint(5, 30), random.randint(1, 20)
    return f"{a}² − {b}² = ?", a * a - b * b


def g9():
    p, q = random.randint(-9, 9), random.randint(-9, 9)
    s, pr = p + q, p * q
    coef = f"{-s:+d}".replace("+", "+ ").replace("-", "− ")
    const = f"{pr:+d}".replace("+", "+ ").replace("-", "− ")
    eq = f"x² {coef}x {const} = 0"
    k = random.random()
    if k < 0.34:
        return f"{eq},  x₁ + x₂ = ?", s
    if k < 0.67:
        return f"{eq},  x₁ · x₂ = ?", pr
    return f"{eq},  max(x₁, x₂) = ?", max(p, q)


def g10():
    r = random.random()
    if r < 0.5:
        b, k = random.choice([2, 3, 4, 5, 6, 7, 10]), random.randint(1, 6)
        return f"log_{b}({b ** k}) = ?", k
    a, m = random.randint(2, 12), random.randint(2, 5)
    return f"{a}^{m} = ?", a ** m


def g11():
    r = random.random()
    if r < 0.6:
        a, n, c = random.randint(1, 6), random.randint(2, 5), random.randint(1, 4)
        return f"f(x) = {a}x^{n},  f′({c}) = ?", a * n * c ** (n - 1)
    a1, d, n = random.randint(1, 9), random.randint(1, 6), random.randint(5, 20)
    return f"a₁ = {a1}, d = {d},  S_{n} = ?", n * (2 * a1 + (n - 1) * d) // 2


GEN = {1: g1, 2: g2, 3: g3, 4: g4, 5: g5, 6: g6, 7: g7, 8: g8, 9: g9, 10: g10, 11: g11}

for grade, fn in GEN.items():
    seen, items, tries = set(), [], 0
    while len(items) < 100 and tries < 20000:
        tries += 1
        text, ans = fn()
        if text in seen:
            continue
        seen.add(text)
        items.append({"q": text, "o": make_options(ans), "a": 0})
    (OUT / f"{grade}_math.json").write_text(
        json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"{grade}-sinf: {len(items)} ta savol")
