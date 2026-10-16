## The idea

Some functions are slow but always give the same output for the same input. These are *pure* functions. You can save each answer the first time and reuse it after that. This is *memoization*. The place where you save the answers is a *cache*.

A cache lookup that finds an answer is a **hit**. A lookup that finds nothing is a **miss**. On a miss, you compute the answer and save it.

## Analogy

A tax accountant gets the same question many times: "What is the tax on $10,000?" The first time, she does the full calculation. Then she writes the answer on a sticky note. The next time, she reads the note. It takes one second, not one hour.

The sticky notes are the cache. Reading a note is a hit. Doing the calculation is a miss.

## In Python

A `dict` is the simplest cache. The key is the input. The value is the output.

```python
cache = {}

def get(n):
    if n in cache:          # hit
        return cache[n]
    value = slow(n)         # miss
    cache[n] = value
    return value
```

The standard library has `functools.cache` and `functools.lru_cache`. Use them in real code. In this challenge, write the cache yourself so you see each part.

## Common mistakes

- **Falsy values.** `if cache.get(n):` treats a saved `0` as a miss. Use `if n in cache:`.
- **Shared state.** A cache defined as a class attribute (`_cache = {}` in the class body) is shared by all instances. Create it in `__init__`.
- **Cached errors.** If the function raises an exception, do not save anything. The next call must try again.

## Interview angle

The first question in the Stripe round is: "How do you make this API faster?" The answer is a cache. Expect follow-up questions:

- How much memory does the cache use? Can it grow forever? (See challenge 5.)
- Is the function really pure? If the answer can change, you need expiry (TTL).
- What happens when many threads use the cache at the same time? (See challenge 2.)

## Tie-in to your work

Look for a slow call inside a loop that keeps asking the same question: an exchange rate for a past date, a parsed config file, a rendered page for the same product. A cache keyed by the input turns many repeated reads into one. (When your AI writes questions for you, this section ties the idea to your own work, from your profile.)
