def solve(text):
    if text == "":
        return ""
    words = []
    for word in text.split(" "):
        words.append(word[:1].upper() + word[1:].lower())
    return " ".join(words)
