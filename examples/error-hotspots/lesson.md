## Where the status is

A log line has a structure, and spaces aren't it. In the **combined log format** the fields are the client address, two identity fields (usually `-`), the time in brackets, the request line in quotes, the status, the bytes sent, then the referrer and the user agent, both in quotes.

`awk '{ print $9 }'` splits on runs of spaces and prints the ninth word. That's the status only while every field before it has a fixed number of words. An address list (`203.0.113.40, 10.20.0.4`) adds a word, and the ninth word becomes `HTTP/1.1"`. A search for what looks like a status, such as `grep ' 5[0-9][0-9] '`, also matches a 571-byte response.

Quotes hold the structure. Split on them instead:

```
$ awk -F'"' '{ print $2 " | " $3 }' access.log | head -n 2
GET /v1/rates?state=NY HTTP/1.1 |  503 197
POST /v1/auth/token HTTP/1.1 |  200 3572
```

Field 2 is the request line, and field 3 starts with the status, whatever came before. `split($2, req, " ")` puts the request's words in `req` and returns how many there were, so a `"-"` gives 1. `sub(/[?].*/, "", s)` cuts a string at its first `?`.

## Counting and ranking

`uniq -c` counts runs of identical adjacent lines. It never looks further back, so a path in two places gets two counts. Sort first: `sort | uniq -c`.

Then rank. Plain `sort` compares text, where `9` comes after `10`; `-n` compares numbers. `-r` reverses the whole order, including how sort breaks a tie: with `sort -rn`, paths with the same count come out Z to A. Keys fix that: `sort -k1,1nr -k2,2` sorts by field 1 as a number, largest first, then by field 2 as text. `LC_ALL=C` makes text order byte order, the same on every machine.

## Rotated logs

`gzip -cd` decompresses to stdout, and `-f` passes plain files through unchanged. So `gzip -cdf access.log*` reads plain and gzipped logs as one stream. `cat` copies the compressed bytes as they are, and `zcat` on macOS looks for `.Z` files. A glob lists only the files that exist, so it works on a server with two logs or eight.

## Subgoals

1. **Keep the right lines.** Split on quotes; keep three-word requests with a 5xx status.
2. **Cut the path.** Drop the query string.
3. **Count.** Sort, then count repeats.
4. **Rank.** By count as a number, largest first, then by path; keep three.
5. **Read every day.** Feed every access log into the same pipeline.

## In a script

`set -euo pipefail` makes a pipeline fail when any command in it fails, not only the last. Two surprises follow. `grep` exits 1 when nothing matches, so on a calm day the script fails. And `head -n 3` exits after three lines; on a big input, the command feeding it then dies of SIGPIPE. `awk 'NR <= 3'` reads all its input, so nothing upstream breaks.
