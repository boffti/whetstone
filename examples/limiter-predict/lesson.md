## The idea

A **rate limiter** caps the requests one caller gets per period, so a burst of webhooks does not flood a merchant's endpoint. "3 per 60 seconds" has two common meanings:

- A **fixed window** counts per clock minute and resets at each boundary. Deliveries at seconds 58 and 61 land in different minutes, so a merchant can get twice the limit within seconds.
- A **sliding window** looks back 60 seconds from each call, so room comes back one delivery at a time.

A **sliding log** keeps the time of each counted event and drops the times behind the **cutoff**, `now - window`.

## Subgoals

1. **Find the state**: what the code keeps between calls.
2. **Find the cutoff**: what it is measured from.
3. **Check the edge**: what happens to an entry exactly one window old.
4. **Find what is recorded**: which calls change the state.
5. **Trace in order**: write the state after every call.

A worked example on different code, a login lockout:

```python
def failed_login(user, now):
    kept = [t for t in fails[user] if t >= now - 300]  # cutoff; >= keeps the edge
    kept.append(now)  # recorded: every failure
    fails[user] = kept
    return len(kept) >= 3  # locked out?
```

Failures at 0, 100 and 300: at 300, `>=` keeps the one at 0, so the user is locked out.

## In Python

`collections.deque` keeps times in order: `d[0]` is the oldest, and `popleft()` drops it in O(1).

```python
d = deque([10, 20]); d.popleft(); d.append(45)  # deque([20, 45])
```

## Misconceptions

- "Per 60 seconds means per clock minute." That is a fixed window. Find what the cutoff is computed from.
- "Every call counts against the limit." Some limiters record refused tries, some do not. Find which calls reach the line that records.
- "The edge does not matter." At exactly one window, `<` and `<=` disagree: read which one the code uses.

## Interview angle

At scale, the log holds up to `limit` times per merchant; a **sliding window counter** weights two fixed-window counts for constant memory. Across servers, use a Redis sorted set, trimmed and counted atomically.

## Tie-in to your work

Find a limiter in front of an API you call or run. Does it slide or reset, count refused tries, keep or drop the edge? (Your AI ties this to your work, from your profile.)
