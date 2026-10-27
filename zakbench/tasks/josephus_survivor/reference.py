def solve(n, k):
    people = list(range(1, n + 1))
    position = 0
    while len(people) > 1:
        position = (position + k - 1) % len(people)
        people.pop(position)
    return people[0]
