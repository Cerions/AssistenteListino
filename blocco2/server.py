import json
import os
import threading
import time
import urllib.request
from collections import deque
from datetime import date
from pathlib import Path

import anthropic
from anthropic import Anthropic
from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Carica ANTHROPIC_API_KEY da un file .env (cercato in questa cartella e in quelle
# superiori). Una variabile già impostata nell'ambiente ha la precedenza.
load_dotenv(find_dotenv())

BASE = Path(__file__).parent

app = FastAPI()
client = Anthropic()  # legge ANTHROPIC_API_KEY dall'ambiente
MODEL = "claude-haiku-5-5"

MAX_MESSAGGI = 12   # oltre questa soglia si riassumono i messaggi più vecchi
TIENI_ULTIMI = 6    # messaggi tenuti interi dopo il riassunto
MAX_TOKENS = 2000   # il thinking conta come output: non scendere troppo

# ---------------------------------------------------------------------------
# Due modalità:
#  - locale (esercizio del blocco 2): il listino è il listino.json di questa cartella;
#  - sito: se è impostata LISTINO_URL, il listino si legge da quell'indirizzo (quello
#    pubblicato dalla webapp, unico posto dei prezzi) e valgono anche i limiti
#    anti-abuso e le regole aggiuntive per la chat del sito.
# ---------------------------------------------------------------------------
LISTINO_URL = os.getenv("LISTINO_URL", "").strip()
MODALITA_SITO = bool(LISTINO_URL)
if MODALITA_SITO and not LISTINO_URL.startswith(("https://", "http://")):
    raise RuntimeError("LISTINO_URL deve iniziare con https:// (o http:// in locale).")

# Origini autorizzate a chiamare /chat dal browser (CORS), separate da virgole.
ORIGINI_AMMESSE = [
    o.strip()
    for o in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,https://legnoco-preventivo.netlify.app",
    ).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGINI_AMMESSE,
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)

DURATA_CACHE_LISTINO = 60  # secondi: dopo una modifica del titolare la chat si aggiorna entro un minuto
LIMITE_RICHIESTE = 30      # messaggi per indirizzo IP...
FINESTRA_SECONDI = 600     # ...ogni 10 minuti (solo in modalità sito)
MAX_SESSIONI = 500         # oltre, si dimentica la sessione più vecchia

REGOLE_SITO = (
    "\n\n<regole_sito>\n"
    "- Sei nella chat del sito di Legno & Co., accanto al preventivatore.\n"
    "- Il prezzo ufficiale è quello che il preventivatore mostra nella pagina: per un totale "
    "preciso invita il cliente a inserire lì misure e scelte. Le cifre che dai in chat sono "
    "indicative.\n"
    "- Non chiedere né ripetere dati personali (cognome, telefono, email, indirizzo): non "
    "servono per il preventivo.\n"
    "</regole_sito>"
)


class ListinoNonDisponibile(Exception):
    pass


def carica_template():
    """Template del blocco 1 (system_prompt_template.txt)."""
    candidati = [
        BASE / "system_prompt_template.txt",
        BASE.parent / "blocco1" / "system_prompt_template.txt",
    ]
    for percorso in candidati:
        if percorso.exists():
            return percorso.read_text(encoding="utf-8")
    raise FileNotFoundError(
        "system_prompt_template.txt non trovato: copialo in questa cartella."
    )


TEMPLATE = carica_template()


def normalizza_listino(listino):
    """Porta il listino nel formato del prompt (dizionari nome -> prezzo).

    Accetta il formato locale del blocco 2 e quello della webapp (liste di voci).
    Solleva ValueError se il listino non è leggibile o contiene prezzi non validi.
    """
    try:
        if isinstance(listino["legni"], dict):
            risultato = listino
        else:
            risultato = {
                "legni": {v["nome"]: v["prezzoMq"] for v in listino["legni"]},
                "finiture": {v["nome"]: v["supplementoMq"] for v in listino["finiture"]},
                "consegne": {v["nome"]: v["costo"] for v in listino["consegne"]},
                "parametri": {
                    "iva": listino["aliquotaIva"],
                    "misura_min_cm": listino["misure"]["minimaCm"],
                    "misura_max_cm": listino["misure"]["massimaCm"],
                },
            }
        valori = [
            *risultato["legni"].values(),
            *risultato["finiture"].values(),
            *risultato["consegne"].values(),
            *risultato["parametri"].values(),
        ]
    except (KeyError, TypeError, AttributeError) as e:
        raise ValueError(f"listino in un formato non riconosciuto: {e!r}") from e
    for v in valori:
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
            raise ValueError(f"valore non valido nel listino: {v!r}")
    return risultato


def leggi_listino():
    if MODALITA_SITO:
        richiesta = urllib.request.Request(
            LISTINO_URL,
            headers={"Cache-Control": "no-cache", "User-Agent": "legnoco-chat"},
        )
        with urllib.request.urlopen(richiesta, timeout=5) as risposta:
            return json.loads(risposta.read().decode("utf-8"))
    return json.loads((BASE / "listino.json").read_text(encoding="utf-8"))


_cache_listino = {"testo": None, "quando": 0.0}
_lock_listino = threading.Lock()


def listino_in_prompt():
    """Testo del listino per il prompt, riletto al massimo una volta al minuto."""
    with _lock_listino:
        adesso = time.monotonic()
        testo = _cache_listino["testo"]
        if testo and adesso - _cache_listino["quando"] < DURATA_CACHE_LISTINO:
            return testo
        try:
            nuovo = json.dumps(
                normalizza_listino(leggi_listino()), ensure_ascii=False, indent=2
            )
        except Exception as e:  # rete assente, JSON rotto, prezzo negativo...
            if testo:
                print(f"[listino] aggiornamento fallito, uso l'ultima copia valida: {e}")
                # riprova fra 10 secondi, non a ogni messaggio
                _cache_listino["quando"] = adesso - DURATA_CACHE_LISTINO + 10
                return testo
            raise ListinoNonDisponibile(str(e)) from e
        _cache_listino.update(testo=nuovo, quando=adesso)
        return nuovo


def carica_system():
    """Template riempito con il listino corrente e con la data di oggi."""
    testo = TEMPLATE.replace("{LISTINO_JSON}", listino_in_prompt()).replace(
        "{DATA_ODIERNA}", date.today().strftime("%d/%m/%Y")
    )
    if MODALITA_SITO:
        testo += REGOLE_SITO
    return testo


PROMPT_RIASSUNTO = (
    "Riassumi la conversazione tra un cliente e l'assistente di una falegnameria. "
    "Scrivi in italiano, in modo sintetico, ma conserva SEMPRE: il nome del cliente, "
    "le misure del mobile, il legno, la finitura, la consegna e ogni scelta o decisione "
    "presa. Conserva anche le domande a cui l'assistente non ha saputo rispondere. "
    "Se ti viene dato un riassunto precedente, integralo con i nuovi messaggi "
    "senza perdere nessun dato già presente."
)

STORIE = {}      # session_id -> lista di messaggi interi
RIASSUNTI = {}   # session_id -> riassunto dei messaggi più vecchi
LOCK_SESSIONI = {}  # session_id -> lock: una richiesta alla volta per sessione
_richieste_ip = {}  # indirizzo IP -> istanti delle ultime richieste


class Richiesta(BaseModel):
    session_id: str = Field(min_length=8, max_length=64)
    messaggio: str = Field(min_length=1, max_length=1000)


def estrai_testo(r):
    # il thinking arriva in blocchi separati: si prende solo il testo
    return "".join(b.text for b in r.content if b.type == "text")


def system_con_riassunto(session_id):
    base = carica_system()
    riassunto = RIASSUNTI.get(session_id)
    if not riassunto:
        return base
    return (
        base
        + "\n\n<riassunto_conversazione>\n"
        + riassunto
        + "\n</riassunto_conversazione>"
    )


def comprimi(session_id):
    """Riassume i messaggi vecchi e lascia in storia solo gli ultimi."""
    storia = STORIE[session_id]

    # la finestra tenuta deve iniziare con un messaggio user (altrimenti errore 400)
    inizio = len(storia) - TIENI_ULTIMI
    while inizio > 0 and storia[inizio]["role"] != "user":
        inizio -= 1
    if inizio <= 0:
        return

    vecchi = storia[:inizio]
    trascrizione = "\n".join(
        f"{'Cliente' if m['role'] == 'user' else 'Assistente'}: {m['content']}"
        for m in vecchi
    )
    precedente = RIASSUNTI.get(session_id)
    contenuto = ""
    if precedente:
        contenuto += f"Riassunto precedente:\n{precedente}\n\n"
    contenuto += f"Nuovi messaggi da integrare:\n{trascrizione}"

    r = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=PROMPT_RIASSUNTO,
        messages=[{"role": "user", "content": contenuto}],
    )
    RIASSUNTI[session_id] = estrai_testo(r)
    STORIE[session_id] = storia[inizio:]
    print(
        f"[riassunto] sessione {session_id[:8]} | input: {r.usage.input_tokens} | "
        f"output: {r.usage.output_tokens} | messaggi {len(storia)} -> "
        f"{len(STORIE[session_id])}"
    )


def indirizzo_client(request: Request):
    inoltrato = request.headers.get("x-forwarded-for")
    if inoltrato:
        return inoltrato.split(",")[0].strip()
    return request.client.host if request.client else "sconosciuto"


def controlla_limite(ip):
    """Al massimo LIMITE_RICHIESTE messaggi ogni FINESTRA_SECONDI per indirizzo IP."""
    ora = time.monotonic()
    if len(_richieste_ip) > 2000:  # ripulisce chi non scrive più da un po'
        for k in [k for k, v in _richieste_ip.items() if not v or ora - v[-1] > FINESTRA_SECONDI]:
            del _richieste_ip[k]
    coda = _richieste_ip.setdefault(ip, deque())
    while coda and ora - coda[0] > FINESTRA_SECONDI:
        coda.popleft()
    if len(coda) >= LIMITE_RICHIESTE:
        raise HTTPException(
            status_code=429,
            detail="Troppi messaggi in poco tempo. Riprova fra qualche minuto.",
        )
    coda.append(ora)


def annulla_ultimo_messaggio(storia):
    # se qualcosa va storto si toglie la domanda dalla storia, così il cliente può riprovare
    if storia and storia[-1]["role"] == "user":
        storia.pop()


@app.get("/salute")
def salute():
    return {"ok": True}


@app.post("/chat")
def chat(req: Richiesta, request: Request):
    if MODALITA_SITO:
        controlla_limite(indirizzo_client(request))

    domanda = req.messaggio.strip()
    if not domanda:
        raise HTTPException(status_code=400, detail="Scrivi un messaggio.")

    sid = req.session_id
    with LOCK_SESSIONI.setdefault(sid, threading.Lock()):
        # TODO 1: storia di questa sessione (creata vuota se non esiste)
        if sid not in STORIE and len(STORIE) >= MAX_SESSIONI:
            vecchia = next(iter(STORIE))
            STORIE.pop(vecchia, None)
            RIASSUNTI.pop(vecchia, None)
            LOCK_SESSIONI.pop(vecchia, None)
        storia = STORIE.setdefault(sid, [])

        # TODO 2: messaggio dell'utente
        storia.append({"role": "user", "content": domanda})

        try:
            # TODO 3: se la storia è troppo lunga, riassumi i messaggi più vecchi
            if len(storia) > MAX_MESSAGGI:
                comprimi(sid)
                storia = STORIE[sid]

            # TODO 4: chiamata al modello, risposta in storia, token a terminale
            r = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system_con_riassunto(sid),
                messages=storia,
            )
        except ListinoNonDisponibile as e:
            annulla_ultimo_messaggio(storia)
            print(f"[errore] listino non disponibile: {e}")
            raise HTTPException(
                status_code=503,
                detail="Il listino non è disponibile in questo momento.",
            )
        except anthropic.APIError as e:
            annulla_ultimo_messaggio(storia)
            print(f"[errore] chiamata al modello fallita: {e!r}")
            raise HTTPException(
                status_code=502,
                detail="L'assistente non è raggiungibile in questo momento.",
            )

        testo = estrai_testo(r)
        if not testo:
            # risposta vuota (es. limite di token raggiunto durante il thinking):
            # tolgo l'ultimo messaggio user per non rompere l'alternanza dei ruoli
            storia.pop()
            return {"risposta": "Non sono riuscito a rispondere, riprova."}

        storia.append({"role": "assistant", "content": testo})
        print(
            f"[chat] sessione {sid[:8]} | input: {r.usage.input_tokens} | "
            f"output: {r.usage.output_tokens} | messaggi in storia: {len(storia)}"
        )
        return {"risposta": testo}
