## The idea

Generated code reads well: good names, type hints, confident docstrings. So a review of **style** finds little. Review it for **guarantees** instead. Each docstring, name and comment is a claim: find the line where it breaks.

Claims break on the **failure path**, the one the assistant did not imagine: a call runs twice, a call never returns, a value sits exactly on an edge. A useful **finding** names the line, the category, and the consequence in the user's world, for example "a merchant is paid twice".

## Subgoals

1. **List the promises**: docstrings, names, comments.
2. **Replay it**: what if a call that changes something runs twice, on a retry or a re-run?
3. **Stall it**: what if another system never answers?
4. **Walk the edges**: run the exact boundary value through each range or window by hand.
5. **Write the finding**: the line, the category, the consequence.

## In Python

Know the defaults that hide defects:

```python
urlopen(url)               # no timeout: waits as long as the socket does, forever by default
urlopen(url, timeout=10)   # gives up after 10 seconds
range(start, stop)         # half-open: includes start, excludes stop
```

Third-party clients differ: `requests` waits forever unless you pass `timeout=`; `httpx` gives up after 5 seconds by default.

## Misconceptions

- "If it reads well, it was thought through." Fluent style is what generated code always has.
- "Code that sends an idempotency key is idempotent." Only a key that stays the same on every retry and every re-run stops a duplicate.
- "A network call fails fast when the other side is down." A server that accepts the connection and then goes quiet holds the call until a limit stops it.
- "A window that looks tidy is right." Each instant must fall in exactly one window.

## Interview angle

Expect: "How do you review code an assistant wrote?" Name the guarantees, then the failure paths: retries, a crash between two writes, a slow dependency, the edge of a range. A staff engineer adds what catches each class next time: a fake gateway that drops a response, a test at exactly midnight, a lint rule for calls with no timeout.

## Tie-in to your work

Open the last pull request your assistant wrote that calls another service. Ask of each call: twice, never, on the edge?
