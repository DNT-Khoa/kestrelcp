# Competitive Programming

Solutions organized by platform. Each problem lives in its own folder with its solution and test cases.

## Directory Structure

```
competitive-programming/
├── kattis/
│   └── problem-name/
│       ├── solution.cpp   ← C++ solution (or solution.py for Python)
│       ├── 1.in           ← sample input (from problem page)
│       ├── 1.out          ← expected output (from problem page)
│       └── 2.in / 2.out   ← add more test cases as needed
├── codeforces/
├── leetcode/
├── new.py                 ← scaffold a new problem (auto-fetches sample tests)
├── test.py                ← compile/run and verify your solution
└── template.cpp           ← C++ starter template (reference)
```

## Starting a New Problem

Run `new.py` with the platform, problem name, and optionally a URL to auto-fetch sample tests:

```bash
# Scaffold only (empty test files)
./new.py kattis oddecho
./new.py leetcode two-sum
./new.py codeforces 1A

# Scaffold + auto-fetch sample input/output from the problem page
./new.py kattis oddecho https://open.kattis.com/problems/oddecho
./new.py codeforces 1A https://codeforces.com/problemset/problem/1/A
```

Auto-fetch is supported for **Kattis** and **Codeforces**. For LeetCode (which doesn't expose test cases in static HTML), the script creates empty `1.in` / `1.out` files for you to paste manually.

**Then:**
1. Write your solution in `solution.cpp` (C++) or `solution.py` (Python)
2. Run the tests (see below)

To add more test cases, just create `2.in` + `2.out`, `3.in` + `3.out`, etc. — the test script picks them all up automatically.

## Testing Your Solution

```bash
./test.py kattis oddecho
./test.py codeforces 1A
```

The script auto-detects the language (Python takes priority over C++ if both exist):
- **Python** (`solution.py`): runs directly with `python3`
- **C++** (`solution.cpp`): compiles with `g++ -O2 -std=c++20`, then runs the binary

In both cases it will:
1. Run against every `*.in` file in the problem folder
2. Compare the output to the matching `*.out` file
3. Report PASS / FAIL, and show a diff on failure

Example output:
```
Compiling kattis/oddecho... OK

Test 1: PASS
Test 2: FAIL
  --- expected ---
  hello
  --- actual ---
  world

Results: 1 passed, 1 failed
```

The comparison ignores trailing whitespace and blank lines, so minor formatting differences won't cause false failures. Each test case has a 5-second time limit.

## Scripts Reference

### `new.py <platform> <problem-name> [url]`

Scaffolds a new problem folder:
- Creates `<platform>/<problem-name>/`
- Generates `solution.cpp` from a built-in template
- If a URL is provided, fetches sample input/output from the problem page (Kattis & Codeforces)
- Otherwise creates empty `1.in` and `1.out`
- Requires `requests` and `beautifulsoup4` (`pip3 install requests beautifulsoup4`)

### `test.py <platform> <problem>`

Compiles (C++) or runs (Python) a solution and tests it:
- Auto-detects `solution.py` or `solution.cpp` (Python takes priority)
- C++: compiles with `g++ -O2 -std=c++20 -Wall`
- Runs against all `*.in` files and compares to `*.out`
- Shows a diff on failure
- Exits with code 0 if all tests pass, 1 if any fail
- Supports tab completion for platform and problem name (see Shell Setup below)

## Shell Setup (Tab Completion)

Both scripts support tab completion for platform and problem name. Add this to your `~/.zshrc`:

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

Then reload: `source ~/.zshrc`

## CLion / IDE Setup

`CMakeLists.txt` auto-discovers every `solution.cpp` in the repo and creates a separate build target for each one, named `<platform>_<problem>` (e.g., `kattis_oddecho`).

After adding a new problem, reload CMake in CLion:
**Tools → CMake → Reload CMake Project**

You can then select and run any target from the toolbar to build/debug it inside the IDE.
