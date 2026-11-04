import json
from datetime import date

import anthropic

MODELLI = [
    "claude-haiku-5-5",
    "claude-sonnet-5-5",
]

# $ per milione di token (da prezzi_modelli.md)
PREZZI = {
    "claude-haiku-5-5": {"input": 1, "output": 5},
    "claude-sonnet-5-5": {"input": 3, "output": 15},
}

PROVE = 2


def leggi_file(percorso):
    with open(percorso, encoding="utf-8") as f:
        return f.read()


def costruisci_system_prompt():
    template = leggi_file("system_prompt_template.txt")
    listino = json.dumps(
        json.loads(leggi_file("listino.json")), ensure_ascii=False, indent=2
    )
    oggi = date.today().strftime("%d/%m/%Y")
    return template.replace("{LISTINO_JSON}", listino).replace("{DATA_ODIERNA}", oggi)


def costo_stimato(modello, input_tokens, output_tokens):
    p = PREZZI[modello]
    return input_tokens / 1e6 * p["input"] + output_tokens / 1e6 * p["output"]


def main():
    client = anthropic.Anthropic()  # legge ANTHROPIC_API_KEY dall'ambiente
    system_prompt = costruisci_system_prompt()
    domande = [r.strip() for r in leggi_file("domande.txt").splitlines() if r.strip()]

    for modello in MODELLI:
        for domanda in domande:
            for prova in range(1, PROVE + 1):
                r = client.messages.create(
                    model=modello,
                    max_tokens=500,
                    system=system_prompt,
                    messages=[{"role": "user", "content": domanda}],
                )
                testo = "".join(b.text for b in r.content if b.type == "text")
                costo = costo_stimato(
                    modello, r.usage.input_tokens, r.usage.output_tokens
                )
                print("=" * 60)
                print(f"Modello: {modello} | prova {prova}")
                print(f"Domanda: {domanda}")
                print(f"Risposta: {testo}")
                print(
                    f"Token input: {r.usage.input_tokens} | "
                    f"output: {r.usage.output_tokens} | "
                    f"costo stimato: ${costo:.6f}"
                )


if __name__ == "__main__":
    main()