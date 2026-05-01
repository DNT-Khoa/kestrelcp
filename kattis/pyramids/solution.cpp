#include <iostream>
using namespace std;

int main() {
    int N;
    cin >> N;

    int height = 1;
    int side = 1;
    N -= 1;

    while (N > 0) {
        side += 2;
        N -= side * side;
        if (N < 0) break;
        height++;
    }

    cout << height << "\n";
}