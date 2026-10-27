def solve(n):
    if n < 3:
        return 0
    is_prime = [True] * n
    is_prime[0] = is_prime[1] = False
    i = 2
    while i * i < n:
        if is_prime[i]:
            for multiple in range(i * i, n, i):
                is_prime[multiple] = False
        i += 1
    return sum(is_prime)
