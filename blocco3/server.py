"""Blocco 3 · Il bot nel sito, con il catalogo.

Parte dal server del blocco 2 (memoria per sessione e riassunto) e aggiunge:
- catalogo (prodotti.json) e listino (listino.json) nel system prompt, dentro <catalogo> e <listino>;
- controllo del catalogo all'avvio (misure tra 30 e 300 cm, legni presenti nel listino);
- CORS per widget.html aperto con Live Server o con doppio clic;
- messaggi di al massimo 500 caratteri e max_tokens fisso.
La chiave API resta qui: il browser chiama solo /chat.
"""
import json
import threading
from datetime import date
from pathlib import Path

import anthropic
from anthropic import Anthropic
from dotenv import find_dotenv, load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Carica ANTHROPIC_API_KEY dal .env (cercato in questa cartella e in quelle superiori).
load_dotenv(find_dotenv())

BASE = Path(__file__).parent

app = FastAPI()
client = Anthropic()  # legge ANTHROPIC_API_KEY dall'ambiente
MODEL = "claude-haiku-5-5"

MAX_MESSAGGI = 12            # oltre questa soglia si riassumono i messaggi più vecchi
TIENI_ULTIMI = 6             # messaggi tenuti interi dopo il riassunto
MAX_TOKENS = 2000            # il thinking conta come output: non scendere troppo
MAX_CARATTERI_MESSAGGIO = 500
MAX_SESSIONI = 500           # oltre, si dimentica la sessione più vecchia

# Chi può chiamare /chat dal browser. 5500 è la porta di Live Server; "null" è
# l'origine di una pagina aperta con doppio clic (file://). Solo per le prove in locale.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "null",
    ],
    allow_methods=["POST"],
    allow_headers=["Content-Type"],
)


# ---------------------------------------------------------------------------
# Catalogo e listino
# ---------------------------------------------------------------------------
LISTINO = json.loads((BASE / "listino.json").read_text(encoding="utf-8"))
PRODOTTI = json.loads((BASE / "prodotti.json").read_text(encoding="utf-8"))
DIMENSIONI = ("larghezza", "altezza", "profondita")


def controlla_catalogo(prodotti, listino):
    """Restituisce l'elenco dei problemi del catalogo (lista vuota se è tutto a posto)."""
    p = listino["parametri"]
    lo, hi = p["misura_min_cm"], p["misura_max_cm"]
    problemi = []
    visti = set()
    for prod in prodotti:
        nome = f"{prod.get('id', '?')} {prod.get('nome', '?')}"
        if prod["id"] in visti:
            problemi.append(f"{nome}: id ripetuto")
        visti.add(prod["id"])
        for d in DIMENSIONI:
            minima = prod["misure_min_cm"][d]
            tipica = prod["misura_tipica_cm"][d]
            massima = prod["misure_max_cm"][d]
            if not lo <= minima <= tipica <= massima <= hi:
                problemi.append(
                    f"{nome}: {d} {minima}/{tipica}/{massima} non rispetta "
                    f"{lo} ≤ minima ≤ tipica ≤ massima ≤ {hi}"
                )
        if not prod["legni_ammessi"]:
            problemi.append(f"{nome}: nessun legno ammesso")
        for legno in prod["legni_ammessi"]:
            if legno not in listino["legni"]:
                problemi.append(f"{nome}: il legno {legno} non è nel listino")
    return problemi


_problemi = controlla_catalogo(PRODOTTI, LISTINO)
if _problemi:
    raise RuntimeError("Catalogo non valido:\n- " + "\n- ".join(_problemi))
print(f"[catalogo] {len(PRODOTTI)} prodotti controllati: tutto ok")


def catalogo_in_prompt(prodotti):
    """Una riga per prodotto: più corta del JSON, quindi meno token a ogni chiamata."""
    righe = []
    for p in prodotti:
        mn, mx, t = p["misure_min_cm"], p["misure_max_cm"], p["misura_tipica_cm"]
        misure = ", ".join(
            f"{sigla} {mn[d]}–{mx[d]}" for sigla, d in zip("LAP", DIMENSIONI)
        )
        tipica = "×".join(str(t[d]) for d in DIMENSIONI)
        righe.append(
            f"{p['id']} | {p['nome']} | {p['categoria']} | {misure} | "
            f"tipica {tipica} | legni: {', '.join(p['legni_ammessi'])} | "
            f"{p['tempi_consegna_giorni']} giorni | {p['descrizione']}"
        )
    return "\n".join(righe)


def carica_system():
    template = (BASE / "system_prompt_template.txt").read_text(encoding="utf-8")
    return (
        template.replace("{CATALOGO}", catalogo_in_prompt(PRODOTTI))
        .replace("{LISTINO_JSON}", json.dumps(LISTINO, ensure_ascii=False, indent=2))
        .replace("{DATA_ODIERNA}", date.today().strftime("%d/%m/%Y"))
    )


SYSTEM = carica_system()


# ---------------------------------------------------------------------------
# Memoria e riassunto (come nel blocco 2)
# ---------------------------------------------------------------------------
PROMPT_RIASSUNTO = (
    "Riassumi la conversazione tra un cliente e l'assistente di una falegnameria. "
    "Scrivi in italiano, in modo sintetico, ma conserva SEMPRE: il nome del cliente, "
    "il prodotto scelto, le misure del mobile, il legno, la finitura, la consegna e ogni "
    "scelta o decisione presa. Conserva anche le domande a cui l'assistente non ha saputo "
    "rispondere. Se ti viene dato un riassunto precedente, integralo con i nuovi messaggi "
    "senza perdere nessun dato già presente."
)

STORIE = {}         # session_id -> lista di messaggi interi
RIASSUNTI = {}      # session_id -> riassunto dei messaggi più vecchi
LOCK_SESSIONI = {}  # session_id -> lock: una richiesta alla volta per sessione


class Richiesta(BaseModel):
    session_id: str = Field(min_length=8, max_length=64)
    messaggio: str  # la lunghezza si controlla in chat(), per dare un errore in italiano


def estrai_testo(r):
    # il thinking arriva in blocchi separati: si prende solo il testo
    return "".join(b.text for b in r.content if b.type == "text")


def system_con_riassunto(riassunto):
    if not riassunto:
        return SYSTEM
    return SYSTEM + "\n\n<riassunto_conversazione>\n" + riassunto + "\n</riassunto_conversazione>"


def comprimi(storia, riassunto):
    """Riassume i messaggi vecchi. Restituisce (storia con solo gli ultimi, nuovo riassunto)."""
    # la finestra tenuta deve iniziare con un messaggio user (altrimenti errore 400)
    inizio = len(storia) - TIENI_ULTIMI
    while inizio > 0 and storia[inizio]["role"] != "user":
        inizio -= 1
    if inizio <= 0:
        return storia, riassunto

    trascrizione = "\n".join(
        f"{'Cliente' if m['role'] == 'user' else 'Assistente'}: {m['content']}"
        for m in storia[:inizio]
    )
    contenuto = f"Riassunto precedente:\n{riassunto}\n\n" if riassunto else ""
    contenuto += f"Nuovi messaggi da integrare:\n{trascrizione}"

    r = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=PROMPT_RIASSUNTO,
        messages=[{"role": "user", "content": contenuto}],
    )
    nuovo = estrai_testo(r) or riassunto  # se il riassunto viene vuoto si tiene il vecchio
    print(
        f"[riassunto] input: {r.usage.input_tokens} | output: {r.usage.output_tokens} | "
        f"messaggi {len(storia)} -> {len(storia) - inizio}"
    )
    return storia[inizio:], nuovo


def rispondi(storia, riassunto, domanda):
    """Un turno di conversazione. Restituisce (testo, nuova storia, nuovo riassunto)."""
    nuova = [*storia, {"role": "user", "content": domanda}]
    if len(nuova) > MAX_MESSAGGI:
        nuova, riassunto = comprimi(nuova, riassunto)

    r = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_con_riassunto(riassunto),
        messages=nuova,
    )
    testo = estrai_testo(r)
    if not testo:
        # risposta vuota (es. limite di token raggiunto durante il thinking)
        return "", storia, riassunto

    nuova.append({"role": "assistant", "content": testo})
    print(
        f"[chat] input: {r.usage.input_tokens} | output: {r.usage.output_tokens} | "
        f"messaggi in storia: {len(nuova)}"
    )
    return testo, nuova, riassunto


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
@app.get("/salute")
def salute():
    return {"ok": True, "prodotti": len(PRODOTTI)}


@app.post("/chat")
def chat(req: Richiesta):
    domanda = req.messaggio.strip()
    if not domanda:
        raise HTTPException(status_code=400, detail="Scrivi un messaggio.")
    if len(domanda) > MAX_CARATTERI_MESSAGGIO:
        raise HTTPException(
            status_code=400,
            detail=f"Il messaggio è troppo lungo: al massimo {MAX_CARATTERI_MESSAGGIO} caratteri.",
        )

    sid = req.session_id
    with LOCK_SESSIONI.setdefault(sid, threading.Lock()):
        if sid not in STORIE and len(STORIE) >= MAX_SESSIONI:
            vecchia = next(iter(STORIE))
            STORIE.pop(vecchia, None)
            RIASSUNTI.pop(vecchia, None)
            LOCK_SESSIONI.pop(vecchia, None)
        storia = STORIE.setdefault(sid, [])

        try:
            testo, nuova, riassunto = rispondi(storia, RIASSUNTI.get(sid, ""), domanda)
        except anthropic.APIError as e:
            print(f"[errore] chiamata al modello fallita: {e!r}")
            raise HTTPException(
                status_code=502,
                detail="L'assistente non è raggiungibile in questo momento.",
            )
        if not testo:
            return {"risposta": "Non sono riuscito a rispondere, riprova."}

        STORIE[sid] = nuova
        if riassunto:
            RIASSUNTI[sid] = riassunto
        return {"risposta": testo}
