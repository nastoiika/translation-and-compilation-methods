def add(a, b):
    result = a + b
    return result

def mult(a, b):
    result = a * b
    return result

def main():
    x = 10
    y = 20

    z = x * 2 + y / 5
    q = (x + y) * 3

    if z > 15 and x < y:
        print("Condition true")
    else:
        print("Condition false")

    if q > z:
        print("Condition true")
    else:
        print("Condition false")
        
    for i in range(3):
        print(add(i, z))

    for i in range(5):
        print(mult(i, q))
