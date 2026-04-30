# Competitive Programming Notes

## Floating Point Output in C++

Use `fixed` + `setprecision` from `<iomanip>` to print decimals precisely:

```cpp
#include <iomanip>
cout << fixed << setprecision(9) << answer;
```

**Why `fixed` matters:**
- Without `fixed`: `setprecision(n)` = n total significant digits (counts from first non-zero digit)
- With `fixed`: `setprecision(n)` = n digits after the decimal point (always safe)

Example without `fixed`: `500000.123456789` with `setprecision(9)` prints `500000.123` (only 3 decimal places)
Example with `fixed`: same number prints `500000.123456789` (9 decimal places)

**"Correct within absolute or relative error of ε" (e.g. 10⁻⁷):**
- Absolute error: `|your_answer - correct| <= ε`
- Relative error: `|your_answer - correct| / correct <= ε`
- Judge accepts if either holds
- Use `setprecision(7)` or higher to satisfy 10⁻⁷

## Common Pitfalls

### Integer division
When dividing integers, the result is truncated:
```cpp
int a = 3, b = 2;
a / b      // = 1, not 1.5!
a / 2.0    // = 1.5 (correct)
```
Always use `2.0` (or cast to `double`) when you need a decimal result.