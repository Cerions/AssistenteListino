# Blocco 2 · Chat con memoria su /chat: considerazioni

Server FastAPI (`server.py`) con una storia di conversazione per ogni `session_id`. Modello: `claude-haiku-5-5`, nessun parametro `temperature`. Quando la storia supera 12 messaggi, i più vecchi vengono riassunti e restano interi solo gli ultimi.

## 1. Come funziona

- **Storia per sessione**: `STORIE` è un dizionario `session_id → lista di messaggi`. Una sessione nuova parte da una lista vuota, quindi sessioni diverse non si mescolano.
- **Finestra e riassunto**: quando la storia supera 12 messaggi, i messaggi più vecchi vengono riassunti dal modello e in storia restano gli ultimi. Il riassunto va nel system prompt dentro `<riassunto_conversazione>`.
- **La finestra inizia sempre con un messaggio `user`**, altrimenti l'API risponde 400. Con 13 messaggi, gli ultimi 6 inizierebbero con un messaggio dell'assistente: il codice torna indietro di uno e ne tiene 7 (nei log: `messaggi 13 -> 7`).
- **Il riassunto è cumulativo**: il prompt del riassunto riceve anche il riassunto precedente e chiede di integrarlo. Chiede esplicitamente di conservare nome, misure, legno, finitura, consegna e decisioni prese.
- **Nella storia si salva solo il testo** della risposta, non i blocchi `thinking`.
- **Risposta vuota**: se il modello non produce testo (es. limite di token raggiunto durante il thinking), l'ultimo messaggio utente viene tolto, per non rompere l'alternanza dei ruoli.

## 2. Esito di `prova_chat.py`

- Arriva in fondo senza errori.
- Ai turni 13–15 il bot ricorda Giulia, rovere e 120×180×30 cm, anche se ormai i messaggi dei primi turni non sono più nella lista mandata al modello: quei dati vengono dal riassunto.
- La seconda sessione non conosce Giulia (input 565 token, storia di 2 messaggi).
- Dove il listino non ha il dato (orari di apertura, colore dei legni, descrizione delle finiture) il bot lo dichiara e non inventa.
- Conti corretti: superficie 2×(120×180 + 120×30 + 180×30) = 61.200 cm² = 6,12 m²; rovere 6,12 × 180 = 1.101,60 €.

## 3. Token per turno (dai log del server)

| Turno | Messaggi in storia | Input | Output | Nota |
|---|---|---|---|---|
| 1 | 2 | 580 | 256 | |
| 2 | 4 | 861 | 742 | |
| 3 | 6 | 1160 | 442 | |
| 4 | 8 | 1377 | 255 | |
| 5 | 10 | 1653 | 216 | |
| 6 | 12 | 1881 | 177 | |
| 7 | 8 | 1607 | 102 | riassunto: 1026 in / 550 out |
| 8 | 10 | 1732 | 168 | |
| 9 | 12 | 1916 | 162 | |
| 10 | 8 | 1575 | 76 | riassunto: 1245 in / 874 out |
| 11 | 10 | 1667 | 147 | |
| 12 | 12 | 1830 | 322 | |
| 13 | 8 | 1915 | 59 | riassunto: 1210 in / 955 out |
| 14 | 10 | 1987 | 110 | |
| 15 | 12 | 2104 | 79 | |
| Sessione nuova | 2 | 565 | 89 | nessuna storia |

## 4. Sai spiegare perché `input_tokens` cresce a ogni turno e perché cala dopo il riassunto?

**Perché cresce.** Il modello non ricorda nulla tra una chiamata e l'altra: l'API non ha stato. A ogni turno il server rimanda il system prompt (circa 550 token tra istruzioni e listino) più tutta la storia della conversazione. Ogni turno aggiunge due messaggi (domanda e risposta), quindi l'input sale di circa 220–300 token a turno (580 → 861 → 1160 → 1377 → 1653 → 1881).

Il thinking si paga come output ma non rientra nell'input dei turni successivi, perché nella storia salviamo solo il testo. Esempio: al turno 2 l'output è 742 token, ma l'input del turno 3 cresce solo di 299.

**Perché cala dopo il riassunto.** Quando la storia supera 12 messaggi, i messaggi più vecchi vengono sostituiti da un riassunto, che è molto più corto della conversazione originale. Dopo il primo riassunto l'input scende da 1881 a 1607, perché si rimandano 7 messaggi invece di 13 più il riassunto.

**Cosa mostrano davvero i numeri:**

- Il calo è modesto e l'input non torna a ~600, perché restano nel prompt il riassunto e gli ultimi messaggi.
- Il riassunto cresce a ogni giro (output 550 → 874 → 955) perché è cumulativo, quindi il risparmio diminuisce. Al terzo riassunto l'input non cala più (1830 → 1915).
- Il riassunto ha un costo: sono chiamate in più. Nel test sono circa 0,015 $ su 0,056 $ totali (Haiku 5.5, 1 $ e 5 $ per milione di token, escluso l'invio della sessione nuova). Una stima semplice senza riassunti, supponendo una crescita costante di ~260 token a turno, dà circa 0,053 $: in 15 turni il costo è praticamente uguale. Il riassunto conviene su conversazioni più lunghe, dove senza finestra l'input crescerebbe senza limite e il costo totale salirebbe quasi con il quadrato del numero di turni.

## 5. Limiti e possibili miglioramenti

- **Memoria in RAM**: `STORIE` e `RIASSUNTI` vivono nel processo. Se il server si riavvia (anche per il `--reload` quando si modifica un file), tutte le sessioni spariscono. Per un servizio vero servirebbe un database o una cache condivisa.
- **Accessi concorrenti**: le richieste della stessa sessione non sono protette da lock; due richieste simultanee potrebbero rovinare l'ordine della storia.
- **Riassunto più corto**: per frenare la crescita si può chiedere nel prompt un limite di lunghezza (ad esempio 120 parole), mantenendo sempre nome, misure, legno e finitura.
- **Soglie fisse**: 12 messaggi e 6 da tenere sono scelte della consegna; si potrebbe ragionare in token invece che in numero di messaggi.
