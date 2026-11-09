"""Passo 1: i 12 casi di casi_di_prova.json su calcola_preventivo, confrontati con "atteso"."""
import json
from pathlib import Path

from preventivo import MisuraNonValida, calcola_preventivo

dati = json.loads((Path(__file__).parent / "casi_di_prova.json").read_text(encoding="utf-8"))
campi = ("larghezza", "altezza", "profondita", "legno", "finitura", "consegna")
ok = 0
for caso in dati["casi"]:
    atteso = dati["atteso"][caso["id"]]
    try:
        ottenuto = calcola_preventivo(**{c: caso[c] for c in campi})
    except MisuraNonValida as e:
        ottenuto = {"errore": str(e)}
    uguale = ottenuto == atteso
    ok += uguale
    print(f"{caso['id']:>3} {caso['cliente']:<9} {'OK ' if uguale else 'NO '} {ottenuto}"
          + ("" if uguale else f"   atteso: {atteso}"))
print(f"\n{ok}/{len(dati['casi'])} casi coincidono con l'atteso")
