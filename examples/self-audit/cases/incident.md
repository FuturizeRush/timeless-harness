# Task

You own a payment service after a release. Give the operator a concise incident verdict, the smallest safe repair plan, and a final verification plan. Do not browse. Do not ask questions; the evidence below is the complete available record.

Observed evidence:

- Deployment and unit tests are green.
- `POST /charge` times out at the gateway after 10 seconds; the gateway retries once.
- The service sometimes completes the first request after 12 seconds and the retry after 8 seconds.
- Both attempts persist a charge because the service has no idempotency handling.
- The unit test mocks the charge provider at 100 ms.
- The dashboard counts HTTP `200` responses, not persisted charges.
- Customers have reported duplicate charges.
- A proposed patch catches the timeout and immediately returns `200 {"status":"pending"}` without changing persistence or retry behavior.
- A rollback is available.

Your answer must classify the current outcome, accept or reject the proposed patch with reasons, identify the highest-leverage repair, contain current harm, and define evidence required before release. Maximum 450 words.
