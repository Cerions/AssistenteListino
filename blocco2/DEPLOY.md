# Pubblicare il server della chat su Vercel

Il sito (Netlify) è statico, quindi il server della chat sta a parte: `server.py` gira su Vercel, nel piano gratuito (Hobby). Vercel riconosce da solo un'app FastAPI in un file `server.py` che contiene `app = FastAPI()`.

## Come funziona la memoria

Su Vercel il server non ricorda nulla tra un messaggio e l'altro (ogni richiesta può cadere su un'istanza diversa). Per questo, **quando c'è `LISTINO_URL`** la conversazione sta nel browser del cliente: a ogni messaggio la webapp rimanda al server la storia e il riassunto, e il server li restituisce aggiornati. Senza `LISTINO_URL` (l'esercizio, in locale) la memoria resta nel server, per sessione, come nel blocco 2.

## Variabili d'ambiente

| Variabile | Obbligatoria | Valore |
|---|---|---|
| `ANTHROPIC_API_KEY` | sì | la chiave API, **solo qui** su Vercel, mai nel repository |
| `LISTINO_URL` | sì | `https://legnoco-preventivo.netlify.app/listino.json` |
| `ALLOWED_ORIGINS` | consigliata | `https://legnoco-preventivo.netlify.app` (più indirizzi si separano con la virgola) |

## Passi

1. Su vercel.com accedi con GitHub, poi **Add New → Project** e scegli il repository `AssistenteListino`.
2. **Root Directory:** clicca *Edit* e scegli `blocco2`. Il preset dovrebbe diventare *FastAPI*; lascia vuoti Build e Output.
3. Apri **Environment Variables** e inserisci le tre variabili della tabella.
4. Clicca **Deploy** e aspetta che finisca.
5. Prendi l'indirizzo del progetto (tipo `https://assistente-listino.vercel.app`, nella pagina del progetto sotto *Domains*) e aprilo con `/salute` in fondo: deve rispondere `{"ok":true}`.
   - Se vedi invece una pagina di accesso o un errore 401, vai in *Settings → Deployment Protection* e disattiva *Vercel Authentication* per il progetto, poi riprova.
6. Su Netlify, *Project configuration → Environment variables*: `VITE_CHAT_URL` = `https://assistente-listino.vercel.app/chat` (metti il tuo indirizzo, con `/chat` alla fine), poi nuova pubblicazione del sito. Senza questa variabile la chat non compare.

## Cose da sapere

- Il limite di 30 messaggi ogni 10 minuti per indirizzo IP è in memoria dell'istanza: su Vercel è un freno, non una garanzia. Il vero argine alla spesa è il limite mensile da impostare nella console di Anthropic.
- Ogni messaggio ha al massimo 1000 caratteri e la conversazione inviata è limitata (14 messaggi, poi i più vecchi diventano riassunto).
- Il primo messaggio dopo un po' di inattività può essere più lento (avvio a freddo di qualche secondo).
- Se la chat dà errore nel browser ma `/salute` funziona, controlla che `ALLOWED_ORIGINS` coincida esattamente con l'indirizzo del sito.
- `system_prompt_template.txt` in questa cartella è una copia di quello del blocco 1: serve perché Vercel pubblica solo la cartella `blocco2`. Se modifichi il prompt, aggiorna entrambi.
