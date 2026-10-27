def solve(coins, amount):
    best = [0] + [-1] * amount
    for value in range(1, amount + 1):
        for coin in coins:
            if coin <= value and best[value - coin] >= 0:
                candidate = best[value - coin] + 1
                if best[value] < 0 or candidate < best[value]:
                    best[value] = candidate
    return best[amount]
