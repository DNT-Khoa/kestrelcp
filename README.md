# 🏆 Competitive Programming Playground

Grinding through problems one bug at a time. Solutions organized by platform — each problem has its own folder, solution, and test cases.

![Problems Solved](https://img.shields.io/badge/problems%20solved-getting%20there-brightgreen?style=for-the-badge&logo=target)
![Language](https://img.shields.io/badge/language-C%2B%2B%20only-blue?style=for-the-badge&logo=cplusplus)
![Platform](https://img.shields.io/badge/platform-macOS-lightgrey?style=for-the-badge&logo=apple)
![Mood](https://img.shields.io/badge/mood-caffeinated-orange?style=for-the-badge&logo=coffeescript)

---

## 📁 What's Inside

```
competitive-programming/
├── 🟡 kattis/
│   └── problem-name/
│       ├── solution.cpp   ← the brain
│       ├── 1.in           ← sample input
│       ├── 1.out          ← expected output
│       └── notes.md       ← problem link & thoughts
├── 🔵 codeforces/
├── 🟢 leetcode/
├── 🛠️ new.py              ← scaffold a new problem in seconds
└── 🧪 test.py             ← compile, run, and judge yourself
```

---

## ⚡ Workflow

### 1. Start a new problem

```bash
# With auto-fetch (recommended) — grabs sample tests straight from the page
./new.py kattis oddecho https://open.kattis.com/problems/oddecho
./new.py codeforces 1A https://codeforces.com/problemset/problem/1/A

# Without URL — creates empty test files to fill in manually
./new.py kattis oddecho
./new.py leetcode two-sum
```

> Auto-fetch works for **Kattis** and **Codeforces**. LeetCode gets empty files since it hides test cases in JS.

### 2. Write your solution

Open `solution.cpp` (or `solution.py`) and go to war. 🥊

### 3. Test it

```bash
./test.py kattis oddecho
./test.py codeforces 1A
```

The script compiles with `g++ -O2 -std=c++20` and runs your solution:

```
Compiling kattis/oddecho... OK

Test 1: ✅ PASS
Test 2: ❌ FAIL
  --- expected
  +++ actual
  - hello
  + world

Results: 1 passed, 1 failed
```

Trailing whitespace and blank lines are ignored — no fake failures over formatting. Each test has a 5s limit before it gets the axe. ⏱️

---

## 🛠️ Scripts Reference

| Script | What it does |
|--------|-------------|
| `./new.py <platform> <problem> [url]` | Scaffold a new problem folder + fetch sample tests |
| `./test.py <platform> <problem>` | Compile/run solution and check against all test cases |

**Dependencies for `new.py`:**
```bash
pip3 install requests beautifulsoup4
```

---

## 🐚 Tab Completion (zsh)

Because typing problem names by hand is for quitters. Add to `~/.zshrc`:

```zsh
_cp_test_complete() {
    local dir="/path/to/competitive-programming"
    local state
    _arguments \
        '1:platform:(kattis codeforces leetcode)' \
        '2:problem:->problem'
    case $state in
        problem)
            compadd -- $(ls "$dir/${words[2]}" 2>/dev/null)
            ;;
    esac
}
_cp_new_complete() {
    _arguments '1:platform:(kattis codeforces leetcode)'
}
compdef _cp_test_complete ./test.py test.py
compdef _cp_new_complete ./new.py new.py
```

```bash
source ~/.zshrc
```

---

## 🖥️ CLion Setup

`CMakeLists.txt` auto-discovers every `solution.cpp` and creates a build target for each one (`kattis_oddecho`, `codeforces_1A`, etc.).

After adding a new problem → **Tools → CMake → Reload CMake Project** → pick your target → run. Done.

---
