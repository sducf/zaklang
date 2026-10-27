def solve(times):
    total = 0
    for time in times:
        hours, minutes = time.split(":")
        total += int(hours) * 60 + int(minutes)
    return total
