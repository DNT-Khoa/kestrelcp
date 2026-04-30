#include <iomanip>
#include <iostream>
using namespace std;

int main() {
    int h, b;
    cin >> h >> b;
    cout << fixed << setprecision(7) << b * h / 2.0;
}
