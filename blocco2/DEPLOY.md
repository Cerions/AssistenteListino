# Pubblicare il server della chat (Render)

Il server serve la chat del preventivatore (`https://legnoco-preventivo.netlify.app`). Netlify ospita solo il sito statico: `server.py` gira su un servizio a parte.

## Variabili d'ambiente

| Variabile | Obbligatoria | Valore |
|---|---|---|
| `ANTHROPIC_API_KEY` | sì | la chiave API, **solo qui** nelle impostazioni del servizio, mai nel repository |
| `LISTINO_URL` | sì, per la chat del sito | `https://legnoco-preventivo.netlify.app/listino.json` |
| `ALLOWED_ORIGINS` | no | origini autorizzate, separate da virgole. Predefinite: `localhost:5173`, `127.0.0.1:5173` e il sito su Netlify |

Con `LISTINO_URL` impostata il server legge i prezzi dal listino pubblicato dalla webapp (riletto al massimo una volta al minuto) e attiva il limite di 30 messaggi ogni 10 minuti per indirizzo IP. Senza, usa il `listino.json` locale, come nell'esercizio.

## Render

1. *New → Web Service*, scegli il repository `AssistenteListino`, ramo `main`. Lascia vuoto *Root Directory*.
2. Runtime: Python. Imposta anche la variabile `PYTHON_VERSION` (ad esempio `3.13`).
3. Build command: `pip install -r blocco2/requirements.txt`
4. Start command: `uvicorn --app-dir blocco2 server:app --host 0.0.0.0 --port $PORT`
5. Health check path: `/salute`
6. Aggiungi le variabili della tabella e pubblica. L'indirizzo del servizio sarà tipo `https://nome-servizio.onrender.com`.

## Collegare la webapp

Su Netlify, *Project configuration → Environment variables*: `VITE_CHAT_URL` = `https://nome-servizio.onrender.com/chat`, poi nuova pubblicazione del sito. Non è un segreto: è l'indirizzo pubblico del server. Senza questa variabile la chat non compare.

## Cose da sapere

- Sul piano gratuito il servizio si spegne dopo un po' di inattività: il primo messaggio può metterci circa un minuto.
- Le conversazioni stanno in memoria: ogni riavvio le cancella.
- Imposta un limite di spesa mensile nella console di Anthropic: il server è pubblico e ogni messaggio costa.
- Verifica `https://nome-servizio.onrender.com/salute`: deve rispondere `{"ok": true}`.
