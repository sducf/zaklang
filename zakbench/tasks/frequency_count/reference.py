def solve(items):
    counts = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return counts
