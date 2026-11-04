# Blocco 2 · Chat con memoria su `/chat`

**Obiettivo:** trasformare l'assistente del blocco 1 in un piccolo server web che *ricorda* la conversazione di ogni utente.

## Cosa trovi nella cartella
| File | A cosa serve |
|---|---|
| `server.py` | Server FastAPI con 4 TODO da completare |
| `listino.json` | Listino aggiornato (8 legni, 6 finiture, 3 consegne) |
| `prova_chat.py` | Script che simula 15 turni di chat + una seconda sessione |

## Preparazione
```bash
pip install fastapi uvicorn anthropic requests
# chiave in variabile d'ambiente ANTHROPIC_API_KEY (mai nel codice)
uvicorn server:app --reload      # terminale 1: il server
python prova_chat.py             # terminale 2: il test
```

## Passi
1. **System prompt.** Sostituisci `SYSTEM` con il prompt del blocco 1 (`../blocco1/system_prompt_template.txt`), riempito con il `listino.json` di **questa** cartella.
2. **TODO 1 – storia per sessione.** `STORIE` è un dizionario `session_id → lista di messaggi`. Se il `session_id` non c'è, crea una lista vuota.
3. **TODO 2 – messaggio utente.** Aggiungi `{"role": "user", "content": req.messaggio}` alla storia.
4. **TODO 3 – finestra e riassunto.** Quando la storia supera **12 messaggi**, riassumi con il modello quelli più vecchi e tieni interi solo gli **ultimi 6**. Il riassunto va nel system prompt (es. dentro `<riassunto_conversazione>`). Attenzione: la lista che mandi al modello deve iniziare con un messaggio `user`.
5. **TODO 4 – risposta.** Chiama il modello, aggiungi la risposta come messaggio `assistant`, stampa a terminale `input_tokens`, `output_tokens` e numero di messaggi.

## Fatto quando
- [ ] `prova_chat.py` arriva in fondo senza errori.
- [ ] Al turno 13–15 il bot ricorda ancora **nome (Giulia), misure (120×180×30) e legno (rovere)** detti all'inizio.
- [ ] La seconda sessione **non** conosce il nome di Giulia.
- [ ] Sai spiegare perché `input_tokens` cresce a ogni turno e perché cala dopo il riassunto.

## Errori tipici
- Storia globale invece che per sessione → le due sessioni si mescolano.
- Finestra che parte da un messaggio `assistant` → errore 400 dell'API.
- Riassunto che perde i dati del cliente → nel prompt del riassunto chiedi esplicitamente di tenere nome, misure, legno, finitura.
