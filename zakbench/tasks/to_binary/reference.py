def solve(n):
    if n == 0:
        return "0"
    digits = ""
    while n > 0:
        digits = str(n % 2) + digits
        n //= 2
    return digits
