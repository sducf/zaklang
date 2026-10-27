VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def solve(numeral):
    total = 0
    for i, letter in enumerate(numeral):
        value = VALUES[letter]
        if i + 1 < len(numeral) and value < VALUES[numeral[i + 1]]:
            total -= value
        else:
            total += value
    return total
