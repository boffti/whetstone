## The idea

When an AI writes your code, the tests are what you trust. A test suite is only as good as the bugs it can **catch**. A suite that passes on correct code is not enough; it must also fail on wrong code.

**Mutation testing** measures this. You change the code in one small way (a **mutant**), run the tests, and check that at least one fails. If every test still passes, the mutant **survives**, and your tests have a blind spot.

## Subgoals

1. **Read the contract**: the docstring says what the function promises.
2. **Turn each promise into a test**: one behavior per test.
3. **Control time and failure**: inject a fake `sleep` and a call that fails on purpose.
4. **Check the exact numbers**: calls, waits, and which error comes out.

## In Python

`pytest.raises(SomeError, match="text")` checks that a block raises, and what the message says. A list's `append` method makes a fine fake `sleep`: it records each wait instead of waiting.

## Misconceptions

- "If the happy path passes, the function works." Most bugs in a retry helper hide in the failure path.
- "Checking that it waits is enough." A test must check how long, and how many times.
- "Testing with real `time.sleep` is fine." It makes tests slow and still cannot see the exact waits.

## Interview angle

Expect: "How would you know your tests are good?" Name mutation testing, then coverage, then the gap between them: coverage shows a line ran, a mutant shows a line was checked.

## Tie-in to your work

Pick a helper your AI wrote last week, list its promises, and ask: which promise has no test?
