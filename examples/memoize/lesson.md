## The idea

Some functions are slow but always give the same output for the same input. These are *pure* functions. You can save each answer the first time and reuse it after that. This is *memoization*. The place where you save the answers is a *cache*.

A cache lookup that finds an answer is a **hit**. A lookup that finds nothing is a **miss**. On a miss, you compute the answer and save it.

## Subgoals

1. **Look up** the input in the cache.
2. On a hit, **count** it and return the saved answer.
3. On a miss, **count** it and call the slow function.
4. **Save** the answer only after the call returns.

A worked example on a different problem with the same subgoals: charge each order only once.

```python
charged = set()

def charge_once(order_id):
    if order_id in charged:   # 1. look up
        return "duplicate"    # 2. hit
    send_charge(order_id)     # 3. miss: do the work
    charged.add(order_id)     # 4. record only after it succeeds
    return "charged"
```

## In Python

A `dict` is the simplest cache: the key is the input and the value is the output. Test membership with `key in d`. The standard library has `functools.cache` and `functools.lru_cache`. Use them in real code. In this question, write the cache yourself so you see each part.

## Misconceptions

- "`cache.get(n)` tells me whether `n` is cached." A saved `0` or `""` is falsy, so it looks like a miss.
- "A dict in the class body belongs to each object." A class attribute is shared by every instance.
- "If the function fails, it is fine to save something." A saved failure stops every later call from trying again.

## Interview angle

The first question in a practical round is often: "How do you make this API faster?" The answer is a cache. Expect follow-up questions:

- How much memory does the cache use? Can it grow forever? (A later question in the module.)
- Is the function really pure? If the answer can change, you need expiry (TTL).
- What happens when many threads use the cache at the same time? (The next question.)

## Tie-in to your work

Look for a slow call inside a loop that keeps asking the same question: an exchange rate for a past date, a parsed config file, a rendered page for the same product. A cache keyed by the input turns many repeated reads into one. (When your AI writes questions for you, this section ties the idea to your own work, from your profile.)
