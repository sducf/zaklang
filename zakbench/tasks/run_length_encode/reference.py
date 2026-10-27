def solve(text):
    result = ""
    i = 0
    while i < len(text):
        j = i
        while j < len(text) and text[j] == text[i]:
            j += 1
        result += text[i] + str(j - i)
        i = j
    return result
