#include <iostream>
double add(double a, double b) {
double result = a + b;
return result;
}
double mult(double a, double b) {
double result = a * b;
return result;
}
int main() {
double x = 10;
double y = 20;
double z = x * 2 + y / 5;
double q = (x + y) * 3;
if (z > 15 && x < y) {
std::cout << "Condition true" << std::endl;
} else {
std::cout << "Condition false" << std::endl;
}
if (q > z) {
std::cout << "Condition true" << std::endl;
} else {
std::cout << "Condition false" << std::endl;
}
for (int i = 0; i < 3; i++) {
std::cout << add(i, z) << std::endl;
}
for (int i = 0; i < 5; i++) {
std::cout << mult(i, q) << std::endl;
}
return 0;
}
