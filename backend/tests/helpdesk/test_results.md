| ID | Test case | Intended result | Actual result | Status |
|---|---|---|---|---|
| HD05-01 | Merge two open tickets, same requester+IDP | Merged; B merged, read-only, linked to A; A has messages a1,b1,a2,b2 and notes an1,bn1 in timestamp order | Merged; B merged, read-only, linked to A; A has messages a1,b1,a2,b2 and notes an1,bn1 in timestamp order | PASS |
| HD05-02 | Same ticket twice | Error; nothing merged | Error; nothing merged | PASS |
| HD05-03 | One ticket already merged | Error; nothing merged | Error; nothing merged | PASS |
| HD05-04 | One ticket closed | Error; nothing merged | Error; nothing merged | PASS |
| HD05-05 | Different requester or IDP | Error; nothing merged | Error; nothing merged | PASS |
| HD05-06 | Failure part way through | Error; both tickets unchanged | Error; both tickets unchanged | PASS |
| HD05-07 | Write to a merged ticket | Rejected | Rejected | PASS |
