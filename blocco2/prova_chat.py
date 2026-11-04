"""Simula 15 turni di chat e poi una seconda sessione. Avvia prima il server: uvicorn server:app --reload"""
import requests, uuid

URL = "http://127.0.0.1:8000/chat"

def chiedi(sid, testo):
    r = requests.post(URL, json={"session_id": sid, "messaggio": testo}, timeout=60)
    r.raise_for_status()
    return r.json()["risposta"]

turni = [
    "Ciao, mi chiamo Giulia e cerco una libreria.",          # 1  dati da ricordare
    "Larghezza 120 cm, altezza 180, profondità 30.",          # 2
    "La vorrei in rovere.",                                   # 3
    "Parliamo d'altro: che finiture avete?",                  # 4  si cambia argomento
    "Che differenza c'è tra olio naturale e cera?",           # 5
    "E il tinto cos'è?",                                      # 6
    "Il ciliegio costa più del noce?",                        # 7
    "Quale legno è più chiaro tra faggio e frassino?",        # 8
    "Fate consegne oltre 50 km?",                             # 9
    "Quanto costa la consegna entro 50 km?",                  # 10
    "Avete orari di apertura il sabato?",                     # 11 dato che NON c'è: non deve inventare
    "Ok, torniamo alla libreria.",                            # 12
    "Aspetta, come mi chiamo?",                               # 13 verifica memoria
    "E che legno avevo scelto?",                              # 14
    "E le misure?",                                           # 15
]
sid = str(uuid.uuid4())
for i, t in enumerate(turni, 1):
    print(f"[{i:2}] Tu: {t}\n     Bot: {chiedi(sid, t)}\n")

print("=== Sessione nuova (non deve sapere chi è Giulia) ===")
print("Bot:", chiedi(str(uuid.uuid4()), "Come mi chiamo?"))
