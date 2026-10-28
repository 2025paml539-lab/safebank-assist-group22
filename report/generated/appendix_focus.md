Predicted before any results existed (`intents.CONFUSABLE_PAIRS`):

| Intent | Confused with | Why |
|---|---|---|
| `card_arrival` | `card_delivery_estimate` | Both concern an undelivered card and differ only in whether the customer asks about current status or about expected timing. |
| `top_up_failed` | `pending_top_up` | An incomplete top-up can be described as failed or as pending depending on the customer's interpretation, not on the facts. |
| `transfer_not_received_by_recipient` | `transfer_timing` | A recipient not seeing money may be a timing question or a fault report; the surface wording is often identical. |
| `lost_or_stolen_card` | `compromised_card` | Both trigger card blocking. The distinction is the cause, which customers rarely state explicitly. |
| `cash_withdrawal_charge` | `declined_cash_withdrawal` | Both mention an ATM withdrawal problem; one is about a fee, the other about a refusal. |
| `pending_cash_withdrawal` | `declined_cash_withdrawal` | Pending and declined withdrawals look identical to a customer whose balance changed but who received no cash. |

Observed in real model runs (`intents.OBSERVED_CONFUSIONS`), kept separate so the prediction is not rewritten by hindsight:

| Gold intent | Predicted | Note |
|---|---|---|
| `card_arrival` | `card_not_working` | Observed on the first real Qwen2.5-1.5B query: 'my card hasn't arrived' was labelled card\_not\_working. An undelivered card and a faulty card are different intents, but both are phrased as the card not working for the customer. Not in the predicted set because the prediction focused on delivery-vs-timing rather than delivery-vs-fault. |
