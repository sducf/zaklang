def solve(expr):
    total = 0
    term = 0
    number = 0
    op = "+"
    for ch in expr + "+":
        if ch.isdigit():
            number = number * 10 + int(ch)
            continue
        if op == "*":
            term *= number
        elif op == "+":
            total += term
            term = number
        else:
            total += term
            term = -number
        op = ch
        number = 0
    return total + term
