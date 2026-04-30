#include <iostream>

using namespace std;

int main() {
    int N;
    cin >> N;

    string echo;
    for (int i = 1; i <= N; i++) {
        cin >> echo;
        if (i % 2 != 0) {
            cout << echo << endl;
        }
    }
}