## The idea

A link shortener is a **read-heavy** system. One write, a new link, makes many reads possible: the **redirects**. So most of the work goes into the read path: a **cache** in front of the **database**, and an **edge** near the visitor.

The write path has one hard problem. Many servers make codes at once, and each code must be **unique**, without one shared **bottleneck**.

The read path hides a write: the click count. Record it inside the redirect, and the redirect stops being cheap. So you record clicks **asynchronously**, after the response.

## Subgoals

1. **Pin the requirements**, with the numbers.
2. **Size it**: requests per second at peak, data, cache.
3. **Define the API**, with the errors.
4. **Choose the data and its keys**.
5. **Draw the read and write paths**.
6. **Go deep on the hardest parts**.
7. **Name the trade-offs**.
8. **Break it on purpose**: remove one part at a time.

Worked example, on a pastebin. **Pin**: text up to 1 MB, kept 30 days. **Size**: 100,000 pastes a day × 10 KB = 1 GB a day. **Data**: metadata by key, text in object storage. **Paths**: reads go through a CDN, because a paste never changes. **Deep**: the 30-day delete. **Trade-off**: fast reads, but a delete waits for the CDN to forget. **Break it**: if object storage slows, popular pastes still come from the CDN.

## Numbers to know

- A day has 86,400 seconds, about 10^5. So 1 million a day is about 12 a second.
- A launch or a TV ad can be 10 to 20 times the average.
- Memory: under 1 µs. Redis: about 1 ms. Database by key: 1 to 10 ms. Across an ocean: about 100 ms.
- One cache server holds tens of GB and serves 100,000 reads a second.
- Base62: 62^6 ≈ 5.7 × 10^10, 62^7 ≈ 3.5 × 10^12.
- n random codes in a space of N give about n² / 2N clashes.

## Misconceptions

- "A 301 and a 302 are the same to the business." Browsers keep a 301, so repeat clicks never reach you.
- "Counting a click is one small write in the redirect." At the peak, it hits one hot row thousands of times a second.
- "A hash of the long URL makes a good short code." Short hashes clash, and one URL often needs a code for each channel.
- "An expired code is free to reuse." Old emails and printed QR codes still point at it.

## Interview angle

Expect: "Your link is on TV at 20:00. What happens in the first ten seconds?" And: "How do you change a destination printed on a million flyers?" A staff engineer names the trade-offs. A 301 is cheaper, but a 302 keeps counts and edits correct. Counter ranges need a coordinator; random codes need a conditional write. Exact counts cost more than approximate ones.

## Tie-in to your work

Look for a service where reads far outnumber writes, such as feature flags or a product catalog. Ask the same questions: what do you cache, how stale may it be, and how do you record a read without slowing it?
