#include <iostream>
using namespace std;

int main() {
    int num;
    cin >> num;

    int firstDigit = num / 10;
    int secondDigit = num % 10;
    cout << secondDigit * 10 + firstDigit;
}
