#include <iostream>
using namespace std;

int main() {
    int count;
    int calc;

    int king = 1;
    int queen = 1;
    int rook = 2;
    int bishop = 2;
    int knight = 2;
    int pawn = 8;

    for (int i = 1; i <= 6; i++) {
        cin >> count;
        if (i == 1) {
            calc = king - count;
        } else if (i == 2) {
            calc = queen - count;
        } else if (i == 3) {
            calc = rook - count;
        } else if (i == 4) {
            calc = bishop - count;
        } else if (i == 5) {
            calc = knight - count;
        } else {
            calc = pawn - count;
        }

        cout << calc << " ";
    }
}
