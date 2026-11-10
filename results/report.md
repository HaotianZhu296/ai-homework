# Eval report: code-grading-llm-judge

Run at 2026-11-10T06:25:35+00:00 on `data/eval_dataset.jsonl` (5 samples x 5 runs per judge).

## Summary

| Judge | Mean score | 95% CI | Variance of sample means | Std | Judge std (repeat runs) | Invalid replies |
| --- | --- | --- | --- | --- | --- | --- |
| `claude-sonnet-5-5` | 3.20 | [1.80, 4.40] | 2.160 | 1.470 | 0.000 | 0 |
| `claude-haiku-5-5` | 3.40 | [2.04, 4.72] | 2.336 | 1.528 | 0.160 | 0 |

## Per sample

| Task | Unit tests | `claude-sonnet-5-5` scores (mean) | `claude-haiku-5-5` scores (mean) |
| --- | --- | --- | --- |
| Write a Python function to add two numbers. | 5/5 | 4, 4, 4, 4, 4 (4.0) | 5, 4, 5, 5, 5 (4.8) |
| Write a Python function to reverse a string. | 5/5 | 5, 5, 5, 5, 5 (5.0) | 5, 5, 5, 5, 5 (5.0) |
| Write a Python function to check if a number is even. | 6/6 | 4, 4, 4, 4, 4 (4.0) | 4, 4, 4, 4, 4 (4.0) |
| Write a Python function to compute factorial. | 2/5 | 2, 2, 2, 2, 2 (2.0) | 2, 2, 2, 2, 2 (2.0) |
| Write a Python function to find the maximum of a list. | 2/5 | 1, 1, 1, 1, 1 (1.0) | 1, 1, 1, 1, 2 (1.2) |

## Sanity check against unit tests

- `claude-sonnet-5-5`: 5/5 samples agree with the unit tests (all tests pass <=> mean score >= 4).
- `claude-haiku-5-5`: 5/5 samples agree with the unit tests (all tests pass <=> mean score >= 4).

## Judge reasoning (first run)

### `claude-sonnet-5-5`

- **Write a Python function to add two numbers.** -> 4 (correct, minor issues): Traced add(2,3)=5, add(0,0)=0, add(-1,1)=0, add('a','b')='ab'. All match the reference since the logic is identical. The only issue is the def and return squeezed onto one line, which the rubric lists as a minor style issue.
- **Write a Python function to reverse a string.** -> 5 (fully correct): Traced 'abc' -> 'cba', '' -> '' (join of empty iterator gives ''), 'a' -> 'a', 'ab' -> 'ba'. All match the reference s[::-1]. Correct for all valid string inputs; clean, idiomatic approach with no issues.
- **Write a Python function to check if a number is even.** -> 4 (correct, minor issues): Traced is_even(4) -> True, is_even(7) -> False, is_even(0) -> True, is_even(-2) -> True, is_even(-3) -> False (Python modulo gives 1). All match the reference. The only problem is the if/else returning True/False instead of returning the condition directly, which is a minor style issue.
- **Write a Python function to compute factorial.** -> 2 (major issues): Traced n=5: loop runs i=1..4, result=24, reference gives 120. n=3: returns 2 vs 6. n=0 returns 1 (correct), n=1 returns 1 (correct), but n=2 returns 1 vs 2. The range bound should be n+1, an off-by-one. Wrong for most ordinary inputs, but a small fix repairs it.
- **Write a Python function to find the maximum of a list.** -> 1 (incorrect): Traced [1,3,2]: sorted gives [1,2,3], [0] returns 1, but the max is 3. Traced [5]: returns 5, correct by coincidence. Traced [-1,-5,-3]: returns -5, but the max is -1. The candidate returns the minimum, not the maximum, so it computes the wrong thing. A fix would be [-1], but the result is wrong in general.

### `claude-haiku-5-5`

- **Write a Python function to add two numbers.** -> 5 (fully correct): Traced add(2, 3) gives 5, add(0, 0) gives 0, add(-1, 1) gives 0, add(1.5, 2.5) gives 4.0. Candidate matches reference on all inputs. Only difference is one-line style, which is acceptable and not a clean-code concern worth flagging given the task's simplicity.
- **Write a Python function to reverse a string.** -> 5 (fully correct): Traced 'hello' -> reversed() yields 'o','l','l','e','h', joined to 'olleh', matching the reference. Empty string '' -> '' (correct). Single char 'a' -> 'a' (correct). Works for any sequence of characters, with identical behavior to s[::-1] for str input. Different approach, same behavior; no issues.
- **Write a Python function to check if a number is even.** -> 4 (correct, minor issues): Traced is_even(4): 4%2==0 is True, returns True. is_even(7): 1 != 0, returns False. is_even(0): returns True. Results match the reference on all inputs, including negatives (-2 % 2 == 0 in Python, True). The if/else returning True/False is a redundant pattern where the condition itself could be returned directly, which is a minor style issue.
- **Write a Python function to compute factorial.** -> 2 (major issues): The loop uses range(1, n), so it multiplies only 1 through n-1 and returns (n-1)!. Traced: factorial(0)=1 is correct, but factorial(1)=1 is correct only by accident, factorial(2) returns 1 instead of 2, and factorial(5) returns 24 instead of 120. The approach is right and the fix is changing the bound to range(1, n+1), an off-by-one error that is wrong for most ordinary inputs.
- **Write a Python function to find the maximum of a list.** -> 1 (incorrect): Traced [3, 1, 2]: the candidate sorts ascending and returns index 0, giving 1, while the reference returns 3. [5] returns 5 and [-4, -9] returns -9, but the expected maxima are -4 and -9's counterpart -4. The candidate returns the minimum, not the maximum, so it is wrong for nearly all ordinary inputs and does not solve the task. A one-character fix (`[-1]`) would be needed, but as written it computes something different from what was asked.

