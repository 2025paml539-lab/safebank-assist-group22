| Theme | Intent | Example query (train split) | Routes to |
|---|---|---|---|
| card delivery | `card_arrival` | How can I see the progress of delivery of the card that was sent? | `check_card_delivery_status` |
| card delivery | `card_delivery_estimate` | Can I have it by a certain date? | `check_card_delivery_status` |
| card security | `lost_or_stolen_card` | I think that the card is stolen.  What are my next steps? | `block_card` |
| card security | `compromised_card` | Questionable transactions on my account. | `block_card` |
| top up | `top_up_failed` | I topped up my card but the app rejected it. | — |
| top up | `pending_top_up` | How long does my top up pending last? | — |
| transfer | `failed_transfer` | I attempted a transfer, but it failed. | — |
| transfer | `pending_transfer` | Why is my transfer still pending after all this time? | — |
| cash atm | `atm_support` | Where is the closest ATM I can use? | `find_branch` |
| cash atm | `cash_withdrawal_charge` | I hate this ATM, it charged me an extra fee, Why did it charge? | `find_branch` |
