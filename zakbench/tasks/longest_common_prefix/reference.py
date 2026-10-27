def solve(words):
    if not words:
        return ""
    prefix = words[0]
    for word in words:
        while not word.startswith(prefix):
            prefix = prefix[:-1]
    return prefix
