# POL-03 Approval and payment

## Automatic approval
A claim whose items all comply with the rules and whose total approved amount is at most Rp500.000 is approved automatically, without a manager.

## Manager approval
Claims above Rp500.000, claims with some items capped or rejected, and claims with suspicious descriptions must be approved by the direct manager.

## Remaining annual budget
The approved total must not exceed the employee's remaining annual budget. If it does, the claim is rejected and the employee is referred to HR.

## Payment transfer
Payment is transferred once per claim after approval. The payment system uses an idempotency key, so a repeated request does not cause a double transfer.
