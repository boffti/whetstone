When `try_send` runs at second 61 in the burst run, which of the earlier times are still in the merchant's deque, and what put them there?

---

Use the lesson's subgoals in order. **Find the cutoff** for each call, then **check the edge** for a time exactly 60 seconds old. **Find what is recorded**: which line adds a time, and which calls get that far?

---

Settle `retries_count_at_75` first. Write the deque after each of the six calls in the retries run, with that call's cutoff next to it. At second 75 the cutoff is 15.

---

Fill in this trace, then make the same table for the burst run and the spread run:

```text
retries run: limit=3, window=60
call  cutoff  deque after the call  returns
0     -60     [0]                   True
10    -50     [0, 10]               True
20    -40     ...                   True
30    -30     ...                   ...
45    -15     ...                   ...
75     15     ...                   ...
```
