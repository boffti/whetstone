Between two calls to `get(7)`, where does the first answer live, and which object owns that place?

---

Use the lesson's subgoals: **look up** by membership, **count**, and **save only after compute returns**. "Is the key there?" is a different question from "is the saved value truthy?".

---

Make `test_caches_zero_and_other_falsy_results` pass first. Create the dict in `__init__`, and check for a hit with `n in self._cache`.

---

```python
def get(self, n):
    if n in self._cache:
        ...  # count a hit, return the saved value
    ...      # count a miss
    value = self._compute(n)
    ...      # save it, then return it
```
