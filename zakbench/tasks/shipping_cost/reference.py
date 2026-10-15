def solve(weight_kg, express, member):
    cost = 500 + 125 * (weight_kg - 1)
    if express:
        cost += 1000
    if member:
        cost //= 2
    return cost
