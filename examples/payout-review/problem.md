## Task

Your AI assistant wrote `subject.py` (read-only, next to your code): the nightly job that pays merchants. It reads the unsettled payments, keeps the ones captured on one day, groups them by merchant, nets out refunds, and sends one transfer per merchant through the bank gateway.

The code is in a pull request, and you are the reviewer. The style is clean and the names are good. Find the defects you would block the pull request for. You do not fix them: you say where each one is and what kind it is.

## API

In `solution.py`, list one finding per defect:

```python
FINDINGS = [(line, "category"), ...]   # line: the line number in subject.py
```

## Categories

Give each finding one of these categories:

- `race`: two threads or processes interleave and break a result.
- `not-idempotent`: doing it twice, for example on a retry or a re-run, has a different effect from doing it once.
- `missing-timeout`: a call to another system can wait forever.
- `wrong-boundary`: an off-by-one at the edge of a range, a window or a limit.
- `resource-leak`: something that is opened is not closed on every path.
- `unvalidated-input`: data from outside is used without a check.

How the review is graded:

- `subject.py` has 2 or 3 defects, each of a different category.
- A finding counts when its line is within 2 lines of the defect and its category is right.
- At most one finding may point at code that is fine. List only what you would defend in a real review.
- **Run tests** checks only the format. **Submit** grades the review.

## Example

A review of a different file might read:

```python
FINDINGS = [(12, "resource-leak"), (40, "race")]
```
