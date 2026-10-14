# Decisions

1. **Indexes.** Unique employee code and employee/date indexes enforce business keys. Department/code supports employee lists and department lookups; joined_on/department supports eligible headcount. Date/code and status/date/code support attendance filters and ordering; employee/punch_in supports the latest eligible punch. Employee/date also supports monthly lookups. I rejected indexing history: no endpoint filters it, and every correction would pay extra write cost.

2. **Punch-in race.** Both requests validate and build the same employee/day key. MongoDB's unique index allows one insert, returning 201. The other insert raises DuplicateKeyError, which becomes 409. A preceding existence check is unnecessary.

3. **Ties.** MongoDB $rank assigns competition ranks using total late minutes alone. Filtering rank <= limit retains the entire boundary tie, so the response can exceed limit. Final sorting uses emp_code to order tied employees consistently.

4. **Headcount.** The summary starts from eligible employees, then looks up each employee's monthly metrics. Empty lookup results become zeros, so employees without logs still count once.

5. **100x data.** I would measure executionStats and latency, then maintain incremental daily summaries for expensive department reporting. Corrections must update those summaries reliably; I would retain source records and audit history for reconciliation.
