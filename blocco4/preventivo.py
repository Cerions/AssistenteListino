"""Calcolo del preventivo Legno & Co. Prezzi letti da listino.json (mai nel codice)."""
import json, pathlib
LISTINO = json.loads((pathlib.Path(__file__).parent / "listino.json").read_text(encoding="utf-8"))

class MisuraNonValida(ValueError):
    pass

def calcola_preventivo(larghezza, altezza, profondita, legno, finitura, consegna):
    p = LISTINO["parametri"]
    for nome, v in (("La larghezza", larghezza), ("L'altezza", altezza), ("La profondità", profondita)):
        if not isinstance(v, (int, float)) or isinstance(v, bool) or v <= 0:
            raise MisuraNonValida(f"{nome} deve essere un numero maggiore di zero.")
        if not p["misura_min_cm"] <= v <= p["misura_max_cm"]:
            raise MisuraNonValida(f"{nome} deve essere tra {p['misura_min_cm']} e {p['misura_max_cm']} cm.")
    for chiave, valore, nome in (("legni", legno, "Legno non valido"), ("finiture", finitura, "Finitura non valida"), ("consegne", consegna, "Consegna non valida")):
        if valore not in LISTINO[chiave]:
            raise MisuraNonValida(f"{nome}: {valore}.")
    mq = 2 * (larghezza * altezza + larghezza * profondita + altezza * profondita) / 10000
    mobile = mq * (LISTINO["legni"][legno] + LISTINO["finiture"][finitura])
    imponibile = round(mobile + LISTINO["consegne"][consegna], 2)
    iva = round(imponibile * p["iva"], 2)
    return {"superficie_mq": round(mq, 4), "imponibile": imponibile, "iva": iva, "totale": round(imponibile + iva, 2)}

def euro(x):
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " €"
