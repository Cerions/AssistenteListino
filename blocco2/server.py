import json
from datetime import date
from pathlib import Path

from anthropic import Anthropic
from fastapi import FastAPI
from pydantic import BaseModel

BASE = Path(__file__).parent

app = FastAPI()
client = Anthropic()  # legge ANTHROPIC_API_KEY dall'ambiente
MODEL = "claude-haiku-5-5"

MAX_MESSAGGI = 12   # oltre questa soglia si riassumono i messaggi più vecchi
TIENI_ULTIMI = 6    # messaggi tenuti interi dopo il riassunto
MAX_TOKENS = 2000   # il thinking conta come output: non scendere troppo


def carica_system():
    """Template del blocco 1 riempito con il listino.json di questa cartella."""
    candidati = [
        BASE / "system_prompt_template.txt",
        BASE.parent / "blocco1" / "system_prompt_template.txt",
    ]
    for percorso in candidati:
        if percorso.exists():
            template = percorso.read_text(encoding="utf-8")
            break
    else:
        raise FileNotFoundError(
            "system_prompt_template.txt non trovato: copialo in questa cartella."
        )
    listino = json.loads((BASE / "listino.json").read_text(encoding="utf-8"))
    listino_testo = json.dumps(listino, ensure_ascii=False, indent=2)
    oggi = date.today().strftime("%d/%m/%Y")
    return template.replace("{LISTINO_JSON}", listino_testo).replace(
        "{DATA_ODIERNA}", oggi
    )


SYSTEM = carica_system()

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


class Richiesta(BaseModel):
    session_id: str
    messaggio: str


def estrai_testo(r):
    # il thinking arriva in blocchi separati: si prende solo il testo
    return "".join(b.text for b in r.content if b.type == "text")


def system_con_riassunto(session_id):
    riassunto = RIASSUNTI.get(session_id)
    if not riassunto:
        return SYSTEM
    return (
        SYSTEM
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


@app.post("/chat")
def chat(req: Richiesta):
    # TODO 1: storia di questa sessione (creata vuota se non esiste)
    storia = STORIE.setdefault(req.session_id, [])

    # TODO 2: messaggio dell'utente
    storia.append({"role": "user", "content": req.messaggio})

    # TODO 3: se la storia è troppo lunga, riassumi i messaggi più vecchi
    if len(storia) > MAX_MESSAGGI:
        comprimi(req.session_id)
        storia = STORIE[req.session_id]

    # TODO 4: chiamata al modello, risposta in storia, token a terminale
    r = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_con_riassunto(req.session_id),
        messages=storia,
    )
    testo = estrai_testo(r)
    if not testo:
        # risposta vuota (es. limite di token raggiunto durante il thinking):
        # tolgo l'ultimo messaggio user per non rompere l'alternanza dei ruoli
        storia.pop()
        return {"risposta": "Non sono riuscito a rispondere, riprova."}

    storia.append({"role": "assistant", "content": testo})
    print(
        f"[chat] sessione {req.session_id[:8]} | input: {r.usage.input_tokens} | "
        f"output: {r.usage.output_tokens} | messaggi in storia: {len(storia)}"
    )
    return {"risposta": testo}