"""Manda al server le 13 domande di domande_docente.txt e salva le risposte.

Uso (con il server acceso in un altro terminale):  python prova_domande.py
Ogni domanda usa una sessione nuova, così le risposte non si influenzano a vicenda.
Le risposte finiscono anche in risposte_domande.md, da rileggere e valutare.
"""
import json
import urllib.error
import urllib.request
import uuid
from pathlib import Path

URL = "http://127.0.0.1:8000/chat"
BASE = Path(__file__).parent


def chiedi(testo, sid=None):
    corpo = json.dumps({"session_id": sid or str(uuid.uuid4()), "messaggio": testo}).encode()
    richiesta = urllib.request.Request(
        URL, data=corpo, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(richiesta, timeout=120) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


# Controlli automatici sui tre casi obbligatori del "Fatto quando".
# Sono solo un aiuto: le risposte vanno comunque lette.
def controllo(domanda, risposta):
    d, r = domanda.lower(), risposta.lower()
    if "atlantide" in d or "divani" in d:
        return "OK" if "non lo produciamo" in r else "CONTROLLA: manca «non lo produciamo»"
    if "castello" in d:
        ok = "noce" in r and "pino" in r and "faggio" in r
        return "OK" if ok else "CONTROLLA: deve escludere il noce e proporre pino o faggio"
    return ""


domande = [
    riga.strip()
    for riga in (BASE / "domande_docente.txt").read_text(encoding="utf-8").splitlines()
    if riga.strip()
]

righe_md = ["# Risposte alle domande del docente\n"]
for n, domanda in enumerate(domande, 1):
    stato, dati = chiedi(domanda)
    risposta = dati.get("risposta") or f"(errore {stato}: {dati.get('detail')})"
    esito = controllo(domanda, risposta)
    print(f"\n=== {n}. {domanda}")
    print(risposta)
    if esito:
        print(f"--> {esito}")
    righe_md += [f"## {n}. {domanda}\n", risposta + "\n"]
    if esito:
        righe_md.append(f"*Controllo automatico: {esito}*\n")

# Il limite dei 500 caratteri: il server deve rifiutare il messaggio con un errore 400.
stato, dati = chiedi("a" * 501)
esito = "OK" if stato == 400 else f"CONTROLLA: atteso 400, ricevuto {stato}"
print(f"\n=== Messaggio di 501 caratteri → {stato} {dati.get('detail')}  --> {esito}")
righe_md.append(f"## Messaggio di 501 caratteri\n\nRisposta {stato}: {dati.get('detail')} ({esito})\n")

(BASE / "risposte_domande.md").write_text("\n".join(righe_md), encoding="utf-8")
print("\nRisposte salvate in risposte_domande.md")
