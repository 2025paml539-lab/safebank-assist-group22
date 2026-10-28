| Intent | Routing outcome taught | Train query |
|---|---|---|
| `card_arrival` | tool `check_card_delivery_status` | why hasnt my card come in yet? |
| `atm_support` | tool `find_branch` | What ATM accepts Mastercard? |
| `card_swallowed` | escalate (destructive tool) | The ATM sucked my card in. |
| `card_not_working` | text only | I tried to purchase airline tickets online this morning and my card information isn't working. Is there something going on with my account? |
