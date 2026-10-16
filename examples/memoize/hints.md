Store answers in a dictionary that belongs to the object. Create it in `__init__`.

---

Check for a key with `n in self._cache`, not with `self._cache.get(n)`. The second form fails when the saved value is `0`.

---

Count a miss before you call `compute`. Save the value only after `compute` returns. If `compute` raises, the line that saves the value never runs.
