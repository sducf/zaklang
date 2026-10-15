def solve(events):
    balance = 0
    for event in events:
        action, amount = event.split(" ")
        amount = int(amount)
        if action == "deposit":
            balance += amount
        elif amount <= balance:
            balance -= amount
    return balance
