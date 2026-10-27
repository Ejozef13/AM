def largest_value(numbers):
    best = 0
    for number in numbers:
        if number > best:
            best = number
    return best
