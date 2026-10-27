def solve(nums, target):
    first_seen = {}
    for j, n in enumerate(nums):
        if target - n in first_seen:
            return [first_seen[target - n], j]
        if n not in first_seen:
            first_seen[n] = j
    return []
