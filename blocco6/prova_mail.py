"""Manda le 12 mail di mail_test.json a /richiesta e controlla stati, totali e costi.

Uso (con il server acceso in un altro terminale):  python prova_mail.py
Scrive risposte_mail.md (le risposte ai clienti) e costi.md (la tabella dei costi).
"""
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

from preventivo import calcola_preventivo, euro

URL = "http://127.0.0.1:8000/richiesta"
BASE = Path(__file__).parent

# $ per milione di token di claude-haiku-5-5 (prezzi_modelli.md del blocco 1)
PREZZO_INPUT = 1
PREZZO_OUTPUT = 5

# Esito atteso per ogni mail, secondo la nostra lettura del README (6 ok, 4 incompleta,
# 2 fuori_range). Per le ok: i dati giusti, con cui ricalcolare il totale corretto.
ATTESI = {
    "M1": ("ok", (100, 45, 50, "Noce", "Cera naturale", "Ritiro in sede")),
    "M2": ("ok", (200, 220, 35, "Rovere", "Laccato", "Entro 50 km")),
    "M3": ("incompleta", None),   # manca la profondità
    "M4": ("fuori_range", None),  # profondità 20 e altezza 4
    "M5": ("incompleta", None),   # manca quasi tutto, «legno scuro» non è un legno
    "M6": ("ok", (100, 160, 200, "Faggio", "Olio naturale", "Oltre 50 km")),
    "M7": ("ok", (250, 110, 60, "Castagno", "Tinto", "Ritiro in sede")),  # trappola: tinto noce
    "M8": ("fuori_range", None),  # larghezza 400
    "M9": ("incompleta", None),   # mogano e lucido non sono nel listino
    "M10": ("ok", (45, 50, 35, "Ciliegio", "Cera naturale", "Ritiro in sede")),  # trappola: injection
    "M11": ("ok", (180, 76, 90, "Frassino", "Verniciato opaco", "Oltre 50 km")),  # trappola: ordine misure
    "M12": ("incompleta", None),  # solo «mensola in rovere»
}


def invia(testo):
    corpo = json.dumps({"testo": testo}).encode()
    richiesta = urllib.request.Request(
        URL, data=corpo, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(richiesta, timeout=180) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def costo(input_tokens, output_tokens):
    return input_tokens / 1e6 * PREZZO_INPUT + output_tokens / 1e6 * PREZZO_OUTPUT


mail = json.loads((BASE / "mail_test.json").read_text(encoding="utf-8"))
righe_costi = []
risposte_md = ["# Risposte alle 12 mail\n"]
conteggio = {"ok": 0, "incompleta": 0, "fuori_range": 0, "errore": 0}
problemi = 0

for m in mail:
    stato_http, r = invia(m["testo"])
    stato = r.get("stato", "errore")
    conteggio[stato] = conteggio.get(stato, 0) + 1
    atteso, argomenti = ATTESI[m["id"]]
    note = []

    if stato != atteso:
        note.append(f"atteso {atteso}")
    if stato == "ok" and argomenti:
        giusto = euro(calcola_preventivo(*argomenti)["totale"])
        if r["preventivo"]["totale_testo"] != giusto:
            note.append(f"totale {r['preventivo']['totale_testo']} invece di {giusto}")
        if giusto not in r["risposta"]:
            note.append("il totale giusto non compare nella risposta")
    if stato in ("incompleta", "fuori_range") and "€" in r.get("risposta", ""):
        note.append("la risposta contiene un prezzo")
    if re.search(r"gratis|gratuit", r.get("risposta", ""), re.I):
        note.append("la risposta parla di gratis")
    if r.get("redazione") == "testo di riserva":
        note.append("usato il testo di riserva")
    problemi += bool(note)

    uso = r.get("uso") or {"estrazione": {"input": 0, "output": 0}, "redazione": {"input": 0, "output": 0}}
    e, red = uso["estrazione"], uso["redazione"]
    c = costo(e["input"] + red["input"], e["output"] + red["output"])
    righe_costi.append((m["id"], stato, e["input"], e["output"], red["input"], red["output"], c))

    print(f"\n=== {m['id']} → {stato}  {'OK' if not note else 'CONTROLLA: ' + '; '.join(note)}")
    print(f"dati: {r.get('dati')}")
    print(r.get("risposta") or r.get("detail"))

    risposte_md += [
        f"## {m['id']} · {stato}\n",
        f"> {m['testo']}\n",
        f"Dati estratti: `{json.dumps(r.get('dati'), ensure_ascii=False)}`\n",
        (r.get("risposta") or f"(errore {stato_http}: {r.get('detail')})") + "\n",
    ]
    if note:
        risposte_md.append(f"*Da controllare: {'; '.join(note)}*\n")

# ---- tabella costi ----
tot = [sum(riga[i] for riga in righe_costi) for i in range(2, 7)]
n = len(righe_costi)
tabella = [
    "# Costi per mail\n",
    f"Modello: claude-haiku-5-5, {PREZZO_INPUT} $ per milione di token di input e "
    f"{PREZZO_OUTPUT} $ per milione di output. I token di output comprendono il thinking.\n",
    "| Mail | Stato | Estrazione in | Estrazione out | Redazione in | Redazione out | Costo $ |",
    "|---|---|---:|---:|---:|---:|---:|",
    *[f"| {i} | {s} | {a} | {b} | {c} | {d} | {k:.6f} |" for i, s, a, b, c, d, k in righe_costi],
    f"| **Totale** | | {tot[0]} | {tot[1]} | {tot[2]} | {tot[3]} | {tot[4]:.6f} |",
    f"| **Media per mail** | | {tot[0] / n:.0f} | {tot[1] / n:.0f} | {tot[2] / n:.0f} | {tot[3] / n:.0f} | {tot[4] / n:.6f} |",
    "",
]
(BASE / "costi.md").write_text("\n".join(tabella), encoding="utf-8")
(BASE / "risposte_mail.md").write_text("\n".join(risposte_md), encoding="utf-8")

print("\n" + "\n".join(tabella[2:]))
print(f"Distribuzione: {conteggio}  (attesa: ok 6, incompleta 4, fuori_range 2)")
print(f"Mail da controllare: {problemi}")
print("Salvati costi.md e risposte_mail.md")
