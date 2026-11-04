# Prezzi indicativi ($ per milione di token)
Valori indicativi: verifica sempre la pagina prezzi ufficiale del provider.

| Modello | Input | Output |
|---|---|---|
| claude-haiku-5-5 | 1 | 5 |
| claude-sonnet-5-5 | 3 | 15 |

costo = input_tokens/1e6 * prezzo_in + output_tokens/1e6 * prezzo_out
