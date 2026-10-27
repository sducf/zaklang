def solve(nums):
    result = []
    total = 0
    for n in nums:
        total += n
        result.append(total)
    return result
