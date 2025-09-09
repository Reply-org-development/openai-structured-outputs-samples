# Conversational Assistant — Guida Estesa Tecnica e Funzionale

Questa guida spiega, senza leggere il codice, come l’assistente conversa con l’utente, quando chiama i modelli OpenAI, come usa i “tool” (funzioni) e come genera l’interfaccia (UI) in modo dinamico.

## Cosa fa l’app (in parole semplici)

- Chatta con l’utente su ordini, resi e prodotti del negozio (dati demo).
- Quando serve, “chiama strumenti” (tool) per cercare dati o eseguire azioni (es. creare un reso).
- Sa generare UI su misura (caroselli, tabelle, grafici) a partire da JSON strutturato.

## Come è fatta (componenti principali)

- Motore agentico (server): riceve i messaggi e chiama OpenAI in streaming.
- Orchestrazione (client): aggiorna in tempo reale la chat, capisce quando eseguire un tool e rilancia il dialogo.
- Tool: funzioni “esterne” che l’assistente può invocare (prodotti, ordini, resi, carrello).
- UI generativa: un tool speciale che restituisce componenti da visualizzare (niente codice da scrivere per i layout comuni).

## Flusso end‑to‑end (passo per passo)

1. L’utente scrive un messaggio nella chat e lo invia.
2. Il browser manda tutto al server dell’app, insieme a un “promemoria” per l’assistente (system prompt) e allo storico.
3. Il server chiama OpenAI (modello predefinito `gpt-4o`) chiedendo una risposta con possibili tool e riceve uno stream di eventi.
4. Durante lo stream possono arrivare:
   - Testo dell’assistente (quando “parla”).
   - Istruzioni per chiamare un tool, con gli argomenti in JSON, inviati a pezzetti.
5. Quando gli argomenti del tool sono completi, il client esegue il tool lato app (es. legge un elenco prodotti dalle API locali) e rimanda il risultato come se fosse un messaggio del “ruolo: tool”.
6. L’assistente riprende la conversazione, ora arricchita con l’output del tool; se serve, propone o genera UI per mostrare meglio i dati.

Schema (semplificato)

Utente → Browser → Server `/api/turn_response` → OpenAI (stream)
↘ tool args (stream) → Browser esegue tool → API locali (prodotti/ordini)
↘ risultato tool → Server → OpenAI → nuova risposta/altro tool → Browser (UI aggiornata)

### Infografica ASCII (dettagliata)

```
┌───────────────┐         ┌────────────────────┐          ┌───────────────┐
│     Utente    │  (1)    │   Browser (Chat)   │   (2)    │    Server     │
└──────┬────────┘  input  └─────────┬──────────┘  POST    └──────┬────────┘
       │                              /api/turn_response          │
       │                                                     (3)  │ openai.chat.stream
       │                                                          v
       │                                                    ┌───────────────┐
       │                                                    │    OpenAI     │
       │                                                    └──────┬────────┘
       │   (7) UI aggiornata (text + UI)                           │ STREAM
       v                                                           │  ├ assistant_delta (testo)
┌───────────────┐    (6) tool result  ┌────────────────────┐       │  ├ function_arguments_delta
│     UI        │◄────────────────────│   Browser (Chat)   │◄──────┘  └ function_arguments_done
└──────┬────────┘                     └─────────┬──────────┘
       │ (5) handleTool(name, args)             │ (4) accumulo argomenti (partial JSON)
       │        ├ generate_ui → render          │
       │        └ business tool → /api/tools/*  │
       │                                        │
       └────────────────────────────────────────┘ (8) loop con nuovo contesto
```

## Modello e prompting

- Modello: `gpt-4o` (modificabile), temperatura 0 per risposte più deterministiche.
- Prompt di sistema: spiega “cosa deve fare” (come gestire ordini/resi, quando usare la UI generativa).
- Messaggio iniziale: un saluto che spiega all’utente cosa può chiedere.

## I Tool (cosa sono e quando si usano)

Strumenti disponibili (semplificati):

- get_products: elenca i prodotti disponibili.
- get_product_details(productId): dettaglio di un prodotto.
- get_orders: elenca gli ordini dell’utente (demo).
- file_claim(orderId, reason, description): registra una segnalazione su un ordine.
- create_return(orderId, return_items[]): crea un reso.
- add_to_cart(items[]): aggiunge articoli al carrello (demo).
- generate_ui(component): genera un layout UI a partire da un JSON strutturato.

Cosa succede realmente:

- L’assistente decide di usare un tool e invia “il nome del tool” e “gli argomenti” in JSON (in streaming).
- L’app esegue quel tool: per i dati usa API locali demo; per azioni mostra conferme.
- Il risultato rientra nella conversazione e l’assistente lo usa per proseguire.

Esempio d’uso tipico

- Utente: “Vorrei restituire il mio ordine”.
- Assistente: chiama `get_orders` → mostra un carosello con gli ordini → chiede quale ordine.
- Utente: seleziona ordine e descrive il problema.
- Assistente: chiama `file_claim` e `create_return` → conferma la creazione del reso.

## UI Generativa (come funziona e cosa si vede)

- Il tool `generate_ui` restituisce un JSON del tipo:
  {
  "component": {
  "name": "card",
  "children": [
  { "name": "header", "content": "Dettaglio ordine #1001" },
  {
  "name": "table",
  "columns": [
  { "key": "name", "title": "Prodotto" },
  { "key": "qty", "title": "Qtà" }
  ],
  "rows": [
  { "name": "Quantum Processor", "qty": 1 }
  ]
  }
  ]
  }
  }
- L’app traduce questo JSON in componenti React predefiniti (card, header, carousel, table, bar_chart, ecc.) e li mostra in chat.
- Vantaggio: si vede subito il risultato in modo leggibile (grafico/tabella) senza scrivere codice aggiuntivo.

Suggerimenti pratici

- Liste di elementi → `carousel` o `table`.
- Confronto di numeri (pesi, prezzi, dimensioni) → `bar_chart` dentro una `card` con `header`.

## Dati e API locali (demo)

- L’app non interroga sistemi reali: espone API finte che restituiscono dati di esempio.
- Endpoints principali:
  - `/api/tools/get_products` → elenco prodotti.
  - `/api/tools/get_orders` → elenco ordini.
  - `/api/tools/get_product_details?productId=...` → dettaglio di un prodotto.

## Cambiare comportamento senza scrivere codice complesso

- Cambiare modello o messaggio iniziale: modificare il valore del modello e il testo del prompt di sistema. Effetto: l’assistente “ragiona” in modo più creativo o più prudente a seconda del modello; il saluto iniziale cambia.
- Aggiungere un nuovo tool (alto livello):
  1. Definisci il nome e i parametri che accetta (es. `track_delivery(orderId)`).
  2. Implementa la “logica” che deve svolgere (anche mock/placeholder).
  3. (Opzionale) Aggiungi un piccolo componente di visualizzazione se vuoi un risultato più gradevole in chat.
- Personalizzare la UI generativa: aggiungi nuovi tipi di componenti (es. “badge”, “grid”) e decidi come renderizzarli; il modello potrà usarli da subito nei layout.

### Aggiungere un nuovo tool (guida passo‑passo senza codice)

1. Definisci lo scopo: cosa deve fare? (es. “traccia spedizione”).
2. Scegli un nome chiaro (es. `track_delivery`) e i parametri minimi (es. `orderId`).
3. Descrizione: spiega al modello quando usarlo e perché (evita ambiguità).
4. Parametri: elenca nome, tipo e descrizione di ciascun parametro (obbligatori dove serve).
5. Esecuzione: prevedi cosa deve restituire (JSON semplice e coerente con la UI).
6. Visualizzazione: se vuoi un rendering dedicato in chat, aggiungi un piccolo componente di output o usa il fallback JSON.
7. Test manuale: chiedi all’assistente “traccia ordine #…”, verifica che proponga il tool e mostri il risultato atteso.

Esempi di risultati utili (best practice)

- Risposta minimale: `{ status: "in_transit", etaDays: 2 }`
- Con UI: fornisci campi pronti per tabella o card (titolo + righe/colonne).

## Sicurezza, privacy e affidabilità

- API Key: salva `OPENAI_API_KEY` in un file `.env` dell’app (non condividerlo mai).
- Niente segreti nei log: i log servono al debug, non devono contenere dati sensibili.
- Determinismo: la temperatura bassa e i “tool in serie” rendono il flusso più prevedibile.
- Validazione: gli argomenti dei tool sono strutturati e verificati; la UI generativa usa una lista chiusa di componenti per proteggere il rendering.

### Dettagli streaming ed errori (cosa aspettarsi)

- Stream testuale: l’assistente può produrre testo anche mentre sta per decidere un tool; è normale vedere aggiornamenti progressivi.
- Argomenti tool “a pezzi”: arrivano in chunk; il client li unisce (tollerante a JSON parziali) prima di eseguire.
- Errori temporanei tool/API: mostra un messaggio chiaro e non bloccare la chat; il flusso può riprendere con un nuovo turno.
- Timeout/Limiti: mantieni risposte brevi quando non necessaria la UI; preferisci ottenere dati essenziali e solo poi generare layout.

### Performance e latenza

- `temperature: 0` riduce riformulazioni e tempi inutili.
- `parallel_tool_calls: false` evita conflitti e rende l’ordine delle azioni prevedibile.
- Dati locali (demo) rispondono immediatamente: con API reali valuta caching e paginazione.

### Checklist di qualità (prima di rilasciare)

- [ ] Prompt di sistema chiaro: spiega “quando” usare i tool e la UI.
- [ ] Tool con parametri minimi, descritti bene e con tipi coerenti.
- [ ] Risposte tool piccole e utili (niente payload ridondanti).
- [ ] UI generativa solo quando porta valore (liste, confronti, grafici).
- [ ] Messaggi d’errore pensati per l’utente finale.

## Esecuzione locale (rapida)

1. Requisiti: Node 18+, npm; variabile `OPENAI_API_KEY` impostata (file `.env`).
2. Installazione: dentro la cartella dell’app esegui `npm i`.
3. Avvio: `npm run dev` → apri il browser su `http://localhost:3000`.

## Risoluzione problemi (comuni)

- Errore 401/chiave mancante: verifica `OPENAI_API_KEY` nel `.env` dell’app.
- L’assistente “si ferma”: controlla la console del browser per eventuali errori di parsing (lo stream arriva a pezzi, è normale vedere JSON “parziali” durante il flusso).
- Un tool “non parte”: assicurati che il suo nome esista fra quelli disponibili e che gli argomenti richiesti siano presenti.
- UI non appare: quando `generate_ui` fornisce componenti sconosciuti, il sistema li ignora; assicurati che il componente esista tra quelli supportati.

## Glossario essenziale

- Tool (Strumento): una funzione esterna che l’assistente può invocare con parametri (es. “dammi i prodotti”).
- Chiamata Tool: la richiesta dal modello a eseguire un tool con determinati argomenti.
- Streaming: la risposta arriva a piccoli pezzi per mostrare aggiornamenti in tempo reale.
- UI generativa: layout creato dal modello ma vincolato a componenti predefiniti, così è sicuro e consistente.

## Domande frequenti

- Posso cambiare modello? Sì, scegli un modello più economico/veloce o più capace. Impatto su qualità/latency.
- Posso eseguire più tool in parallelo? Di default no (serie). È possibile, ma sconsigliato per semplicità e controllo.
- Posso collegare API reali? Sì: sostituisci le API demo con le tue (autenticazione, errori, ecc.).

—
Questa guida vuole rendere trasparenti i passaggi principali di un agente: messaggi → decisioni → chiamate tool → UI. Con questi concetti puoi capire, usare e personalizzare l’assistente senza leggere il codice.
