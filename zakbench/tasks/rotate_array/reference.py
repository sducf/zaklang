def solve(nums, k):
    n = len(nums)
    if n == 0:
        return []
    k %= n
    return nums[n - k:] + nums[:n - k]
