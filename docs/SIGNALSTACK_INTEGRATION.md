# SignalStack integration

Trade The Pool has no public custom-application API. SignalStack is the supported execution layer under the user's written conditional approval; direct Trade The Pool integration remains prohibited. SignalStack and automated trading are beta capabilities whose availability, parameters, account coverage and authorization may change.

SignalStack's official help center explains that users create an account-specific webhook and must use the example payload shown for that connected account. It also distinguishes production webhooks, which can execute, from test webhooks used for format validation: [Create Webhooks](https://help.signalstack.com/kb/getting-started/create-webhooks), [Production and Test Webhooks](https://help.signalstack.com/kb/getting-started/difference-between-production-and-test-webhooks).

This repository therefore does not guess an endpoint, authentication format, Trade The Pool payload, symbol mapping, protective-order format, response schema or error code. It implements approval/policy validation, internal order intents, a durable priority queue, idempotency, bounded retries, request/response tables and a hard two-request-per-rolling-minute limiter with at least 30 seconds between ordinary requests. Outbound transport remains disabled until the exact account-generated webhook and official payload displayed for the supported Trade The Pool connection are supplied and validated in a test webhook.

All live flags, current rules, production environment, reconciliation, account state, volume rule, risk state, queue safety and policy freshness must pass. Risk-reducing exits receive queue priority but never bypass the rate limit. A queued or acknowledged request is not a confirmed fill.

## Confirmed demo payload

The Trade The Pool demo displayed the basic request `{"symbol":"AAPL","quantity":1,"action":"buy"}`. The repository models that exact three-field schema: symbols are normalized, quantity must be a positive integer, action is restricted to `buy` or `sell`, and additional fields are refused. Because the example does not define stop, target, short-sale, cancel, or modify semantics, none of those payloads are inferred. Outbound HTTP transport remains disabled until this request succeeds against the SignalStack test webhook and its test log is reviewed.

The test-only transport requires `SIGNALSTACK_WEBHOOK_TYPE=test`, `SIGNALSTACK_TEST_TRANSPORT_ENABLED=true`, an HTTPS `SIGNALSTACK_WEBHOOK_URL`, and `SIGNALSTACK_LIVE_EXECUTION_ALLOWED=false`. `POST /signalstack/test-configuration` without a body performs a readiness check only. Sending the confirmed JSON body makes one authenticated test request, records its timestamp/status without storing the webhook URL, and applies the same two-per-minute/30-second limiter. A production webhook type is always refused by this transport.
