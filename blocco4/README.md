# Blocco 4 · Carrello e preventivo con i tool

**Obiettivo:** il bot non *dice* i prezzi, li fa *calcolare* al tuo codice. Il modello sceglie quale tool chiamare; il server lo esegue e gli restituisce il risultato.

## Cosa trovi nella cartella
| File | A cosa serve |
|---|---|
| `tools_schema.json` | I 6 tool da passare al modello (`tools=`): cerca, aggiungi, mostra, rimuovi, svuota, preventivo |
| `prodotti.json` | Catalogo di 60 prodotti, con misure min/max e legni ammessi |
| `listino.json` · `preventivo.py` | Prezzi e calcolo esatto (`calcola_preventivo`, `euro`) |
| `casi_di_prova.json` | 12 casi con il risultato atteso di `calcola_preventivo` (anche errori) |
| `scenari.md` | 10 conversazioni che il bot deve superare |

## Passi
1. **Prova il calcolo.** Fai girare i 12 `casi_di_prova.json` su `calcola_preventivo` e confronta con `atteso`: devono coincidere tutti, compresi i messaggi di errore.
2. **Scrivi le 6 funzioni Python**, una per tool. Ognuna riceve anche il `session_id` (lo passa il server, **non** il modello) e restituisce una **stringa**.
3. **Ciclo tool** nel `/chat`:
   1. chiami il modello con `tools=`;
   2. se `stop_reason == "tool_use"` esegui ogni blocco `tool_use` e rimandi i `tool_result` (stesso `tool_use_id`);
   3. ripeti finché il modello risponde con testo, **al massimo 6 giri**.
4. **Regole di sicurezza (obbligatorie):**
   - il carrello sta sul server, in un dizionario `session_id → righe`;
   - i prezzi vengono da `listino.json` / `preventivo.py`, **mai** dagli argomenti del tool;
   - valida tutto: prodotto esistente, legno tra quelli ammessi dal prodotto, misure nei limiti del prodotto, quantità 1–20;
   - in caso di errore restituisci `"Errore: ..."` con `is_error: true` nel `tool_result`;
   - `svuota_carrello` funziona solo con `confermato: true`, e il modello deve averlo chiesto prima all'utente.

## Fatto quando
- [ ] I 12 casi di prova coincidono con `atteso`.
- [ ] I 10 scenari di `scenari.md` passano.
- [ ] Il totale dello scenario 3 coincide con il calcolo a mano (lo trovi spiegato nello scenario).
