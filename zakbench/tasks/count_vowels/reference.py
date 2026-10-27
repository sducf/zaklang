def solve(text):
    count = 0
    for ch in text.lower():
        if ch in "aeiou":
            count += 1
    return count
