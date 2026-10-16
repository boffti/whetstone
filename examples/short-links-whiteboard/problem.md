## Task

Your company launches a new product next month. The marketing team runs the launch campaign on TV, email, SMS, social posts and printed QR codes. Every placement gets its own short link on the company domain, for example `go.example.com/x7Kp2Qa`, so the team can see which channel works.

Design the short link service.

- The campaign tool creates links in bulk before the launch: one link for each email and SMS recipient. During the campaign, the team creates more links by hand. Some links get a custom alias, such as `go.example.com/launch`.
- A visitor who opens a short link arrives at its destination URL.
- Some links expire, for example when a launch offer ends. After that, the visitor sees an "offer ended" page.
- The team can fix a wrong destination, or switch a link off, at any time.
- The campaign report shows clicks per link, per channel and per hour. Finance pays partners from these numbers, so the counts must be right.

## Scale

- 50 million redirects a day during the campaign.
- The launch is a TV ad and a push notification at 20:00. For about 15 minutes after it, redirects reach 20 times the daily average. The TV link alone gets up to 5,000 redirects a second.
- 1 million new links a day on average. In the week before the launch, the campaign tool imports 5 million links in one batch.
- 100 million links exist after a year. A destination URL is at most 2 KB. Most are about 200 bytes.
- Visitors are worldwide, mostly in North America and Europe.
- A redirect must feel instant: under 100 ms for the visitor, at p99.
- Redirects keep working when one part of the system fails. Link creation may pause for a few minutes.
- A destination change or a switch-off takes effect within 1 minute. Clicks appear in the report within 5 minutes.

## Out of scope

- Sign-in and user management: the team signs in with the company's single sign-on.
- The report's user interface, and QR code images.
- Link previews, and sign-up for people outside the company.
- Bot detection beyond a basic user-agent filter.

## What the interviewer looks for

The interviewer expects you to drive. They want to see each stage of a design interview, in this order:

1. Requirements that you confirm out loud, including what you leave out.
2. Estimates with the arithmetic shown, and a design that uses them.
3. An API with its error cases, and a data model with its keys.
4. A diagram of the main components, for creating a link and for following one.
5. Depth on the two or three hardest parts. You choose them.
6. Trade-offs named as choices, with what each one costs.
7. What breaks, and what the visitor and the marketing team see when it does.
