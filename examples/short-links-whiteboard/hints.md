Two servers each create a link in the same millisecond: the email version and the SMS version of the same offer. How do you know their codes differ, without both servers asking one shared thing for every code?

---

Use the subgoal **go deep on the hardest parts**. Here there are two: making unique codes without one shared bottleneck, and counting clicks without slowing the redirect. For codes, ask who decides a code is free, and when. For clicks, ask what the visitor must wait for, and what can happen after the response.

---

In Estimates, compute redirects per second on an average day and in the 15 minutes after launch. Then size the cache from the number of active campaign links. Carry both numbers into High-level design: how many redirect servers, and how many reads may reach the database.

---

```markdown
## Estimates
- Redirects: 50 M a day / 86,400 s = ... per second. Launch peak: ...
- Cache: ... active links x ... bytes = ...

## API
- GET /{code} returns ..., because ...

## Deep dives
- Codes: each create server gets ... ; a code is ... base62 characters
- Read path: in-process cache, then ..., then ...
- Clicks: the redirect ... and returns; a ... counts them per link and hour

## Failure modes
- Cache down: ...
- Database down: ...
- The TV link at 20:00: ...
```
