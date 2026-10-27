def solve(nums):
    if not nums:
        return 0
    best = nums[0]
    current = 0
    for n in nums:
        current = max(n, current + n)
        best = max(best, current)
    return best
