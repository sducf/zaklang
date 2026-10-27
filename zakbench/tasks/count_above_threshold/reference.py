def solve(scores, threshold):
    count = 0
    for score in scores.values():
        if score >= threshold:
            count += 1
    return count
