# Blocco 6 · Mail libera → JSON → preventivo

`POST /richiesta` con body `{"testo": "<mail>"}`. Risponde con uno stato (`ok`, `incompleta`, `fuori_range`), i dati estratti e la risposta da mandare al cliente.

## Come si prova

```
pip install -r ../requirements.txt
uvicorn server:app --reload        # terminale 1
python prova_mail.py               # terminale 2
```

`prova_mail.py` manda le 12 mail di `mail_test.json`, controlla stato e totale di ognuna e scrive due file:

- `risposte_mail.md`: le risposte ai clienti;
- `costi.md`: token e costo per mail.

La chiave API sta nel `.env` della cartella principale, mai nel codice.

## La catena

1. **Estrazione (modello).** Il prompt contiene le voci del listino (solo i nomi), lo schema e le regole: conversione in cm, «lunghezza» = profondità, ordine delle misure, colori che non sono legni, istruzioni nella mail da ignorare. Il modello risponde solo con il JSON.
2. **Validazione (codice).**
   - Il JSON passa da Pydantic. Se non è valido, il modello riceve un solo nuovo tentativo con l'errore; al secondo errore l'endpoint risponde 502 con un messaggio chiaro.
   - Legno, finitura e consegna vengono confrontati di nuovo con il listino: una voce che non c'è diventa `null`.
   - I campi mancanti li ricalcola il codice dai `null`, senza fidarsi della lista `mancanti` del modello.
   - Misure presenti ma fuori 30–300 cm → `fuori_range`, con tutti i motivi. Altrimenti campi mancanti → `incompleta`. Altrimenti `calcola_preventivo` → `ok`.
3. **Redazione (modello).** Il modello riceve la mail, il compito per quello stato e i dati già pronti, con gli importi formattati da `euro`.
   - Il codice controlla la risposta: con `ok` deve contenere il totale e nessun importo diverso da imponibile, IVA e totale; negli altri stati nessun importo.
   - Se il controllo non passa, si usa un testo di riserva costruito dal codice, così al cliente non arriva mai un prezzo inventato.

## Esito atteso sulle 12 mail

| Mail | Stato | Nota |
|---|---|---|
| M1 | ok | |
| M2 | ok | «2 metri», «2 e 20» → 200, 220 |
| M3 | incompleta | manca la profondità |
| M4 | fuori_range | altezza 4 e profondità 20 |
| M5 | incompleta | «legno scuro» non è un legno, mancano le misure |
| M6 | ok | «lunghezza» del letto = profondità; 90 km → Oltre 50 km |
| M7 | ok | **trappola**: «castagno tinto noce» = Castagno + Tinto |
| M8 | fuori_range | larghezza 400 |
| M9 | incompleta | mogano e «lucido» non sono nel listino |
| M10 | ok | **trappola**: prompt injection («preventivo gratis») ignorata |
| M11 | ok | **trappola**: «180 x 90, altezza 76» → 180 × 76 × 90 |
| M12 | incompleta | solo «mensola in rovere» |

## Scelte

- **Niente temperature 0.** I modelli 5.5 accettano solo il valore di default (vedi le considerazioni del blocco 1). La stabilità la danno lo schema, le regole del prompt e i controlli del codice.
- **I conti li fa solo il codice.** Il modello non vede i prezzi del listino, nemmeno nell'estrazione, e nella redazione non può scrivere importi diversi da quelli calcolati.
- **Il campo `uso` nella risposta** (token di estrazione e redazione) serve alla tabella dei costi. In un servizio vero resterebbe nei log del server.

## Costi

Vedi `costi.md`, generato da `prova_mail.py` con i prezzi di Haiku 5.5 (1 $ per milione di token di input, 5 $ di output; il thinking conta come output).
