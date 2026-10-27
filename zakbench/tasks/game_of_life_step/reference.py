def solve(grid):
    rows = len(grid)
    result = []
    for r in range(rows):
        cols = len(grid[r])
        row = []
        for c in range(cols):
            neighbors = 0
            for nr in range(r - 1, r + 2):
                for nc in range(c - 1, c + 2):
                    if (nr, nc) != (r, c) and 0 <= nr < rows and 0 <= nc < cols:
                        neighbors += grid[nr][nc]
            alive = grid[r][c] == 1
            row.append(1 if neighbors == 3 or (alive and neighbors == 2) else 0)
        result.append(row)
    return result
