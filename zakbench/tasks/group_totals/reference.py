def solve(names, amounts):
    totals = {}
    for name, amount in zip(names, amounts):
        totals[name] = totals.get(name, 0) + amount
    return totals
