# Mailer FAQ

## Why does the Mailer correlate on Reply-To and headers instead of subject?

Subject lines are too weak in email threads. A lead can reply to an earlier message with a different subject, or multiple campaigns can reuse similar wording. Reply-To tokens and thread headers are stronger signals.

## What happens if the lead unsubscribes?

The engine records the stop condition and prevents future Mailer outreach for that lead/campaign.

## Does the engine call Resend directly?

No. The engine uses the shared TPI abstraction so vendor details stay behind the integration boundary.
