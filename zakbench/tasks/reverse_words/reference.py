def solve(text):
    if text == "":
        return ""
    words = text.split(" ")
    words.reverse()
    return " ".join(words)
