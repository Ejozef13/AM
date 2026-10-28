def largest_value(numbers):
    best = numbers[0]
    for number in numbers[1:]:
        if number > best:
            best = number
    return best
