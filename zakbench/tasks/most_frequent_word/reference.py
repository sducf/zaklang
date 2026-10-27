def solve(text):
    if text == "":
        return ""
    counts = {}
    for word in text.split(" "):
        counts[word] = counts.get(word, 0) + 1
    best = ""
    best_count = 0
    for word, count in counts.items():
        if count > best_count or (count == best_count and word < best):
            best = word
            best_count = count
    return best
