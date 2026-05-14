# Backend Calculation Step Migration Plan

## Current State

### Frontend (completed)
- Discriminated union types are canonical: `CalculationStep`, `Operand`, `Condition`
- Legacy flat interface renamed to `CalculationStepLegacy`
- `fromLegacy()`/`toLegacy()` converters exist at API boundary (marked `@deprecated`)
- Frontend sends/receives flat format from backend, converts at boundary

### Backend (current)
- No typed Go structs for calculation steps — `any` passthrough
- `SavedCalculation.CalculationSteps` = `any` (jsonb)
- `Constraint.Conditions` / `Constraint.Actions` = `any` (jsonb)
- DB columns: `conditions jsonb`, `actions jsonb`, `calculation_steps jsonb`
- Import configurator function (`supabase/functions/import-configurator/tools.ts`) defines flat JSON Schema

### Existing JSON Schema (flat format)
```json
{
  "id": "string",
  "operation": "multiply|divide|add|subtract|...",
  "leftType": "number|field|previous_step|option_quantity",
  "leftNumberValue": 0,
  "leftFieldId": "string",
  "leftStepId": "string",
  "leftOptionId": "string",
  "rightType": "string",
  "rightNumberValue": 0,
  ...
}
```

## Target State

### JSON wire format (new discriminated union)
```json
{
  "kind": "calculation",
  "id": "string",
  "operation": "multiply|divide|add|subtract|...",
  "left": { "kind": "number", "value": 0 },
  "right": { "kind": "field", "fieldId": "string" },
  "valuesList": [{ "kind": "field", "fieldId": "string" }]
}
```

```json
{
  "kind": "conditional",
  "id": "string",
  "condition": {
    "operator": "equals|greater_than|less_than|greater_or_equal|less_or_equal",
    "left": { "kind": "field", "fieldId": "string" },
    "right": { "kind": "number", "value": 0 }
  },
  "thenSteps": [...],
  "elseSteps": [...]
}
```

```json
{
  "kind": "variable_definition",
  "id": "string",
  "variableName": "string",
  "valueSteps": [...]
}
```

```json
{
  "kind": "saved_calculation",
  "id": "string",
  "savedCalculationId": "string",
  "mappings": [{ "placeholderId": "string", "source": "field|direct|variable", "value": "string" }]
}
```

## Migration Strategy: Dual-Format Compatibility

### Approach: Backward-compatible read, write new format

The backend currently passes JSON through untyped. The migration adds typed Go structs with custom JSON marshaling that can **read both formats** and **write only the new format**.

This means:
- Old clients sending flat format → backend reads it fine
- New clients sending discriminated union → backend reads it fine
- All responses use new format
- Once all clients migrate, remove flat-format read support

## Step-by-step Plan

### 1. Add Go Calculation Step Types

**File**: `internal/domain/calculations/types.go`

```go
// Operand is a discriminated union for calculation step operands.
type Operand struct {
    Kind           string  `json:"kind"`
    Value          float64 `json:"value,omitempty"`          // kind=number
    FieldID        string  `json:"fieldId,omitempty"`         // kind=field
    StepID         string  `json:"stepId,omitempty"`          // kind=previous_step
    OptionID       string  `json:"optionId,omitempty"`        // kind=option_quantity (with FieldID)
    VariableID     string  `json:"variableId,omitempty"`      // kind=variable
    LocalVariableID string `json:"localVariableId,omitempty"` // kind=local_variable
    PlaceholderID  string  `json:"placeholderId,omitempty"`   // kind=placeholder
}
```

Or use the interface+switch pattern for stronger type safety:

```go
type CalculationStep interface { stepKind() string }

type CalculationExpr struct {
    Kind      string    `json:"kind"` // always "calculation"
    ID        string    `json:"id"`
    Operation string    `json:"operation"`
    Left      Operand   `json:"left"`
    Right     *Operand  `json:"right,omitempty"`
    ValuesList []Operand `json:"valuesList,omitempty"`
    Name      *string   `json:"name,omitempty"`
}

type ConditionalExpr struct { ... }
type VariableDefExpr struct { ... }
type SavedCalcExpr struct { ... }
```

### 2. Custom JSON Unmarshaling (Dual-Format Read)

**File**: `internal/domain/calculations/json.go`

```go
func UnmarshalCalculationSteps(data []byte) ([]CalculationStep, error) {
    // Try discriminated union first (look for "kind" field)
    // If no "kind" field, fall back to flat format conversion
    // This gives backward compatibility
}
```

Key logic:
- Detect format by checking for `kind` field on each step object
- If `kind` present → parse as discriminated union
- If `kind` absent → convert from flat format using same logic as frontend's `fromLegacy()`
- Output always in new format

### 3. Custom JSON Marshaling (New Format Only)

```go
func MarshalCalculationSteps(steps []CalculationStep) ([]byte, error) {
    // Always output discriminated union format
    // Never output flat format
}
```

### 4. Update Constraint/SavedCalculation Handlers

**Files**:
- `internal/transport/http/handlers/constraints.go`
- `internal/transport/http/handlers/saved_calculations.go`

Currently Accept/return `any` for conditions/actions/calculation_steps. Change to:

```go
// Before (passthrough)
Conditions any `json:"conditions"`
Actions    any `json:"actions"`

// After (typed with dual-read)
Conditions []ConditionGroup  `json:"conditions"`
Actions    []ActionWithSteps  `json:"actions"`
```

Where `ActionWithSteps` includes typed `CalculationSteps []CalculationStep`.

### 5. DB Migration (No Schema Change Needed)

The DB uses `jsonb` columns. No ALTER TABLE needed. The migration is purely in application-layer JSON interpretation.

However, add a data migration to transform existing flat-format rows:

**File**: `supabase/migrations/YYYYMMDD_migrate_calculation_steps_to_discriminated_union.sql`

```sql
-- Transform flat-format calculation_steps in saved_calculations
-- to discriminated union format (adds "kind" field, nests operands)
--
-- This is idempotent — rows already in new format are unchanged.
-- Run once after backend code supports both formats.
```

The SQL would use `jsonb` path operations to:
1. Check each step object for `kind` field
2. If missing, add `kind` based on `type` field
3. Restructure `leftType`/`leftFieldId`/... into `left: {kind, ...}` object
4. Same for `right` operand
5. Rename `variableValueSteps` → `valueSteps`
6. Rename `condition` sub-objects

### 6. OpenAPI Spec Update

**File**: `openapi/openapi.yaml`

Add schema components for the new format:

```yaml
components:
  schemas:
    CalculationStep:
      oneOf:
        - $ref: '#/components/schemas/CalculationExpr'
        - $ref: '#/components/schemas/ConditionalExpr'
        - $ref: '#/components/schemas/VariableDefExpr'
        - $ref: '#/components/schemas/SavedCalcExpr'
      discriminator:
        propertyName: kind

    Operand:
      oneOf:
        - $ref: '#/components/schemas/NumberOperand'
        - $ref: '#/components/schemas/FieldOperand'
        # ... etc
      discriminator:
        propertyName: kind

    CalculationExpr:
      type: object
      required: [kind, id, operation, left]
      properties:
        kind: { type: string, enum: [calculation] }
        id: { type: string }
        operation: { $ref: '#/components/schemas/CalculationOperation' }
        left: { $ref: '#/components/schemas/Operand' }
        right: { $ref: '#/components/schemas/Operand' }
        valuesList: { type: array, items: { $ref: '#/components/schemas/Operand' } }
```

### 7. Import Configurator Edge Function Update

**File**: `supabase/functions/import-configurator/tools.ts`

Update `calculationStepSchema` from flat format to discriminated union:

```typescript
const operandSchema = {
  type: "object",
  required: ["kind"],
  properties: {
    kind: { type: "string", enum: ["number", "field", "previous_step", "option_quantity", "variable", "local_variable", "placeholder"] },
    value: { type: "number" },
    fieldId: { type: "string" },
    stepId: { type: "string" },
    optionId: { type: "string" },
    variableId: { type: "string" },
    localVariableId: { type: "string" },
    placeholderId: { type: "string" },
  },
};
```

### 8. Go Unit Tests

**Files**:
- `internal/domain/calculations/types_test.go` — struct construction, kind validation
- `internal/domain/calculations/json_test.go` — marshal/unmarshal round-trips
  - New format → new format (identity)
  - Flat format → new format (conversion)
  - Mixed array (some flat, some new) → all new
  - Nil/empty/invalid inputs
- Integration tests for constraint/saved_calculation handler endpoints

### 9. Frontend Converter Removal (after backend deployed)

Once backend serves new format:
1. Delete `fromLegacy()` / `toLegacy()` from frontend
2. Delete `CalculationStepLegacy` type
3. Delete `CalculationValueEntry`, `ConditionDef` types (only used by converters)
4. Update `useConstraintActions`, `conditionGroupEvaluator`, `constraintActionProcessor` to pass steps directly
5. Update all DB-facing types in `constraint.types.ts`, `conditionGroup.types.ts`, `elementTraversal.ts` to use `CalculationStep[]` instead of `CalculationStepLegacy[]`

## Rollout Order

1. **Add Go types + dual-format unmarshaling** — non-breaking, reads both formats
2. **Update OpenAPI spec** — documents new format as canonical
3. **Deploy backend** — starts outputting new format, accepts both
4. **SQL data migration** — transform existing flat rows to new format (idempotent)
5. **Update import function** — generates new format
6. **Remove frontend converters** — breaking change, requires backend deployed first
7. **Remove flat-format read support from backend** — after frontend is migrated

## Risk Assessment

- **Low risk**: Backend currently passes JSON through untyped — no existing typed code to break
- **Medium risk**: Data migration converting existing JSONB rows — test on staging first
- **Rollback**: Keep dual-format read support until all clients confirmed migrated