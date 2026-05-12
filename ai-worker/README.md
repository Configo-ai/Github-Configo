# Configo AI Worker

## Overview

`Configo-AI-Worker` er et separat Python-baseret service-repo til AI-orchestration for Configo.

Det er designet til at kunne bruges af flere klienter, herunder:
- `Configo-Frontend`
- `Configo-Developer-Frontend`

Det er ikke en erstatning for backend eller frontend. Det er et specialiseret lag til agent-workflows, retrieval og draft-baseret AI-assistance.

## Ansvar

AI workerens ansvar er:
- chat-orchestration for AI-assistent flows
- draft sessions for configurator-redigering
- plan mode vs build mode
- preview-targeted instruktioner
- product attachment og product search context
- configurator matching fra naturligt sprog
- guided filling flows, hvor AI stiller manglende spørgsmål og udfylder en configurator gradvist
- retrieval over store configurator-strukturer uden at sende hele JSON'en i hver prompt

## Ikke-ansvar

AI workerens ansvar er ikke:
- at være source of truth for configurator-data
- at eje pricing, permissions eller valideringsregler
- at mutere persisted state uden eksplicit apply-flow
- at erstatte backendens domænelogik

Hvis logik påvirker correctness, permissions, pricing eller tenant isolation, skal den stadig bo i backend.

## Arkitekturretning

Workeren bruger:
- HTTP som eksternt interface mod frontends
- et internt tool-runtime lag til agent-operationer
- draft state som arbejdskopi
- preview state som visualiseringslag
- AST/graph parsing som strukturel sandhed
- retrieval som kontekstlag ovenpå AST'en
- en dedikeret retrieval-engine som `Qdrant` til hybrid dense+sparse search

Det betyder i praksis:
- frontends sender ikke hele configuratoren i prompten
- agenten henter kun relevant hot/warm context
- mutationer sker via strukturerede tools fremfor fritekst-patching af rå JSON
- business data kan fortsat bo i Supabase/Postgres, mens retrieval-indekser holdes separat

## Frontend-forbrug

### Configo Frontend

`Configo-Frontend` får en feature-flagged `AI Assistant` tab i configurator-workspace.

V1-retning:
- chat til venstre
- preview til højre
- click-to-target i preview
- staged actions
- apply/discard
- eksplicit bekræftelse af delete-handlinger

Frontend skal følge den eksisterende struktur i `Configo-Frontend` og udvide den nuværende configurator-oplevelse, ikke opfinde en parallel mini-app.

### Configo Developer Frontend

`Configo-Developer-Frontend` skal senere kunne bruge de samme worker-endpoints og tools, men UI og integration kan være anderledes. Den repo ejer ikke worker-logikken.

## Assisted Filling

En vigtig fremtidig retning er AI-assisteret udfyldning:

1. Brugeren beskriver behov i naturligt sprog.
2. Worker matcher den relevante configurator.
3. Worker finder manglende inputs.
4. AI stiller de nødvendige opfølgende spørgsmål.
5. Svar anvendes på configuratoren gradvist.
6. Resultatet valideres og opsummeres.

Eksempel:

> "Jeg skal bruge en lejder på siden af min bygning der 5 meter op og det er på en skole"

Her skal worker:
- finde den rigtige configurator
- udlede kendt kontekst
- spørge efter manglende oplysninger
- udfylde relevante felter uden at sende hele konfiguratoren i prompten

## Retrieval-retning

Undgå klassisk "embed hele JSON'en og søg i den" som primær model.

Foretrukken retning:
- parse configurator til AST/graph
- chunk strukturelt pr. page/section/element/constraint
- indeksér både dense og sparse retrieval-repræsentationer med strukturel metadata
- retrieve kun relevante noder, naboer og regler

Kort sagt:
- `AST/graph` er sandheden
- `Qdrant` kan være retrieval-motoren
- `retrieval` reducerer kontekst-bloat
- `tools` udfører mutationer sikkert
