def solve(pattern, text):
    words = text.split(" ") if text else []
    if len(words) != len(pattern):
        return False
    letter_to_word = {}
    word_to_letter = {}
    for letter, word in zip(pattern, words):
        if letter in letter_to_word:
            if letter_to_word[letter] != word:
                return False
        elif word in word_to_letter:
            return False
        else:
            letter_to_word[letter] = word
            word_to_letter[word] = letter
    return True
