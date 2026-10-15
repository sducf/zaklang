def solve(text):
    result = {}
    if text == "":
        return result
    for pair in text.split(","):
        key, value = pair.split("=")
        result[key] = int(value)
    return result
