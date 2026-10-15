def solve(text):
    closers = {")": "(", "]": "[", "}": "{"}
    stack = []
    for char in text:
        if char in closers:
            if not stack or stack.pop() != closers[char]:
                return False
        else:
            stack.append(char)
    return not stack
