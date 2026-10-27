def solve(events):
    stock = {}
    for event in events:
        action, item, quantity = event.split(" ")
        quantity = int(quantity)
        current = stock.get(item, 0)
        if action == "add":
            stock[item] = current + quantity
        else:
            stock[item] = max(0, current - quantity)
    return {item: count for item, count in stock.items() if count > 0}
