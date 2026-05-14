# Staging Testplan — Backend Calculation Step Migration

**Formål:** Verificere at backend dual-format migration virker korrekt på staging.
**Dato:** 2025-07-01
**Miljø:** Staging (https://api-staging.configo.ai eller tilsvarende)

---

## Forberedelse

1. Deploy backend `main` branch til staging
2. Kør ikke DB migration endnu (test dual-format først)
3. Sørg for at frontend er deployet med seneste kode (stadig med `fromLegacy` converters)
4. Log ind med en test-organisation

---

## Test 1: Constraint CRUD med eksisterende (flat-format) data

**Mål:** Verificere at backend læser flat-format data og returnerer det normaliseret (med `kind` felt).

### 1.1 Opret configurator med constraints
1. Gå til configurator builder
2. Tilføj et element (f.eks. number field)
3. Gå til Constraints tab
4. Opret en constraint med:
   - **Condition:** Field X equals 5
   - **Action:** Set value = 10 (med calculation steps)
5. Gem configurator

**Forventet:** Gemmer korrekt, ingen fejl.

### 1.2 Verificér API respons
1. Åbn browser network tab
2. Genindlæs configurator
3. Find `GET /v1/constraints` kald
4. Tjek response body:

```json
{
  "items": [{
    "conditions": [...],
    "actions": [{
      "type": "set_value",
      "action_calculation_steps": [{
        "kind": "calculation",  // <-- SKAL have kind felt
        "id": "step-1",
        "operation": "add",
        "left": { "kind": "number", "value": 10 },
        "right": { "kind": "field", "field_id": "field-1" }
      }]
    }]
  }]
}
```

**Forventet:** `action_calculation_steps` har `kind` felt (viser at backend normaliserede data).

### 1.3 Verificér frontend rendering
1. Constraints vises korrekt i UI
2. Calculation steps renderes korrekt i constraint builder
3. Ingen console errors

---

## Test 2: Constraint CRUD med nyt format (hvis frontend sender det)

**Mål:** Verificere at backend accepterer nyt format.

### 2.1 Test med frontend
Hvis frontend allerede sender nyt format (fjerner `fromLegacy` først):
1. Opret constraint med calculation steps
2. Tjek at det gemmer korrekt

**Forventet:** Gemmer korrekt, ingen fejl.

### 2.2 Test direkte API
1. Brug Postman/curl til at sende constraint med nyt format:

```bash
curl -X POST https://api-staging.configo.ai/v1/constraints \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "source_configurator_id": "test",
    "conditions": [],
    "actions": [{
      "type": "set_value",
      "action_calculation_steps": [{
        "kind": "calculation",
        "id": "step-1",
        "operation": "add",
        "left": { "kind": "number", "value": 10 },
        "right": { "kind": "field", "field_id": "field-1" }
      }]
    }]
  }'
```

**Forventet:** 201 Created. Response har `kind` felt.

---

## Test 3: Saved Calculations CRUD

**Mål:** Verificere at saved calculations normaliseres korrekt.

### 3.1 Opret saved calculation
1. Gå til Saved Calculations side
2. Opret ny saved calculation med calculation steps
3. Gem

**Forventet:** Gemmer korrekt.

### 3.2 Verificér API respons
1. Find `GET /v1/saved-calculations` kald
2. Tjek at `calculation_steps` har `kind` felt

```json
{
  "items": [{
    "name": "My Calc",
    "calculation_steps": [{
      "kind": "calculation",
      "id": "step-1",
      "operation": "multiply",
      "left": { "kind": "field", "field_id": "field-1" },
      "right": { "kind": "number", "value": 2 }
    }]
  }]
}
```

**Forventet:** `calculation_steps` har `kind` felt.

### 3.3 Opdater saved calculation
1. Rediger en eksisterende saved calculation
2. Gem ændringer

**Forventet:** Opdaterer korrekt.

---

## Test 4: Calculation Builder (Frontend)

**Mål:** Verificere at frontend calculation builder virker med normaliseret data.

### 4.1 Simpel calculation
1. Opret calculation step i builder
   - Left: Field = "field-1"
   - Operation: Add
   - Right: Number = 5
2. Gem

**Forventet:** Viser korrekt i builder efter reload.

### 4.2 Conditional calculation
1. Opret conditional step:
   - Condition: Field X > 10
   - Then: Multiply by 2
   - Else: Add 1
2. Gem

**Forventet:** Conditional rendering virker korrekt.

### 4.3 Saved calculation reference
1. Opret step der refererer til saved calculation
2. Map placeholders
3. Gem

**Forventet:** Saved calc reference virker korrekt.

---

## Test 5: Configurator Import

**Mål:** Verificere at import-configurator edge function genererer nyt format.

### 5.1 Import configurator
1. Gå til Import Configurator
2. Upload Excel/CSV fil med calculation steps
3. Kør import

### 5.2 Verificér genereret data
1. Gå til den importerede configurator
2. Tjek constraints/saved calculations
3. Verificér at calculation steps har `kind` felt

**Forventet:** Importeret data har `kind` felt på alle calculation steps.

---

## Test 6: Dual-format kompatibilitet (vigtigst)

**Mål:** Verificere at backend accepterer både gammelt og nyt format.

### 6.1 Send gammelt format direkte
1. Brug Postman til at sende constraint med FLAT format:

```bash
curl -X POST https://api-staging.configo.ai/v1/constraints \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "source_configurator_id": "test",
    "conditions": [],
    "actions": [{
      "type": "set_value",
      "action_calculation_steps": [{
        "id": "step-1",
        "operation": "add",
        "left_type": "number",
        "left_number_value": 10,
        "right_type": "field",
        "right_field_id": "field-1"
      }]
    }]
  }'
```

2. Tjek response:

**Forventet:** 201 Created. Response har `kind` felt (viser at backend konverterede fra flat).

### 6.2 Send blandet format
1. Send request hvor nogle steps er nyt format og andre er gammelt:

```json
{
  "action_calculation_steps": [
    { "kind": "calculation", "id": "new", "operation": "add", "left": {"kind":"number","value":1} },
    { "id": "old", "operation": "multiply", "left_type": "field", "left_field_id": "field-1" }
  ]
}
```

**Forventet:** 201 Created. Begge steps har `kind` felt i response.

---

## Test 7: Eksisterende data (før DB migration)

**Mål:** Verificere at eksisterende flat-format data i DB stadig virker.

### 7.1 Gamle constraints
1. Find en configurator med eksisterende constraints (oprettet før migration)
2. Åbn configurator builder
3. Gå til constraints tab

**Forventet:** Constraints vises korrekt. Calculation steps renderes korrekt (backend normaliserer ved læsning).

### 7.2 Gamle saved calculations
1. Gå til Saved Calculations
2. Åbn en eksisterende saved calculation

**Forventet:** Viser korrekt. Calculation steps har `kind` felt i API respons.

---

## Test 8: Efter DB migration

**Mål:** Verificere at DB migration transformerer data korrekt.

**Kun kør dette efter backend er verificeret OK og du er klar til at migrere data.**

### 8.1 Kør migration
1. Kør SQL migration på staging:
   ```bash
   psql $DATABASE_URL -f supabase/migrations/20250701120000_migrate_calculation_steps.sql
   ```

### 8.2 Verificér migreret data
1. Tjek `saved_calculations` tabel:
   ```sql
   SELECT calculation_steps FROM saved_calculations LIMIT 1;
   ```
   
   **Forventet:** `calculation_steps` har `kind` felt på alle steps.

2. Tjek `constraints` tabel:
   ```sql
   SELECT actions FROM constraints LIMIT 1;
   ```
   
   **Forventet:** Actions har `kind` felt på calculation steps.

### 8.3 Idempotens test
1. Kør migration igen

**Forventet:** Ingen ændringer (idempotent).

### 8.4 Frontend test efter migration
1. Gentag Test 7.1 og 7.2

**Forventet:** Stadig virker korrekt.

---

## Test 9: Edge Cases

### 9.1 Tomme arrays
1. Opret constraint med tomme `action_calculation_steps`: `[]`

**Forventet:** 201 Created. Tom array bevares.

### 9.2 Invalid data
1. Send request med invalid calculation step:
   ```json
   {"action_calculation_steps": [{"invalid": true}]}
   ```

**Forventet:** 400 Bad Request eller graceful handling.

### 9.3 Dyb nesting
1. Opret conditional med nested conditionals (3+ niveauer)

**Forventet:** Normalisering virker rekursivt. Response korrekt.

---

## Test 10: Performance

### 10.1 Stor configurator
1. Åbn configurator med 50+ constraints
2. Tjek load tid

**Forventet:** Ingen mærkbar forsinkelse (normalisering er O(n)).

---

## Godkendelseskriterier

✅ = Pass, ❌ = Fail, ⏳ = Blocked

| Test | Status | Kommentar |
|------|--------|-----------|
| 1.1 Opret constraint | | |
| 1.2 API respons har kind | | |
| 1.3 Frontend rendering | | |
| 2.1 API med nyt format | | |
| 3.1 Saved calc CRUD | | |
| 3.2 API respons | | |
| 4.1 Simpel calculation | | |
| 4.2 Conditional | | |
| 4.3 Saved calc ref | | |
| 5.1 Import | | |
| 6.1 Dual-format (gammelt) | | |
| 6.2 Blandet format | | |
| 7.1 Gamle constraints | | |
| 7.2 Gamle saved calcs | | |
| 8.2 Migreret data | | |
| 8.3 Idempotens | | |
| 9.1 Tomme arrays | | |
| 9.2 Invalid data | | |
| 9.3 Dyb nesting | | |
| 10.1 Performance | | |

---

## Hvis noget fejler

1. **Backend fejl:** Tjek logs på staging
2. **Frontend fejl:** Tjek browser console
3. **API fejl:** Brug Postman til at reproducere
4. **Rapportér:** Opret issue med:
   - Test nummer
   - Forventet vs faktisk
   - API request/response
   - Screenshot

## Sign-off

**Tester:** _______________  **Dato:** _______________

**Resultat:** ☐ Alle tests passer  ☐ Nogle fejl (se kommentarer)

**Kommentarer:**

_______________________________________________
_______________________________________________