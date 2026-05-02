# 🏆 Competitive Programming Playground

Grinding through problems one bug at a time. Solutions organized by platform — each problem has its own folder, solution, and test cases.

![Language](https://img.shields.io/badge/language-Java%20only-ED8B00?style=for-the-badge&logo=openjdk&logoColor=white)
![Platform](https://img.shields.io/badge/platform-macOS-9333EA?style=for-the-badge&logo=apple&logoColor=white)
![Mood](https://img.shields.io/badge/mood-caffeinated-D2691E?style=for-the-badge&logo=coffeescript&logoColor=white)

---

## 📁 What's Inside

```
competitive-programming/
├── 🟡 kattis/
│   └── problem-name/
│       ├── Solution.java   ← the brain
│       ├── 1.in            ← sample input
│       ├── 1.out           ← expected output
│       └── notes.md        ← problem link & thoughts
├── 🔵 codeforces/
├── 🟢 leetcode/
├── 🧪 playground/
│   ├── Main.java          ← single-file scratchpad
│   └── run                ← `./run` shortcut (forwards stdin/args to Main)
├── 🛠️ new.py               ← scaffold a new problem in seconds
├── 🧪 test.py              ← compile, run, and judge yourself
└── 🤖 commit.py            ← AI-generated commit messages
```

---

## ⚡ Workflow

### 1. Start a new problem

```bash
# Paste the URL — folder name is derived from the slug, sample tests fetched
./new.py kattis https://open.kattis.com/problems/oddecho
./new.py codeforces https://codeforces.com/problemset/problem/1/A
./new.py leetcode https://leetcode.com/problems/two-sum/

# Slug-only shorthand (leetcode auto-derives URL; kattis/cf just scaffold)
./new.py leetcode two-sum
./new.py kattis oddecho

# Explicit form still works (slug + URL)
./new.py kattis oddecho https://open.kattis.com/problems/oddecho
```

> Auto-fetch works for **Kattis**, **Codeforces**, and **LeetCode** (via its public GraphQL endpoint). For LeetCode, each `.in` file contains one value per parameter on its own line — e.g. for `two-sum`, `1.in` is `[2,7,11,15]\n9` — so your `Solution.main` reads each arg with `sc.nextLine()` and parses the array/value before printing the result in LeetCode's expected format. Premium-only problems and design-style problems (LRU Cache, etc.) won't fit this stdin/stdout model.

### 2. Write your solution

Open `Solution.java` and go to war. 🥊

### 3. Test it

```bash
./test.py kattis oddecho
./test.py codeforces 1A
```

The script compiles with `javac` and runs `java Solution` against every `*.in` / `*.out` pair:

```
Compiling... OK

Test 1: PASS
Test 2: FAIL
  --- expected ---
  hello
  --- actual ---
  world

Results: 1 passed, 1 failed
```

Trailing whitespace and blank lines are ignored — no fake failures over formatting. Each test has a 5s limit before it gets the axe. ⏱️

### 4. Commit your solution

Stage your changes, then let Claude write the commit message:

```bash
git add kattis/oddecho/Solution.java
./commit.py
```

Claude analyzes the diff and suggests a [Conventional Commit](https://www.conventionalcommits.org/) message with an emoji prefix:

```
  ✨ feat(kattis): solve oddecho with word index filtering

Commit with this message? [Y/n/e]
```

| Key | Action |
|-----|--------|
| `y` / Enter | Commit with the suggested message |
| `n` | Abort |
| `e` | Edit the suggestion in place, then press Enter to commit |

Keys are case-insensitive.

**Emoji legend:**

| Emoji | Type | When to use |
|-------|------|-------------|
| ✨ | `feat` | New solution or feature |
| 🐛 | `fix` | Bug fix in a solution |
| 📝 | `docs` | README or notes update |
| ♻️ | `refactor` | Rewrite without changing behavior |
| ✅ | `test` | Adding or fixing test cases |
| 🔧 | `chore` | Tooling, config, scripts |
| ⚡️ | `perf` | Performance improvement |
| 💄 | `style` | Formatting only |

**Setup — Claude API key required:**

`commit.py` calls the [Claude API](https://console.anthropic.com/) to generate messages. Sign up at the Anthropic Console — new accounts get trial credits, after which usage is pay-per-token (commit messages are tiny, so cost is negligible). Add the key to your shell:

```bash
export ANTHROPIC_API_KEY=your-api-key-here
```

To persist it, add the line above to your `~/.zshrc` and run `source ~/.zshrc`.

---

## 🛠️ Scripts Reference

| Script | What it does |
|--------|-------------|
| `./new.py <platform> <url-or-slug> [url]` | Scaffold a new problem folder + fetch sample tests (folder name derived from URL slug) |
| `./test.py <platform> <problem>` | Compile/run solution and check against all test cases |
| `./commit.py` | Generate a conventional commit message from staged changes using the Claude API |

**Dependencies:**
```bash
# Java toolchain (JDK 17+ recommended)
brew install openjdk    # or: sdk install java

# Python helpers
pip3 install requests beautifulsoup4 anthropic
export ANTHROPIC_API_KEY=your-api-key-here  # required for commit.py
```

Verify the JDK is wired up:

```bash
javac -version
java -version
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

## 🖥️ IntelliJ IDEA Setup

Each problem is a self-contained `Solution.java` file with no package — IntelliJ
can run any of them as a single-file program (right-click → **Run
'Solution.main()'**).

For a full project view, open the repo root in IntelliJ and mark each platform
folder (`kattis`, `codeforces`, `leetcode`, `playground`) as a **Sources Root**
so IntelliJ indexes them. `playground/Main.java` is a single-file scratchpad —
right-click → **Run 'Main.main()'** to experiment with snippets.

From the CLI, `./playground/run` is a one-liner wrapper around `java Main.java`
that forwards stdin and args, so you can also do `./playground/run < input.txt`.

---
