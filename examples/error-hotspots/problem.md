You're on call for `quotes-api` at Larkmoor, a home-insurance marketplace. Fourteen nginx servers behind a load balancer take about 11 million requests a day. At 09:10 the 5xx alert fired: 2.4% of requests are failing, and the dashboard can't say which ones. Before you page a team, you want the endpoints that fail most.

`sandbox/` is one server's `/var/log/nginx/`, cut down to a few hundred lines a file; the real logs hold about 800,000 lines a day. Explore there. Then write the commands in `solution.sh`: the tests run it in other log folders, from other servers and other days.

nginx writes one line per request in the combined log format, with one change: the first field is the `X-Forwarded-For` header, so a request that came through the partner gateway shows two addresses.

```
198.51.100.23 - - [07/Nov/2026:09:14:03 +0000] "GET /v1/quotes?zip=10001 HTTP/1.1" 502 157 "-" "Larkmoor-iOS/5.12.1 (iPhone15,3; iOS 18.1)"
203.0.113.40, 10.20.0.4 - - [07/Nov/2026:09:14:04 +0000] "POST /v1/quotes/compare HTTP/1.1" 200 1834 "-" "PartnerHub/2.4 (+https://partners.example/bot)"
```

## Stage 1

From `access.log` in the current folder, print the 3 paths with the most 5xx responses, one per line as `<count> <path>`, the most first.

- The path is the request path without its query string: `/v1/quotes?zip=10001` counts as `/v1/quotes`.
- A 5xx is a status from 500 to 599. A 4xx is the client's mistake, not an outage.
- Break ties by path, in byte order (the tests run with `LC_ALL=C`).
- Skip lines whose request isn't three words: a method, a path and a protocol. `"-"` is a client that connected and sent nothing; `"\x16\x03\x01..."` is a TLS handshake sent to the HTTP port.
- When fewer than 3 paths failed, print the ones that did; when none did, print nothing. Exit 0 either way.
- Padding before the count doesn't matter.

`sandbox/` also holds older days' logs. Stage 1 is about `access.log` alone.

## Stage 2

nginx rotates the log every night and keeps a week: `access.log` is today, `access.log.1` is yesterday, and older days are gzipped, from `access.log.2.gz` to `access.log.7.gz`. A server that came up a few days ago has fewer.

Print the same top 3, counted across every access log in the folder. Leave the logs as they are: on the server they're the only copy, so don't unzip them in place.
