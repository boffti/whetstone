## Task

`retry.py` (read-only, next to your code) retries a flaky call with exponential backoff. Write tests for it in `solution.py`.

## API

```python
def retry(fn, attempts=3, base_delay=0.1, sleep=time.sleep): ...
```

Read its docstring: every promise there is something a test can check.

## Rules

- Your tests must pass on the real `retry.py`. **Run tests** checks this.
- **Submit** also runs your tests against hidden buggy versions of `retry.py`. Each buggy version must make at least one of your tests fail.
- Do not really sleep: pass your own `sleep` function.

## Example

```python
def test_returns_the_value_when_the_call_works():
    assert retry(lambda: 42, sleep=lambda seconds: None) == 42
```
