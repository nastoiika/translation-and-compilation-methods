# Однострочный комментарий

"""
Многострочный комментарий
"""

def add(a, b):
    result = a + b
    return result

def mult(a, b):
    result = a * b
    return result

def main():
    x = 10
    y = 20

    # арифметическое выражение
    z = x * 2 + y / 5
    q = (x + y) * 3

    # логическое выражение
    if z > 15 and x < y:
        print("Condition true")
    else:
        print("Condition false")

    # логическое выражение
    if q > z:
        print("Condition true")
    else:
        print("Condition false")
        
    
    # цикл
    for i in range(3):
        print(add(i, z)) # вызов функции

     # цикл
    for i in range(5):
        print(mult(i, q)) # вызов функции
