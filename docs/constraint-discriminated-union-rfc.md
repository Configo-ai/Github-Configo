# RFC: Constraint Discriminated Union Refactor

**Status:** Exploratory / Research  
**Scope:** All constraint levels (element, page, option)  
**Author:** AI Agent (synthesized from architecture discussion)  
**Related:** [Backend Calculation Migration](./backend-calculation-migration.md)

---

## 1. Executive Summary

This RFC proposes applying the same discriminated union pattern (successfully used for calculation steps) to **constraint conditions and actions**. Currently, constraints use flat `any` / `unknown[]` types for `conditions` and `actions`, making it difficult for AI agent builders to generate valid constraints programmatically.

The refactor introduces typed `Condition` and `Action` discriminated unions with explicit `kind` fields, dual-format backward compatibility, and a machine-readable OpenAPI schema.

---

## 2. Problem Statement

### 2.1 Current Flat Format

```json
{
  "conditions": [
    {
      "type": "group",
      "logicOperator": "and",
      "children": [
        {
          "type": "number_value",
          "elementId": "field-1",
          "operator": "greater_than",
          "value": 5,
          "calculationSteps": [],
          "comparisonCalculationSteps": []
        },
        {
          "type": "option_selected",
          "elementId": "field-2",
          "optionIds": ["opt-1"]
        }
      ]
    }
  ],
  "actions": [
    {
      "type": "set_value",
      "value": 10,
      "valueMode": "direct",
      "calculationSteps": [],
      "variableId": null,
      "savedCalculationId": null,
      "savedCalculationMappings": []
    }
  ]
}
```

**AI Agent Pain Points:**
- **Ambiguous field presence:** `calculationSteps`, `variableId`, `savedCalculationId` are all optional on every action. AI must know which combinations are valid.
- **No type safety:** Backend accepts `any`, so invalid constraints silently fail or behave unexpectedly at runtime.
- **Cross-scope confusion:** Cross-configurator references use the same `elementId` field with no indication the field lives elsewhere.
- **Hard to validate:** PostgreSQL functions (`sanitize_constraint_condition_node`, `is_valid_constraint_condition_node`) validate at DB level, but there's no typed API contract.

### 2.2 What Worked for Calculations

The calculation step refactor introduced:
- Discriminated union with `kind` field
- Dual-format read (legacy flat + new format)
- New-format-only write
- Typed Go structs + OpenAPI schema
- AI agents can now generate `CalculationStep[]` with confidence

**This RFC applies the same pattern to constraints.**

---

## 3. Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Scope** | All levels (element, page, option) | Reusable base types; scope-specific subsets via composition |
| **Backward compatibility** | Dual-format (read old+new, write new only) | Same proven approach as calculations; avoids breaking existing data |
| **Condition nesting** | Keep recursive groups (max 3 levels) | Needed for complex rules; best AI compromise with explicit `type: "group"` nodes |
| **Action value sources** | Nested discriminated union | Single action kind + explicit `source` union; extensible without kind explosion |
| **Cross-scope** | Explicit cross-scope condition kinds | Clear to AI; enables backend validation of target configurator access |
| **Validation** | Go struct validation (primary) + PostgreSQL (safety net) | Backend is source of truth; catches invalid constraints before DB write |
| **OpenAPI** | Full schema with discriminator | AI agents consume OpenAPI to generate correct constraint JSON |
| **Migration** | SQL data migration (one-time) | Transform all existing flat-format rows to new format |
| **Timeline** | Exploratory / research | Document now; implement when prioritized |

---

## 4. Target Architecture

### 4.1 High-Level Structure

A constraint now has:
```
Constraint
├── metadata (id, name, scope, priority, enabled, ...)
├── conditions: ConditionGroup[]
└── actions: Action[]
```

Where:
- `ConditionGroup` = recursive tree of `ConditionNode`
- `ConditionNode` = `ConditionGroup | ConditionItem`
- `ConditionItem` = discriminated union by `kind`
- `Action` = discriminated union by `kind`
- `Action.value` (when present) = nested `ValueSource` discriminated union

### 4.2 Condition Discriminated Union

#### Local Conditions

```typescript
// TypeScript (frontend)
type ConditionItem =
  | { kind: "option_selected"; elementId: string; optionIds?: string[] }
  | { kind: "number_value"; elementId: string; operator: string; value: number }
  | { kind: "number_calculation"; elementId: string; operator: string; value: number; calculationSteps: CalculationStep[] }
  | { kind: "number_variable"; elementId: string; operator: string; value: number; variableId: string }
  | { kind: "option_calculation"; elementId: string; optionIds?: string[]; calculationSteps: CalculationStep[] }
```

```go
// Go (backend)
type ConditionItem struct {
    Kind string `json:"kind"`
    
    // Common to all condition kinds
    ElementID string `json:"element_id,omitempty"`
    
    // kind == "option_selected" | "option_calculation"
    OptionIDs []string `json:"option_ids,omitempty"`
    
    // kind == "number_value" | "number_calculation" | "number_variable"
    Operator string `json:"operator,omitempty"`
    Value    float64 `json:"value,omitempty"`
    
    // kind == "number_calculation" | "option_calculation"
    CalculationSteps []calculations.CalculationStep `json:"calculation_steps,omitempty"`
    
    // kind == "number_variable"
    VariableID string `json:"variable_id,omitempty"`
}
```

#### Cross-Scope Conditions

```typescript
type CrossScopeConditionItem =
  | { kind: "cross_scope_number_value"; configuratorId: string; elementId: string; operator: string; value: number }
  | { kind: "cross_scope_option_selected"; configuratorId: string; elementId: string; optionIds?: string[] }
  | { kind: "cross_scope_number_calculation"; configuratorId: string; elementId: string; operator: string; value: number; calculationSteps: CalculationStep[] }
  | { kind: "cross_scope_number_variable"; configuratorId: string; elementId: string; operator: string; value: number; variableId: string }
  | { kind: "cross_scope_option_calculation"; configuratorId: string; elementId: string; optionIds?: string[]; calculationSteps: CalculationStep[] }
```

```go
type CrossScopeConditionItem struct {
    Kind           string  `json:"kind"`
    ConfiguratorID string  `json:"configurator_id"`
    ElementID      string  `json:"element_id,omitempty"`
    OptionIDs      []string `json:"option_ids,omitempty"`
    Operator       string  `json:"operator,omitempty"`
    Value          float64 `json:"value,omitempty"`
    CalculationSteps []calculations.CalculationStep `json:"calculation_steps,omitempty"`
    VariableID     string  `json:"variable_id,omitempty"`
}
```

**Rationale for explicit cross-scope kinds:**
- AI knows immediately when a condition references another configurator
- Backend can validate `configurator_id` exists and user has access
- No opaque string conventions like `"config-123::field-456"`
- OpenAPI schema clearly separates local vs cross-scope

#### Condition Groups

```typescript
type ConditionNode = ConditionItem | CrossScopeConditionItem | ConditionGroup;

interface ConditionGroup {
  kind: "group";
  logicOperator: "and" | "or";
  children: ConditionNode[];
}
```

**Depth limit:** Max 3 levels (depths 0, 1, 2). Enforced by backend validation.

```go
type ConditionGroup struct {
    Kind          string          `json:"kind"` // always "group"
    LogicOperator string          `json:"logic_operator"`
    Children      []ConditionNode `json:"children"`
}

type ConditionNode struct {
    Kind string `json:"kind"`
    // Embedded fields from ConditionItem / CrossScopeConditionItem / ConditionGroup
    // NOTE: This flat struct is necessary for Go's json.Unmarshal with discriminated unions.
    // The struct contains all possible fields with omitempty; the Kind field determines
    // which fields are relevant. This is the same pattern used by CalculationStep.
}
```

### 4.3 Action Discriminated Union

#### Base Action Types

```typescript
type Action =
  | { kind: "show" }
  | { kind: "hide" }
  | { kind: "required" }
  | { kind: "not_required" }
  | { kind: "message"; message: string; severity: "info" | "warning" | "error" | "success" }
  | { kind: "set"; targetOptionId: string }
  | { kind: "unset"; targetOptionId: string }
  | { kind: "disable" }
  | SetValueAction
  | SetQuantityAction;
```

#### Value Source (Nested Discriminated Union)

```typescript
type ValueSource =
  | { kind: "direct"; value: number | string }
  | { kind: "field"; fieldId: string }
  | { kind: "calculation"; steps: CalculationStep[] }
  | { kind: "variable"; variableId: string }
  | { kind: "saved_calculation"; savedCalculationId: string; mappings: SavedCalculationMapping[] };

type SetValueAction = {
  kind: "set_value";
  source: ValueSource;
};

type SetQuantityAction = {
  kind: "set_quantity";
  targetOptionId: string;
  source: ValueSource;
};
```

```go
type ValueSource struct {
    Kind               string                    `json:"kind"` // "direct", "field", "calculation", "variable", "saved_calculation"
    Value              float64                   `json:"value,omitempty"`
    FieldID            string                    `json:"field_id,omitempty"`
    Steps              []calculations.CalculationStep `json:"steps,omitempty"`
    VariableID         string                    `json:"variable_id,omitempty"`
    SavedCalculationID string                    `json:"saved_calculation_id,omitempty"`
    Mappings           []SavedCalculationMapping `json:"mappings,omitempty"`
}

// Validate checks that only the fields relevant to Kind are populated.
// This prevents invalid combinations (e.g., kind="direct" with field_id set).
func (vs ValueSource) Validate() error {
    switch vs.Kind {
    case "direct":
        if vs.FieldID != "" || vs.Steps != nil || vs.VariableID != "" || vs.SavedCalculationID != "" {
            return fmt.Errorf("value source kind=%q should only have value field", vs.Kind)
        }
    case "field":
        if vs.Value != 0 || vs.Steps != nil || vs.VariableID != "" || vs.SavedCalculationID != "" {
            return fmt.Errorf("value source kind=%q should only have field_id", vs.Kind)
        }
    // ... etc for other kinds
    default:
        return fmt.Errorf("unknown value source kind: %q", vs.Kind)
    }
    return nil
}

type Action struct {
    Kind string `json:"kind"`
    
    // kind == "message"
    Message  string `json:"message,omitempty"`
    Severity string `json:"severity,omitempty"` // "info", "warning", "error", "success"
    
    // kind == "set" | "unset" | "set_quantity"
    TargetOptionID string `json:"target_option_id,omitempty"`
    
    // kind == "set_value" | "set_quantity"
    Source *ValueSource `json:"source,omitempty"`
}
```

**Why nested discriminated union for value sources:**
- Extensible: adding a new value source type only requires adding to `ValueSource`, not creating N new action kinds
- AI generates `source: { kind: "calculation", steps: [...] }` — clear and unambiguous
- Go struct stays flat (one struct per action), but the JSON contract is clean

### 4.4 Scope-Specific Subsets

```typescript
// Element constraints: full action set
type ElementAction = Action;

// Page constraints: subset
type PageAction =
  | { kind: "show" }
  | { kind: "hide" }
  | { kind: "message"; message: string; severity: "info" | "warning" | "error" | "success" };

// Option constraints: subset
type OptionAction =
  | { kind: "set" }
  | { kind: "unset" }
  | { kind: "set_quantity"; targetOptionId: string; source: ValueSource }
  | { kind: "show" }
  | { kind: "hide" }
  | { kind: "disable" }
  | { kind: "message"; message: string; severity: "info" | "warning" | "error" | "success" };
```

Backend validation rejects invalid action kinds for the constraint's target level (page/element/option).

---

## 5. Dual-Format Compatibility

Same strategy as calculation steps:

### 5.1 Read Path

```go
func UnmarshalConditions(data []byte) ([]ConditionNode, error) {
    // 1. Try new format (look for "kind" field on root nodes)
    // 2. If no "kind" found, detect legacy format:
    //    - legacy: { type: "group", logicOperator: "and", children: [...] }
    //    - legacy leaf: { type: "number_value", elementId: "...", ... }
    // 3. Convert legacy → new format using mapping rules
    // 4. Return always in new format
}

func UnmarshalActions(data []byte) ([]Action, error) {
    // Same approach:
    // 1. Try new format (look for "kind" field)
    // 2. If legacy format detected, convert:
    //    - type: "set_value" + valueMode: "direct" → kind: "set_value", source: { kind: "direct", value: ... }
    //    - type: "set_value" + valueMode: "calculation" → kind: "set_value", source: { kind: "calculation", steps: ... }
    //    - etc.
    // 3. Return always in new format
}
```

### 5.2 Write Path

```go
func MarshalConditions(nodes []ConditionNode) ([]byte, error) {
    // Always output new discriminated union format
}

func MarshalActions(actions []Action) ([]byte, error) {
    // Always output new discriminated union format
}
```

### 5.3 Legacy → New Format Mapping Rules

**Conditions:**
| Legacy Field | New Format |
|-------------|-----------|
| `type: "group"` | `kind: "group"` |
| `type: "number_value"` | `kind: "number_value"` |
| `type: "option_selected"` | `kind: "option_selected"` |
| `logicOperator` | `logic_operator` |
| `elementId` | `element_id` |
| `optionIds` | `option_ids` |
| `calculationSteps` | `calculation_steps` |
| `comparisonCalculationSteps` | `calculation_steps` (on the condition itself) |
| `valueSource: "variable"` + `comparisonVariableId` | `kind: "number_variable"` + `variable_id` |
| `scope: "cross"` in parent constraint | Prefix condition `kind` with `cross_scope_` |

**Actions:**
| Legacy | New Format |
|--------|-----------|
| `type: "show"` | `kind: "show"` |
| `type: "set_value"` + `valueMode: "direct"` + `value` | `kind: "set_value"`, `source: { kind: "direct", value }` |
| `type: "set_value"` + `valueMode: "field"` + `value` (field: prefix) | `kind: "set_value"`, `source: { kind: "field", field_id }` |
| `type: "set_value"` + `valueMode: "calculation"` + `calculationSteps` | `kind: "set_value"`, `source: { kind: "calculation", steps }` |
| `type: "set_value"` + `valueMode: "variable"` + `variableId` | `kind: "set_value"`, `source: { kind: "variable", variable_id }` |
| `type: "set_value"` + `valueMode: "saved_calculation"` + `savedCalculationId` + `savedCalculationMappings` | `kind: "set_value"`, `source: { kind: "saved_calculation", saved_calculation_id, mappings }` |
| `type: "set"` + `targetOptionId` | `kind: "set"`, `target_option_id` |
| `type: "set_quantity"` + ... | `kind: "set_quantity"`, `target_option_id`, `source: {...}` |
| `condition` (deprecated) | Map to `type` → `kind` |

---

## 6. Backend Implementation

### 6.1 New Package: `internal/domain/constraints/types`

```
internal/domain/constraints/
├── service.go              # existing
├── permissions.go          # existing
├── types.go                # existing Constraint struct (updated)
└── typed/
    ├── conditions.go       # ConditionNode, ConditionGroup, ConditionItem, CrossScopeConditionItem
    ├── actions.go          # Action, ValueSource
    ├── json.go             # Marshal/Unmarshal functions (dual-format)
    └── json_test.go        # Round-trip tests
```

### 6.2 Updated Constraint Struct

```go
type Constraint struct {
    ID                   string              `json:"id"`
    OrganizationID       string              `json:"organization_id"`
    SourceConfiguratorID string              `json:"source_configurator_id"`
    TargetConfiguratorID *string             `json:"target_configurator_id,omitempty"`
    Scope                string              `json:"scope"`
    Priority             int                 `json:"priority"`
    Enabled              bool                `json:"enabled"`
    Name                 *string             `json:"name,omitempty"`
    Note                 *string             `json:"note,omitempty"`
    SourcePageID         *string             `json:"source_page_id,omitempty"`
    SourceFieldIDs       []string            `json:"source_field_ids"`
    TargetFieldID        *string             `json:"target_field_id,omitempty"`
    TargetFormKey        *string             `json:"target_form_key,omitempty"`
    Conditions           []typed.ConditionNode `json:"conditions"`  // WAS: any
    Actions              []typed.Action        `json:"actions"`     // WAS: any
    CreatedBy            *string             `json:"created_by,omitempty"`
    UpdatedBy            *string             `json:"updated_by,omitempty"`
    CreatedAt            string              `json:"created_at"`
    UpdatedAt            string              `json:"updated_at"`
}
```

### 6.3 Custom JSON Unmarshaling

Custom unmarshal lives in the `constraints` package (not `typed`) to avoid circular imports:

```go
// internal/domain/constraints/json.go
package constraints

import "encoding/json"

func (c *Constraint) UnmarshalJSON(data []byte) error {
    type alias Constraint // prevent recursion
    var raw alias
    if err := json.Unmarshal(data, &raw); err != nil {
        return err
    }
    
    // Conditions and actions are json.RawMessage at this point
    // Convert to typed structs via typed.UnmarshalConditions/Actions
    // ...
    
    *c = Constraint(raw)
    return nil
}
```

**Repository layer:** The repository currently uses `json.RawMessage` for conditions/actions. Update to use the typed structs.

### 6.4 Validation

```go
// typed/validate.go
func ValidateConditions(nodes []ConditionNode, scope string, targetLevel string) error
func ValidateActions(actions []Action, targetLevel string) error
```

Validation rules:
- **Depth:** Max 3 levels for condition groups
- **Cross-scope:** `cross_scope_*` kinds only valid when constraint scope is `"cross"`
- **Target level:** Page constraints reject `set_value`, `required`, etc.
- **Field references:** All `element_id` and `field_id` values must be valid UUIDs (format check)
- **Calculation steps:** Delegate to `calculations.ValidateSteps()`
- **Variable references:** Check `variable_id` exists in organization's variables

### 6.5 Handler Updates

```go
// internal/transport/http/handlers/constraints.go

// Update request/response DTOs
type CreateConstraintRequest struct {
    Name         *string             `json:"name,omitempty"`
    Scope        string              `json:"scope"`
    SourceFieldIDs []string          `json:"source_field_ids"`
    TargetFieldID  *string           `json:"target_field_id,omitempty"`
    SourcePageID   *string           `json:"source_page_id,omitempty"`
    TargetLevel    string            `json:"target_level"` // "page" | "element" | "option"
    Conditions     []typed.ConditionNode `json:"conditions"`
    Actions        []typed.Action        `json:"actions"`
}

func (h *ConstraintsHandler) Create(w http.ResponseWriter, r *http.Request) {
    var req CreateConstraintRequest
    if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
        response.WriteError(w, http.StatusBadRequest, "invalid_request", "request body must be valid JSON")
        return
    }
    
    // Validate
    if err := typed.ValidateConditions(req.Conditions, req.Scope, req.TargetLevel); err != nil {
        response.WriteError(w, http.StatusBadRequest, "validation_error", err.Error())
        return
    }
    
    // ... rest of handler
}
```

---

## 7. Frontend Implementation

### 7.1 Type Updates

```typescript
// features/configurators/types/constraint.types.ts (refactored)

// Re-export from new typed module
export type {
  ConditionNode,
  ConditionGroup,
  ConditionItem,
  CrossScopeConditionItem,
  Action,
  ValueSource,
} from "./constraint-typed.types";

// Scope-specific action subsets (for form builder validation)
export type ElementAction = Action;
export type PageAction = Extract<Action, { kind: "show" | "hide" | "message" }>;
export type OptionAction = Extract<
  Action,
  { kind: "set" | "unset" | "set_quantity" | "show" | "hide" | "disable" | "message" }
>;
```

### 7.2 New File: `constraint-typed.types.ts`

```typescript
// Condition discriminated union
export type ConditionItem =
  | { kind: "option_selected"; elementId: string; optionIds?: string[] }
  | { kind: "number_value"; elementId: string; operator: string; value: number }
  | { kind: "number_calculation"; operator: string; value: number; calculationSteps: CalculationStep[] }
  | { kind: "number_variable"; operator: string; value: number; variableId: string }
  | { kind: "option_calculation"; optionIds?: string[]; calculationSteps: CalculationStep[] }
  | CrossScopeConditionItem;

export type CrossScopeConditionItem =
  | { kind: "cross_scope_option_selected"; configuratorId: string; elementId: string; optionIds?: string[] }
  | { kind: "cross_scope_number_value"; configuratorId: string; elementId: string; operator: string; value: number }
  | { kind: "cross_scope_number_calculation"; configuratorId: string; operator: string; value: number; calculationSteps: CalculationStep[] }
  | { kind: "cross_scope_number_variable"; configuratorId: string; operator: string; value: number; variableId: string };

export interface ConditionGroup {
  kind: "group";
  logicOperator: "and" | "or";
  children: ConditionNode[];
}

export type ConditionNode = ConditionItem | ConditionGroup;

// Value source discriminated union
export type ValueSource =
  | { kind: "direct"; value: number | string }
  | { kind: "field"; fieldId: string }
  | { kind: "calculation"; steps: CalculationStep[] }
  | { kind: "variable"; variableId: string }
  | { kind: "saved_calculation"; savedCalculationId: string; mappings: SavedCalculationMapping[] };

// Action discriminated union
export type Action =
  | { kind: "show" }
  | { kind: "hide" }
  | { kind: "required" }
  | { kind: "not_required" }
  | { kind: "message"; message: string; severity: "info" | "warning" | "error" | "success" }
  | { kind: "set"; targetOptionId: string }
  | { kind: "unset"; targetOptionId: string }
  | { kind: "disable" }
  | { kind: "set_value"; source: ValueSource }
  | { kind: "set_quantity"; targetOptionId: string; source: ValueSource };

// Type guards
const CROSS_SCOPE_KINDS = new Set([
  "cross_scope_number_value",
  "cross_scope_option_selected",
  "cross_scope_number_calculation",
  "cross_scope_number_variable",
  "cross_scope_option_calculation",
]);

export function isConditionGroup(node: ConditionNode): node is ConditionGroup {
  return node.kind === "group";
}

export function isCrossScopeCondition(item: ConditionItem): item is CrossScopeConditionItem {
  return CROSS_SCOPE_KINDS.has(item.kind);
}

export function isValueSourceOfKind<T extends ValueSource["kind"]>(
  source: ValueSource,
  kind: T
): source is Extract<ValueSource, { kind: T }> {
  return source.kind === kind;
}
```

### 7.3 Runtime Evaluators

Update these files to use discriminated unions:
- `conditionGroupEvaluator.ts` — branch on `node.kind`
- `constraintActionProcessor.ts` — branch on `action.kind`, then `action.source.kind`
- `elementTraversal.ts` — update `RuntimeConstraint` to use typed conditions/actions

```typescript
// conditionGroupEvaluator.ts — simplified example
function evaluateSingleCondition(
  condition: ConditionNode,
  formValues: FormValues,
  fields: FormField[]
): boolean {
  if (isConditionGroup(condition)) {
    return evaluateConditionGroup(condition, formValues, fields);
  }

  switch (condition.kind) {
    case "number_value":
      return evaluateNumberCondition(condition, formValues);
    case "number_calculation":
      const calcResult = evaluateCalculationSteps(condition.calculationSteps, formValues);
      return compare(calcResult, condition.operator, condition.value);
    case "number_variable":
      const varValue = variables[condition.variableId];
      return compare(varValue, condition.operator, condition.value);
    case "option_selected":
      return evaluateOptionSelected(condition, formValues, fields);
    case "cross_scope_number_value":
      // Fetch value from cross-configurator form state
      const crossValue = getCrossScopeValue(condition.configuratorId, condition.elementId);
      return compare(crossValue, condition.operator, condition.value);
    // ... etc
  }
}
```

### 7.4 Form Builder UI

Update constraint draft builders:
- `ConditionDraft` → typed `ConditionNode` builder
- `ActionDraft` → typed `Action` builder
- Remove `valueMode`, `calculationMode`, `comparisonValueMode` fields (replaced by discriminated union)

---

## 8. Database Migration

### 8.1 Migration Script

**File:** `supabase/migrations/YYYYMMDD_migrate_constraints_to_discriminated_union.sql`

```sql
-- Migrate constraints.conditions from legacy format to new discriminated union format
-- This is idempotent — constraints already in new format are unchanged.

CREATE OR REPLACE FUNCTION public.migrate_constraint_conditions(conditions jsonb)
RETURNS jsonb AS $$
DECLARE
  result jsonb;
  node jsonb;
  migrated_children jsonb;
  child jsonb;
BEGIN
  -- Handle array of condition groups
  IF jsonb_typeof(conditions) = 'array' THEN
    result := '[]'::jsonb;
    FOR node IN SELECT jsonb_array_elements(conditions) LOOP
      result := result || jsonb_build_array(migrate_condition_node(node));
    END LOOP;
    RETURN result;
  END IF;
  
  RETURN conditions;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.migrate_condition_node(node jsonb)
RETURNS jsonb AS $$
DECLARE
  node_type text;
  result jsonb;
BEGIN
  -- Already migrated?
  IF node ? 'kind' THEN
    RETURN node;
  END IF;
  
  node_type := node->>'type';
  
  -- Group node
  IF node_type = 'group' THEN
  result := jsonb_build_object(
    'kind', 'group',
    'logic_operator', COALESCE(group_node->>'logic_operator', 'and'),
    'children', '[]'::jsonb
  );
    
    IF node ? 'children' AND jsonb_typeof(node->'children') = 'array' THEN
      DECLARE
        child jsonb;
        migrated jsonb := '[]'::jsonb;
      BEGIN
        FOR child IN SELECT jsonb_array_elements(node->'children') LOOP
          migrated := migrated || jsonb_build_array(migrate_condition_node(child));
        END LOOP;
        result := jsonb_set(result, '{children}', migrated);
      END;
    END IF;
    
    RETURN result;
  END IF;
  
  -- Leaf condition: number_value
  IF node_type = 'number_value' THEN
    result := jsonb_build_object(
      'kind', 'number_value',
      'element_id', node->>'elementId',
      'operator', node->>'operator',
      'value', (node->>'value')::float
    );
    
    -- Handle value source variations
    -- Legacy conditions store variable references in either valueSource='variable' or a variableId field
    IF node->>'valueSource' = 'variable' OR node->>'valueSource' = 'comparison_variable' OR node ? 'variableId' OR node ? 'comparisonVariableId' THEN
      result := jsonb_build_object(
        'kind', 'number_variable',
        'element_id', node->>'elementId',
        'operator', node->>'operator',
        'value', COALESCE((node->>'value')::float, 0),
        'variable_id', COALESCE(node->>'variableId', node->>'comparisonVariableId', '')
      );
    ELSIF node ? 'calculationSteps' AND jsonb_array_length(node->'calculationSteps') > 0 THEN
      result := jsonb_build_object(
        'kind', 'number_calculation',
        'element_id', node->>'elementId',
        'operator', node->>'operator',
        'value', (node->>'value')::float,
        'calculation_steps', migrate_calculation_steps(node->'calculationSteps')
      );
    END IF;
    
    RETURN result;
  END IF;
  
  -- Leaf condition: option_selected
  IF node_type = 'option_selected' THEN
    result := jsonb_build_object(
      'kind', 'option_selected',
      'element_id', node->>'elementId',
      'option_ids', COALESCE(node->'optionIds', node->'option_ids', '[]'::jsonb)
    );
    
    IF node ? 'calculationSteps' AND jsonb_array_length(node->'calculationSteps') > 0 THEN
      result := jsonb_build_object(
        'kind', 'option_calculation',
        'element_id', node->>'elementId',
        'option_ids', COALESCE(node->'optionIds', node->'option_ids', '[]'::jsonb),
        'calculation_steps', migrate_calculation_steps(node->'calculationSteps')
      );
    END IF;
    
    RETURN result;
  END IF;
  
  RETURN node;
END;
$$ LANGUAGE plpgsql;

-- Migrate constraints.actions from legacy format to new discriminated union format
CREATE OR REPLACE FUNCTION public.migrate_constraint_actions(actions jsonb)
RETURNS jsonb AS $$
DECLARE
  result jsonb := '[]'::jsonb;
  action jsonb;
  migrated jsonb;
BEGIN
  IF jsonb_typeof(actions) != 'array' THEN
    RETURN actions;
  END IF;
  
  FOR action IN SELECT jsonb_array_elements(actions) LOOP
    -- Already migrated?
    IF action ? 'kind' THEN
      result := result || jsonb_build_array(action);
      CONTINUE;
    END IF;
    
    migrated := migrate_single_action(action);
    result := result || jsonb_build_array(migrated);
  END LOOP;
  
  RETURN result;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.migrate_single_action(action jsonb)
RETURNS jsonb AS $$
DECLARE
  action_type text;
  value_mode text;
  source jsonb;
  result jsonb;
BEGIN
  action_type := COALESCE(action->>'type', action->>'condition');
  
  -- Simple actions (no value)
  IF action_type IN ('show', 'hide', 'required', 'not_required', 'disable') THEN
    RETURN jsonb_build_object('kind', action_type);
  END IF;
  
  -- Message action
  IF action_type = 'message' THEN
    RETURN jsonb_build_object(
      'kind', 'message',
      'message', COALESCE(action->>'message', action->>'value', ''),
      'severity', COALESCE(action->>'severity', 'info')
    );
  END IF;
  
  -- Set / Unset actions
  IF action_type IN ('set', 'unset') THEN
    RETURN jsonb_build_object(
      'kind', action_type,
      'target_option_id', action->>'targetOptionId'
    );
  END IF;
  
  -- Set value action
  IF action_type = 'set_value' THEN
    value_mode := COALESCE(action->>'valueMode', 'direct');
    
    CASE value_mode
      WHEN 'direct' THEN
        source := jsonb_build_object('kind', 'direct', 'value', action->'value');
      WHEN 'field' THEN
        -- Legacy field values may be "field:uuid" or bare uuid; handle both
        DECLARE
          raw_value text := COALESCE(action->>'value', '');
          field_id text;
        BEGIN
          IF raw_value LIKE 'field:%' THEN
            field_id := trim(both 'field:' from raw_value);
          ELSE
            field_id := raw_value;
          END IF;
          source := jsonb_build_object('kind', 'field', 'field_id', field_id);
        END;
      WHEN 'calculation' THEN
        source := jsonb_build_object('kind', 'calculation', 'steps', migrate_calculation_steps(action->'calculationSteps'));
      WHEN 'variable' THEN
        source := jsonb_build_object('kind', 'variable', 'variable_id', action->>'variableId');
      WHEN 'saved_calculation' THEN
        source := jsonb_build_object(
          'kind', 'saved_calculation',
          'saved_calculation_id', action->>'savedCalculationId',
          'mappings', COALESCE(action->'savedCalculationMappings', '[]'::jsonb)
        );
      ELSE
        source := jsonb_build_object('kind', 'direct', 'value', action->'value');
    END CASE;
    
    RETURN jsonb_build_object('kind', 'set_value', 'source', source);
  END IF;
  
  -- Set quantity action
  IF action_type = 'set_quantity' THEN
    value_mode := COALESCE(action->>'valueMode', 'direct');
    
    CASE value_mode
      WHEN 'direct' THEN
        source := jsonb_build_object('kind', 'direct', 'value', action->'value');
      WHEN 'calculation' THEN
        source := jsonb_build_object('kind', 'calculation', 'steps', migrate_calculation_steps(action->'calculationSteps'));
      WHEN 'variable' THEN
        source := jsonb_build_object('kind', 'variable', 'variable_id', action->>'variableId');
      ELSE
        source := jsonb_build_object('kind', 'direct', 'value', action->'value');
    END CASE;
    
    RETURN jsonb_build_object(
      'kind', 'set_quantity',
      'target_option_id', action->>'targetOptionId',
      'source', source
    );
  END IF;
  
  RETURN action;
END;
$$ LANGUAGE plpgsql;

-- Helper: migrate calculation steps (reuses existing calculation migration if available)
CREATE OR REPLACE FUNCTION public.migrate_calculation_steps(steps jsonb)
RETURNS jsonb AS $$
BEGIN
  -- If calculation steps already have 'kind', return as-is
  IF jsonb_typeof(steps) = 'array' AND jsonb_array_length(steps) > 0 THEN
    IF (steps->0) ? 'kind' THEN
      RETURN steps;
    END IF;
  END IF;
  
    -- Reuse calculation step migration: if legacy flat format detected, convert to discriminated union
  -- This depends on the existing calculation_steps migration being applied first
  IF jsonb_typeof(steps) = 'array' AND jsonb_array_length(steps) > 0 THEN
    -- Check if first step lacks 'kind' (legacy flat format)
    IF NOT (steps->0) ? 'kind' THEN
      -- Delegate to existing calculation step migration function
      -- Requires: supabase/migrations/YYYYMMDD_migrate_calculation_steps_to_discriminated_union.sql
      RETURN public.migrate_calculation_steps_to_union(steps);
    END IF;
  END IF;
  
  RETURN steps;
END;
$$ LANGUAGE plpgsql;

-- Apply migration to constraints not yet migrated (detected by absence of 'kind' field)
UPDATE configurator.constraints
SET 
  conditions = migrate_constraint_conditions(conditions),
  actions = migrate_constraint_actions(actions)
WHERE 
  (conditions IS NOT NULL AND jsonb_typeof(conditions) = 'array' AND jsonb_array_length(conditions) > 0 AND NOT (conditions->0) ? 'kind')
  OR (actions IS NOT NULL AND jsonb_typeof(actions) = 'array' AND jsonb_array_length(actions) > 0 AND NOT (actions->0) ? 'kind');

-- Verify migration
SELECT 
  id,
  CASE 
    WHEN jsonb_typeof(conditions) = 'array' AND jsonb_array_length(conditions) > 0 
    THEN (conditions->0) ? 'kind'
    ELSE true
  END as conditions_migrated,
  CASE 
    WHEN jsonb_typeof(actions) = 'array' AND jsonb_array_length(actions) > 0 
    THEN (actions->0) ? 'kind'
    ELSE true
  END as actions_migrated
FROM configurator.constraints;
```

### 8.2 Cross-Scope Detection

The migration must detect cross-scope constraints and apply `cross_scope_` prefix to condition kinds:

```sql
-- After migrating conditions, update cross-scope constraint condition kinds
UPDATE configurator.constraints c
SET conditions = (
  SELECT jsonb_agg(
    CASE 
      WHEN (node->>'kind') IN ('number_value', 'option_selected', 'number_calculation', 'number_variable', 'option_calculation')
      THEN jsonb_set(node, '{kind}', to_jsonb('cross_scope_' || (node->>'kind')))
      WHEN (node->>'kind') = 'group' THEN migrate_group_to_cross_scope(node, c.target_configurator_id)
      ELSE node
    END
  )
  FROM jsonb_array_elements(c.conditions) as node
)
WHERE c.scope = 'cross';

-- Helper function for recursive group conversion
CREATE OR REPLACE FUNCTION public.migrate_group_to_cross_scope(group_node jsonb, target_configurator_id text)
RETURNS jsonb AS $$
DECLARE
  result jsonb;
  child jsonb;
  migrated_children jsonb := '[]'::jsonb;
BEGIN
  result := jsonb_build_object(
    'kind', 'group',
    'logic_operator', COALESCE(group_node->>'logic_operator', group_node->>'logicOperator', 'and'),
    'children', '[]'::jsonb
  );
  
  IF group_node ? 'children' AND jsonb_typeof(group_node->'children') = 'array' THEN
    FOR child IN SELECT jsonb_array_elements(group_node->'children') LOOP
      IF (child->>'kind') IN ('number_value', 'option_selected', 'number_calculation', 'number_variable', 'option_calculation') THEN
        child := jsonb_set(child, '{kind}', to_jsonb('cross_scope_' || (child->>'kind')));
        child := jsonb_set(child, '{configurator_id}', to_jsonb(target_configurator_id));
      ELSIF (child->>'kind') = 'group' THEN
        child := migrate_group_to_cross_scope(child, target_configurator_id);
      END IF;
      migrated_children := migrated_children || jsonb_build_array(child);
    END LOOP;
    result := jsonb_set(result, '{children}', migrated_children);
  END IF;
  
  RETURN result;
END;
      THEN jsonb_set(node, '{kind}', to_jsonb('cross_scope_' || (node->>'kind')))
      WHEN (node->>'kind') = 'group' THEN migrate_group_to_cross_scope(node, c.target_configurator_id)
      ELSE node
    END
  )
  FROM jsonb_array_elements(c.conditions) as node
)
WHERE c.scope = 'cross';

-- Helper function for recursive group conversion
CREATE OR REPLACE FUNCTION public.migrate_group_to_cross_scope(group_node jsonb, target_configurator_id text)
RETURNS jsonb AS $$
DECLARE
  result jsonb;
  child jsonb;
  migrated_children jsonb := '[]'::jsonb;
BEGIN
  result := jsonb_build_object(
    'kind', 'group',
    'logic_operator', COALESCE(group_node->>'logic_operator', group_node->>'logicOperator', 'and'),
    'children', '[]'::jsonb
  );
  
  IF group_node ? 'children' AND jsonb_typeof(group_node->'children') = 'array' THEN
    FOR child IN SELECT jsonb_array_elements(group_node->'children') LOOP
      IF (child->>'kind') IN ('number_value', 'option_selected', 'number_calculation', 'number_variable', 'option_calculation') THEN
        child := jsonb_set(child, '{kind}', to_jsonb('cross_scope_' || (child->>'kind')));
        child := jsonb_set(child, '{configurator_id}', to_jsonb(target_configurator_id));
      ELSIF (child->>'kind') = 'group' THEN
        child := migrate_group_to_cross_scope(child, target_configurator_id);
      END IF;
      migrated_children := migrated_children || jsonb_build_array(child);
    END LOOP;
    result := jsonb_set(result, '{children}', migrated_children);
  END IF;
  
  RETURN result;
END;
$$ LANGUAGE plpgsql;
```

---

## 9. OpenAPI Schema

### 9.1 New Components

```yaml
# openapi/openapi.yaml

components:
  schemas:
    ConditionNode:
      oneOf:
        - $ref: '#/components/schemas/ConditionGroup'
        - $ref: '#/components/schemas/ConditionItem'
        - $ref: '#/components/schemas/CrossScopeConditionItem'
      discriminator:
        propertyName: kind
        mapping:
          group: '#/components/schemas/ConditionGroup'
          number_value: '#/components/schemas/ConditionItem'
          option_selected: '#/components/schemas/ConditionItem'
          number_calculation: '#/components/schemas/ConditionItem'
          number_variable: '#/components/schemas/ConditionItem'
          option_calculation: '#/components/schemas/ConditionItem'
          cross_scope_number_value: '#/components/schemas/CrossScopeConditionItem'
          cross_scope_option_selected: '#/components/schemas/CrossScopeConditionItem'
          cross_scope_number_calculation: '#/components/schemas/CrossScopeConditionItem'
          cross_scope_number_variable: '#/components/schemas/CrossScopeConditionItem'

    ConditionGroup:
      type: object
      required: [kind, logic_operator, children]
      properties:
        kind:
          type: string
          enum: [group]
        logic_operator:
          type: string
          enum: [and, or]
        children:
          type: array
          items:
            $ref: '#/components/schemas/ConditionNode'

    ConditionItem:
      type: object
      required: [kind]
      properties:
        kind:
          type: string
          enum: [number_value, option_selected, number_calculation, number_variable, option_calculation]
        element_id:
          type: string
          format: uuid
        option_ids:
          type: array
          items:
            type: string
            format: uuid
        operator:
          type: string
          enum: [equals, greater_than, less_than, greater_or_equal, less_or_equal]
        value:
          type: number
        calculation_steps:
          type: array
          items:
            $ref: '#/components/schemas/CalculationStep'
        variable_id:
          type: string

    CrossScopeConditionItem:
      type: object
      required: [kind, configurator_id]
      properties:
        kind:
          type: string
          enum: [cross_scope_number_value, cross_scope_option_selected, cross_scope_number_calculation, cross_scope_number_variable, cross_scope_option_calculation]
        configurator_id:
          type: string
          format: uuid
        element_id:
          type: string
          format: uuid
        option_ids:
          type: array
          items:
            type: string
            format: uuid
        operator:
          type: string
          enum: [equals, greater_than, less_than, greater_or_equal, less_or_equal]
        value:
          type: number
        calculation_steps:
          type: array
          items:
            $ref: '#/components/schemas/CalculationStep'
        variable_id:
          type: string

    Action:
      oneOf:
        - $ref: '#/components/schemas/SimpleAction'
        - $ref: '#/components/schemas/MessageAction'
        - $ref: '#/components/schemas/TargetAction'
        - $ref: '#/components/schemas/SetValueAction'
        - $ref: '#/components/schemas/SetQuantityAction'
      discriminator:
        propertyName: kind
        mapping:
          show: '#/components/schemas/SimpleAction'
          hide: '#/components/schemas/SimpleAction'
          required: '#/components/schemas/SimpleAction'
          not_required: '#/components/schemas/SimpleAction'
          disable: '#/components/schemas/SimpleAction'
          message: '#/components/schemas/MessageAction'
          set: '#/components/schemas/TargetAction'
          unset: '#/components/schemas/TargetAction'
          set_value: '#/components/schemas/SetValueAction'
          set_quantity: '#/components/schemas/SetQuantityAction'

    SimpleAction:
      type: object
      required: [kind]
      properties:
        kind:
          type: string
          enum: [show, hide, required, not_required, disable]

    MessageAction:
      type: object
      required: [kind, message, severity]
      properties:
        kind:
          type: string
          enum: [message]
        message:
          type: string
        severity:
          type: string
          enum: [info, warning, error, success]

    TargetAction:
      type: object
      required: [kind, target_option_id]
      properties:
        kind:
          type: string
          enum: [set, unset]
        target_option_id:
          type: string
          format: uuid

    SetValueAction:
      type: object
      required: [kind, source]
      properties:
        kind:
          type: string
          enum: [set_value]
        source:
          $ref: '#/components/schemas/ValueSource'

    SetQuantityAction:
      type: object
      required: [kind, target_option_id, source]
      properties:
        kind:
          type: string
          enum: [set_quantity]
        target_option_id:
          type: string
          format: uuid
        source:
          $ref: '#/components/schemas/ValueSource'

    ValueSource:
      oneOf:
        - $ref: '#/components/schemas/DirectValueSource'
        - $ref: '#/components/schemas/FieldValueSource'
        - $ref: '#/components/schemas/CalculationValueSource'
        - $ref: '#/components/schemas/VariableValueSource'
        - $ref: '#/components/schemas/SavedCalculationValueSource'
      discriminator:
        propertyName: kind
        mapping:
          direct: '#/components/schemas/DirectValueSource'
          field: '#/components/schemas/FieldValueSource'
          calculation: '#/components/schemas/CalculationValueSource'
          variable: '#/components/schemas/VariableValueSource'
          saved_calculation: '#/components/schemas/SavedCalculationValueSource'

    DirectValueSource:
      type: object
      required: [kind, value]
      properties:
        kind:
          type: string
          enum: [direct]
        value:
          # Note: oneOf [number, string] is not well-supported by all OpenAPI generators.
          # If your generator struggles, split into DirectNumberValueSource / DirectStringValueSource,
          # or use type: string with a numeric format pattern.
          oneOf:
            - type: number
            - type: string

    FieldValueSource:
      type: object
      required: [kind, field_id]
      properties:
        kind:
          type: string
          enum: [field]
        field_id:
          type: string
          format: uuid

    CalculationValueSource:
      type: object
      required: [kind, steps]
      properties:
        kind:
          type: string
          enum: [calculation]
        steps:
          type: array
          items:
            $ref: '#/components/schemas/CalculationStep'

    VariableValueSource:
      type: object
      required: [kind, variable_id]
      properties:
        kind:
          type: string
          enum: [variable]
        variable_id:
          type: string

    SavedCalculationValueSource:
      type: object
      required: [kind, saved_calculation_id, mappings]
      properties:
        kind:
          type: string
          enum: [saved_calculation]
        saved_calculation_id:
          type: string
          format: uuid
        mappings:
          type: array
          items:
            $ref: '#/components/schemas/SavedCalculationMapping'

    SavedCalculationMapping:
      type: object
      required: [placeholder_id, source, value]
      properties:
        placeholder_id:
          type: string
        source:
          type: string
          enum: [field, direct, variable]
        value:
          type: string
```

### 9.2 Updated Constraint Schema

```yaml
    Constraint:
      type: object
      # Note: conditions and actions are required at the API level (must be arrays),
      # but may be empty ([]). The DB schema allows NULL for backward compatibility
      # during migration; the API layer normalizes NULL to [].
      required: [id, organization_id, source_configurator_id, scope, priority, enabled, conditions, actions]
      properties:
        id:
          type: string
          format: uuid
        organization_id:
          type: string
          format: uuid
        source_configurator_id:
          type: string
          format: uuid
        target_configurator_id:
          type: string
          format: uuid
        scope:
          type: string
          enum: [local, cross]
        priority:
          type: integer
        enabled:
          type: boolean
        name:
          type: string
        note:
          type: string
        source_page_id:
          type: string
          format: uuid
        source_field_ids:
          type: array
          items:
            type: string
            format: uuid
        target_field_id:
          type: string
          format: uuid
        target_form_key:
          type: string
        conditions:
          type: array
          items:
            $ref: '#/components/schemas/ConditionNode'
        actions:
          type: array
          items:
            $ref: '#/components/schemas/Action'
        created_by:
          type: string
        updated_by:
          type: string
        created_at:
          type: string
          format: date-time
        updated_at:
          type: string
          format: date-time
```

---

## 10. AI Agent Interface

### 10.1 Tool Design

AI agent builders get a set of structured tools for constraint creation:

```typescript
// Tool: create_constraint
interface CreateConstraintTool {
  name: "create_constraint";
  parameters: {
    name?: string;
    scope: "local" | "cross";
    source_field_ids: string[];
    target_field_id?: string;
    target_level: "page" | "element" | "option";
    conditions: ConditionNode[];
    actions: Action[];
  };
}
```

### 10.2 Why This Helps AI Agents

| Before (flat format) | After (discriminated union) |
|---------------------|----------------------------|
| "Create an action with type=set_value, valueMode=direct, value=5" | "Create a set_value action with direct source value=5" |
| AI must know which fields are valid for each mode | Each `kind` has exactly its required fields |
| Invalid combinations silently accepted | Backend validation rejects invalid combinations |
| No OpenAPI schema for conditions/actions | Full discriminator schema in OpenAPI |
| Cross-scope uses same fields as local | Explicit `cross_scope_*` kinds signal different behavior |

### 10.3 Example: AI-Generated Constraint

```json
{
  "name": "Show discount when quantity > 10",
  "scope": "local",
  "source_field_ids": ["550e8400-e29b-41d4-a716-446655440000"],
  "conditions": [
    {
      "kind": "group",
      "logic_operator": "and",
      "children": [
        {
          "kind": "number_value",
          "element_id": "quantity-field",
          "operator": "greater_than",
          "value": 10
        }
      ]
    }
  ],
  "actions": [
    {
      "kind": "show"
    },
    {
      "kind": "set_value",
      "source": {
        "kind": "calculation",
        "steps": [
          {
            "kind": "calculation",
            "id": "step-1",
            "operation": "multiply",
            "left": { "kind": "field", "field_id": "550e8400-e29b-41d4-a716-446655440001" },
            "right": { "kind": "number", "value": 0.9 }
          }
        ]
      }
    }
  ]
}
```

---

## 11. Validation Strategy

### 11.1 Go Struct Validation (Primary)

```go
package typed

import "fmt"

func ValidateConditions(nodes []ConditionNode, constraintScope string, targetLevel string) error {
    for i, node := range nodes {
        if err := validateConditionNode(node, constraintScope, targetLevel, 0); err != nil {
            return fmt.Errorf("conditions[%d]: %w", i, err)
        }
    }
    return nil
}

func validateConditionNode(node ConditionNode, scope string, targetLevel string, depth int) error {
    if depth >= 3 {
        return fmt.Errorf("condition nesting exceeds maximum depth of 3 (levels 0,1,2)")
    }
    
    switch node.Kind {
    case "group":
        return validateConditionGroup(node, scope, targetLevel, depth)
    case "number_value", "option_selected", "number_calculation", "number_variable", "option_calculation":
        return validateLocalCondition(node, targetLevel)
    case "cross_scope_number_value", "cross_scope_option_selected", "cross_scope_number_calculation", "cross_scope_number_variable":
        if scope != "cross" {
            return fmt.Errorf("cross-scope condition kind %q not allowed for scope=%q", node.Kind, scope)
        }
        return validateCrossScopeCondition(node)
    default:
        return fmt.Errorf("unknown condition kind: %q", node.Kind)
    }
}

func validateActions(actions []Action, targetLevel string) error {
    validKinds, err := getValidActionKindsForLevel(targetLevel)
    if err != nil {
        return err
    }
    
    validMap := make(map[string]bool, len(validKinds))
    for _, k := range validKinds {
        validMap[k] = true
    }
    
    for i, action := range actions {
        if !validMap[action.Kind] {
            return fmt.Errorf("actions[%d]: kind %q not valid for target level %q", i, action.Kind, targetLevel)
        }
        
        if err := validateAction(action); err != nil {
            return fmt.Errorf("actions[%d]: %w", i, err)
        }
    }
    return nil
}

func getValidActionKindsForLevel(level string) ([]string, error) {
    switch level {
    case "page":
        return []string{"show", "hide", "message"}, nil
    case "option":
        return []string{"set", "unset", "set_quantity", "show", "hide", "disable", "message"}, nil
    case "element":
        return []string{"show", "hide", "required", "not_required", "set_value", "set", "unset", "set_quantity", "message", "disable"}, nil
    default:
        return nil, fmt.Errorf("unknown target level: %q", level)
    }
}
```

### 11.2 PostgreSQL Validation (Safety Net)

Update existing SQL functions to handle new format:

```sql
-- Update is_valid_constraint_condition_node to accept new format
CREATE OR REPLACE FUNCTION public.is_valid_constraint_condition_node(node jsonb)
RETURNS boolean AS $$
BEGIN
  -- New format: check for kind field
  IF node ? 'kind' THEN
    RETURN node->>'kind' IN (
      'group', 'number_value', 'option_selected', 
      'number_calculation', 'number_variable', 'option_calculation',
      'cross_scope_number_value', 'cross_scope_option_selected',
      'cross_scope_number_calculation', 'cross_scope_number_variable',
      'cross_scope_option_calculation'
    );
  END IF;
  
  -- Legacy format fallback
  RETURN node->>'type' IN ('group', 'number_value', 'option_selected');
END;
$$ LANGUAGE plpgsql;
```

### 11.3 Validation Errors for AI

Backend returns structured validation errors:

```json
{
  "error": {
    "code": "validation_error",
    "message": "Invalid constraint",
    "details": {
      "conditions[0].children[1]": "unknown condition kind: 'invalid_kind'",
      "actions[0]": "kind 'set_value' not valid for target level 'page'",
      "actions[1].source": "value source kind 'invalid' not supported"
    }
  }
}
```

---

## 12. Frontend Runtime Changes

### 12.1 Files to Update

| File | Change |
|------|--------|
| `types/constraint.types.ts` | Refactor to use discriminated unions; remove flat types |
| `types/conditionGroup.types.ts` | Update `SerializedConditionGroup` to use new `kind` field |
| `lib/conditionGroupEvaluator.ts` | Branch on `node.kind` instead of `node.type` |
| `lib/constraintEvaluator.ts` | Update to accept typed conditions |
| `utils/constraintActionProcessor.ts` | Branch on `action.kind` and `action.source.kind` |
| `utils/elementTraversal.ts` | Update `RuntimeConstraint` to use typed arrays |
| `utils/constraintDrafts.ts` | Update draft builders to construct discriminated unions |
| `hooks/useConstraintActions.ts` | Pass typed constraints through |
| `hooks/useFormPreviewData.ts` | Update constraint fetching |
| `hooks/useConfiguratorData.ts` | Update constraint fetching |
| `components/constraint-editor/*.tsx` | Update form builder constraint UI |
| `components/constraint-modals/*.tsx` | Update constraint creation/modal UIs |
| `components/condition-builder/*.tsx` | Update condition builder components |

### 12.2 Migration Path

Since backend supports dual-format read:
1. **Phase 1:** Backend deployed with dual-format support (reads old+new, writes new)
2. **Phase 2:** SQL migration transforms all existing constraints to new format
3. **Phase 3:** Frontend refactored to use discriminated union types
4. **Phase 4:** Remove legacy format read support from backend (once all clients updated)

---

## 13. Rollout Plan

### Phase 1: Backend Types (1-2 days)
- Create `internal/domain/constraints/typed/` package
- Add `ConditionNode`, `Action`, `ValueSource` structs
- Implement dual-format JSON marshal/unmarshal
- Add validation functions
- Write unit tests for marshal/unmarshal round-trips

### Phase 2: Backend Integration (2-3 days)
- Update `Constraint` struct to use typed arrays
- Update handlers to use typed request DTOs
- Add validation to Create/Update handlers
- Update repository layer
- Run `TestNewRouter_NoRouteConflicts`
- Write integration tests

### Phase 3: OpenAPI (1 day)
- Add all new schema components
- Update Constraint schema
- Validate with OpenAPI linter

### Phase 4: SQL Migration (1-2 days)
- Write migration script
- Test on staging database copy
- Verify idempotency
- Add rollback script

### Phase 5: Frontend Types (1-2 days)
- Add `constraint-typed.types.ts`
- Update `constraint.types.ts` to re-export
- Add type guards

### Phase 6: Frontend Runtime (3-5 days)
- Update evaluators (conditionGroupEvaluator, constraintActionProcessor)
- Update constraint draft builders
- Update form builder UI components
- Update tests

### Phase 7: Cleanup (1 day)
- Remove legacy format read support from backend
- Remove `CalculationStepLegacy`, `fromLegacy()`, `toLegacy()` from frontend (if still present)
- Remove deprecated SQL validation functions

**Total estimated effort:** 3-4 weeks (includes testing, staging validation, and incremental rollout)

---

## 14. Comparison: Before vs After

### 14.1 AI Agent Prompt

**Before:**
```
Create a constraint that shows a field when:
1. Field "quantity" is greater than 10
2. Option "premium" is selected

Use this JSON structure:
{
  "conditions": [
    {
      "type": "group",
      "logicOperator": "and",
      "children": [
        {
          "type": "number_value",
          "elementId": "quantity",
          "operator": "greater_than",
          "value": 10,
          "calculationSteps": [],
          "comparisonCalculationSteps": []
        },
        {
          "type": "option_selected",
          "elementId": "package",
          "optionIds": ["premium"]
        }
      ]
    }
  ],
  "actions": [
    {
      "type": "show"
    }
  ]
}
```

**After:**
```
Create a constraint that shows a field when:
1. Field "quantity" is greater than 10
2. Option "premium" is selected

Use this JSON structure:
{
  "conditions": [
    {
      "kind": "group",
      "logic_operator": "and",
      "children": [
        {
          "kind": "number_value",
          "element_id": "quantity",
          "operator": "greater_than",
          "value": 10
        },
        {
          "kind": "option_selected",
          "element_id": "package",
          "option_ids": ["premium"]
        }
      ]
    }
  ],
  "actions": [
    { "kind": "show" }
  ]
}
```

**Key improvement:** AI doesn't need to know about `calculationSteps`, `comparisonCalculationSteps`, `valueMode`, or other optional fields that aren't relevant to this constraint.

### 14.2 Validation Example

**Before:**
```json
{
  "actions": [
    {
      "type": "set_value",
      "value": 10,
      "valueMode": "calculation",
      "calculationSteps": []
    }
  ]
}
```
- Backend accepts this (valueMode says calculation but calculationSteps is empty)
- Runtime behavior undefined

**After:**
```json
{
  "actions": [
    {
      "kind": "set_value",
      "source": {
        "kind": "calculation",
        "steps": []
      }
    }
  ]
}
```
- Backend validation: `"actions[0].source.steps: must contain at least one calculation step"`
- AI gets clear error message

---

## 15. Open Questions

1. **Should we keep the `FlatConditionGroup` type?** The form builder currently uses flat conditions before converting to nested groups. Do we maintain a separate flat type for the UI, or does the UI directly build the discriminated union tree?

2. **Action `message` severity:** Currently not explicitly stored. Should we add `severity` to message actions, or default to `"info"`?

3. **Should `number_value` support string comparisons?** Currently `value` is `number | string` in some places. Should we split into `number_value` (number) and `string_value` (string) kinds?

4. **How to handle `source_page_id` vs conditions referencing pages?** Currently `source_page_id` is metadata, but conditions reference elements by ID. Should page-level constraints have a `page_id` field in conditions?

5. **Should we add `kind: "always"` for conditions that are always true?** This would replace empty condition arrays.

6. **Cross-scope field validation:** When a constraint references a field in another configurator, how does the backend validate that the field exists and is accessible? Does this require a new service call or can it be deferred to runtime?

7. **Migration of embedded constraints:** Some configurators may still have embedded constraints in `configuration_data`. The SQL migration only handles the `constraints` table. Do we need a second migration for embedded constraints?

8. **Performance impact:** Typed structs with custom JSON unmarshaling are slightly slower than `any` passthrough. Is this acceptable for the constraint endpoints (which typically return < 100 constraints)?

---

## 16. Appendix: Decision Log

| Date | Decision | Context |
|------|----------|---------|
| 2026-05-15 | All scopes, reusable types | User wants consistent pattern across element/page/option |
| 2026-05-15 | Dual-format compatibility | Same proven approach as calculation migration |
| 2026-05-15 | Keep recursive groups | Complex rules need nesting; best AI compromise |
| 2026-05-15 | Nested discriminated union for value sources | Extensible without action kind explosion |
| 2026-05-15 | Explicit cross-scope condition kinds | Clear to AI; enables backend validation |
| 2026-05-15 | Go struct validation (primary) | Backend is source of truth |
| 2026-05-15 | Full OpenAPI schema | AI agents consume schema programmatically |
| 2026-05-15 | SQL data migration | One-time transform of all existing constraints |
| 2026-05-15 | Flat ConditionNode struct with Kind discriminator | Same proven pattern as CalculationStep; avoids interface complexity |
| 2026-05-15 | ValueSource.Validate() method | Prevents invalid field combinations per kind |
| 2026-05-15 | Realistic 3-4 week timeline | Includes testing, staging validation, incremental rollout |

---

## 17. Related Documents

- [Backend Calculation Migration](./backend-calculation-migration.md)
- [Staging Test Plan](./staging-testplan.md)
- Backend: `internal/domain/calculations/types.go`
- Backend: `internal/domain/calculations/json.go`
- Backend: `internal/domain/constraints/service.go`
- Frontend: `src/features/configurators/types/calculation.types.ts`
- Frontend: `src/features/configurators/types/constraint.types.ts`
- Frontend: `src/features/configurators/lib/conditionGroupEvaluator.ts`
- Frontend: `src/features/configurators/utils/constraintActionProcessor.ts`
