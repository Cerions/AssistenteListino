# Blocco 1 · Assistente da terminale: considerazioni

Script: `assistente.py`. Legge `listino.json`, lo inserisce nel system prompt (`system_prompt_template.txt`), pone le domande di `domande.txt` a due modelli (Haiku 5.5 e Sonnet 5.5), 2 prove ciascuna, e stampa token e costo stimato.

## 1. Temperature non utilizzabile

La consegna chiedeva temperature 0 e 1, ma con questo setup non è possibile:

- `anthropic` 2.x (installata la 2.4.0) ha rimosso `temperature`, `top_p` e `top_k` da `messages.create()`: passarla dà `TypeError`.
- Secondo la guida di migrazione di Claude Haiku 5.5, su questo modello `temperature`, se presente, deve valere 1.
- Anche su Sonnet 5.5 i parametri di campionamento sono rimossi: valori non-default non sono supportati (guida di migrazione della famiglia 5.5 riassunta da OpenRouter; nella documentazione Anthropic di Sonnet 5 un valore non-default dà errore 400). Il default è 1, quindi `temperature=1` non cambierebbe nulla, mentre lo 0 richiesto dall'esercizio non è ammesso. Da ricontrollare sulla pagina ufficiale di Sonnet 5.5 se si cita come regola precisa.

Soluzione adottata: parametro tolto e ogni domanda ripetuta 2 volte per osservare la variabilità tra una run e l'altra. Da confermare con il docente se serve un modello più vecchio con `anthropic<2`.

## 2. Perché il costo cambia tra i due modelli

Formula: `costo = input/1e6 * prezzo_in + output/1e6 * prezzo_out`

| Modello | Input ($/M token) | Output ($/M token) |
|---|---|---|
| claude-haiku-5-5 | 1 | 5 |
| claude-sonnet-5-5 | 3 | 15 |

Esempi dai log (stessa domanda, token di input identici):

| Domanda | Modello | Input | Output | Costo |
|---|---|---|---|---|
| Noce vs castagno (prova 1) | Haiku | 515 | 90 | $0,000965 |
| Noce vs castagno (prova 1) | Sonnet | 515 | 217 | $0,004800 |
| Tavolo 200x100x50 (prova 1) | Haiku | 557 | 990 | $0,005507 |
| Tavolo 200x100x50 (prova 1) | Sonnet | 557 | 818 | $0,013941 |

Il costo cambia per due motivi:

1. **Prezzo unitario**: Sonnet costa 3 volte Haiku per token, sia in input sia in output.
2. **Quantità di output**: i modelli scrivono quantità diverse di testo e, soprattutto, producono blocchi `thinking`. I token di thinking non compaiono nel testo ma sono contati e pagati come output.

L'output costa 5 volte l'input per token, quindi pesa più dell'input anche quando è più corto.

## 3. Problema trovato: risposta vuota con `max_tokens=500`

Con `max_tokens=500` la domanda sul tavolo restituiva risposta vuota e 500 token di output. Causa: il thinking consumava tutto il limite prima che il modello scrivesse il testo. Verificato stampando `stop_reason` e i tipi di blocco: la risposta contiene `['thinking', 'text']`. Alzando `max_tokens` a 2000 la risposta arriva (`end_turn`).

Conseguenze nel codice:

- il testo si legge selezionando i blocchi di tipo `text`, non con `r.content[0]`;
- `max_tokens` va dimensionato tenendo conto del thinking.

## 4. Il listino nel system prompt si paga a ogni chiamata

Circa 500 token di input fissi in ogni richiesta (515, 516, 513, 557 a seconda della domanda). Il JSON è formattato con `indent=2`: togliere l'indentazione ridurrebbe i token di input senza cambiare il contenuto.

## 5. Comportamento dei modelli

- **"Non inventare" funziona**: sulla differenza tra cera naturale e laccato entrambi i modelli dicono che il listino riporta solo i prezzi e non le caratteristiche delle finiture.
- **Calcolo del tavolo corretto** in tutte le prove: superficie 2×(200×100 + 200×50 + 100×50) = 70.000 cm² = 7 m²; abete 7 × 85 = 595,00 €; IVA 22% = 130,90 €; totale 725,90 €. Il modello ha anche segnalato che il listino non specifica come si conta la superficie di un tavolo (assunzione: parallelepipedo). Il calcolo è fatto "a mente" dal modello, quindi da verificare in codice.
- **IVA**: l'IVA al 22% e i limiti 30–300 cm sono nel listino (`parametri`), quindi i modelli li citano correttamente. Il listino però non dice se le consegne siano IVA esclusa: Sonnet lo ha segnalato in più prove, Haiku ha risposto "120,00 €" senza dubbi.
- **Variabilità**: la stessa domanda dà risposte e costi diversi da una prova all'altra (es. Haiku su noce/castagno: 90 token senza thinking, 193 con thinking). Una formulazione di Haiku ("80,00 € a favore del castagno") risulta ambigua: serve confrontare più prove.

