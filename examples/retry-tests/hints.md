The docstring makes four promises. Which of them does the starter test check?

---

**Control time and failure** (subgoal 3): a call that fails a set number of times, and a fake `sleep` that records each wait, let you check exact numbers.

---

Write a test that fails 2 times then succeeds with `attempts=3`. Assert the call count and the recorded waits, `[0.1, 0.2]`.

---

```python
def test_raises_the_last_error_and_does_not_wait_after_it():
    waits = []
    with pytest.raises(ConnectionError, match=...):
        retry(..., attempts=3, base_delay=0.1, sleep=waits.append)
    assert waits == ...
```
