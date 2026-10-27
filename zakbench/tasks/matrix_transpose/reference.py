def solve(grid):
    if not grid:
        return []
    result = []
    for col in range(len(grid[0])):
        result.append([row[col] for row in grid])
    return result
