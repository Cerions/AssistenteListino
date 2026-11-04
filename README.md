# Blocco 1 · Assistente da terminale
Obiettivo: `assistente.py` che risponde a una domanda sul listino e stampa token e costo.

1. `pip install anthropic`  ·  chiave in variabile d'ambiente `ANTHROPIC_API_KEY` (mai nel codice, mai su git).
2. Leggi `listino.json` e inseriscilo nel system prompt seguendo `system_prompt_template.txt`.
3. Chiama il modello con temperature 0 e poi 1 su 3 domande, con due modelli (vedi `prezzi_modelli.md`).
4. Stampa `r.usage.input_tokens`, `r.usage.output_tokens` e il costo stimato.

Fatto quando: lo script gira, stampa i token, e sai spiegare a voce perché il costo cambia tra i due modelli.
Domande di prova: vedi `domande.txt`.
