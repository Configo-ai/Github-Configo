# RFC: Configuration Data Discriminated Union Refactor

**Status:** Exploratory / Research  
**Scope:** Configurator form elements (`configuration_data.pages[].elements[]`)  
**Author:** AI Agent  
**Related:** [Constraint Discriminated Union RFC](./constraint-discriminated-union-rfc.md), [Quote Builder Discriminated Union RFC](./quote-builder-discriminated-union-rfc.md)

---

## 1. Executive Summary

This RFC proposes refactoring configurator **form elements** from a flat interface with 25+ optional fields to a **discriminated union** with explicit `kind` fields. Currently, `Element` stores all possible fields as optional, making it impossible for AI agents to know which combinations are valid per element type.

The refactor is **significantly larger** than constraints or quote builder blocks — it touches 3 frontends, backend, edge functions, PDF generation, and the AI worker. To manage this, the work is broken into **8 incremental phases** that can be shipped independently.

**Key insight:** Making elements less flat makes adding new element types trivial. Instead of adding optional fields to a shared interface (polluting all types), you add a new interface with exactly the fields it needs.

---

## 2. Problem Statement

### 2.1 Current Flat Format

```typescript
interface Element {
  id: string;
  type: FieldType;  // "text" | "number" | "select" | "section" | ...
  label: string;
  fieldState: FieldState;
  
  // ALL of these are optional on EVERY element type:
  placeholder?: string;
  description?: string;
  defaultValue?: string | number;
  options?: Option[];        // only for select/radio/checkbox/multiselect
  min?: number;              // only for number/range
  max?: number;              // only for number/range
  step?: number;             // only for number/range
  columns?: Element[][];     // only for section
  sectionLayout?: SectionLayout; // only for section
  acceptedTypes?: string[];  // only for file
  maxFiles?: number;         // only for file
  outputMapping?: Record<string, string>; // only for model3d
  showTotalPrice?: boolean;  // only for number
  allowQuantity?: boolean;   // only for checkbox/radio
  imageUrl?: string;         // only for image
  price?: number;            // only for price
  sku?: string;              // only for product-linked
  productId?: string;        // only for product-linked
  defaultSelectedOption?: string; // only for select/radio
  span?: number;             // layout
  disableStacking?: boolean; // layout
  hidden?: boolean;
  required?: boolean;
}
```

**AI Agent Pain Points:**
- **25+ optional fields:** AI must know which subset applies to each `type`
- **No compile-time safety:** TypeScript allows `min` on a `text` field
- **Hard to document:** Cannot generate per-type OpenAPI schemas from a flat interface
- **Adding types is painful:** New element type = new optional fields on ALL elements
- **Validation scattered:** Runtime checks in form builder, constraint evaluator, quote builder, PDF generator

### 2.2 Adding a New Element Type Today

To add an `ai_prompt` element type:

1. Add `"ai_prompt"` to `FieldType` union
2. Add optional fields to `Element` interface:
   - `promptTemplate?: string` — only for ai_prompt
   - `outputFormat?: string` — only for ai_prompt
   - `maxTokens?: number` — only for ai_prompt
3. Now ALL elements have these fields (TypeScript allows them)
4. Update validation in form builder, runtime, quote builder, PDF generator, edge functions
5. Hope no other code accidentally sets these fields on unrelated types

**With discriminated union:**

1. Add `"ai_prompt"` to `ElementKind` union
2. Add `AiPromptElement` interface with exactly its fields
3. Done — no pollution of other element types

---

## 3. Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Field naming** | `kind` (not `type`) | Aligns with constraint/calculation/quote-builder pattern |
| **Common fields** | Extract shared `ElementBase` interface | ID, label, fieldState, hidden, required are universal |
| **Type-specific data** | Typed fields per kind | Each element has exactly the fields it needs |
| **Nested elements** | `SectionElement.columns: Element[][]` | Same recursive pattern as blocks/constraints |
| **Backward compatibility** | Dual-format (read old+new, write new only) | Same proven approach |
| **Migration strategy** | Incremental: new configs use new format, old configs migrate on edit | Too much data to migrate at once |
| **OpenAPI** | Full schema with discriminator | AI agents consume schema programmatically |
| **Timeline** | 8 phases, ~8-10 weeks | Large blast radius requires careful incremental rollout |

---

## 4. Target Architecture

### 4.1 Element Discriminated Union

```typescript
// TypeScript (frontend + backend API contract)

interface ElementBase {
  id: string;
  label: string;
  fieldState: FieldState;  // "standard" | "required" | "disabled"
  hidden?: boolean;
  required?: boolean;
  description?: string;
  span?: number;
  disableStacking?: boolean;
}

// ─── Input Elements ───

interface TextElement extends ElementBase {
  kind: "text";
  placeholder?: string;
  defaultValue?: string;
}

interface NumberElement extends ElementBase {
  kind: "number";
  placeholder?: string;
  defaultValue?: number;
  min?: number;
  max?: number;
  step?: number;
  showTotalPrice?: boolean;
}

interface RangeElement extends ElementBase {
  kind: "range";
  defaultValue?: number;
  min?: number;
  max?: number;
  step?: number;
}

// ─── Selection Elements ───

interface SelectElement extends ElementBase {
  kind: "select";
  placeholder?: string;
  defaultSelectedOption?: string;
  options: Option[];
}

interface RadioElement extends ElementBase {
  kind: "radio";
  defaultSelectedOption?: string;
  options: Option[];
  allowQuantity?: boolean;
}

interface CheckboxElement extends ElementBase {
  kind: "checkbox";
  defaultSelectedOption?: string;
  options: Option[];
  allowQuantity?: boolean;
}

interface MultiselectElement extends ElementBase {
  kind: "multiselect";
  placeholder?: string;
  defaultSelectedOption?: string;
  options: Option[];
}

// ─── Media Elements ───

interface ImageElement extends ElementBase {
  kind: "image";
  imageUrl?: string;
}

interface FileElement extends ElementBase {
  kind: "file";
  acceptedTypes?: string[];
  maxFiles?: number;
}

interface Model3dElement extends ElementBase {
  kind: "model3d";
  outputMapping?: Record<string, string>;
}

interface PdfAnnotationElement extends ElementBase {
  kind: "pdf_annotation";
}

// ─── Container Elements ───

interface SectionElement extends ElementBase {
  kind: "section";
  sectionLayout: SectionLayout;  // "1" | "2" | "2x1" | "1x2" | "3" | "4"
  columns: Element[][];  // nested elements per column
}

// ─── Pricing Elements ───

interface PriceElement extends ElementBase {
  kind: "price";
  price?: number;
  sku?: string;
  productId?: string;
  costPrice?: number;
}

// ─── Union ───

type Element =
  | TextElement
  | NumberElement
  | RangeElement
  | SelectElement
  | RadioElement
  | CheckboxElement
  | MultiselectElement
  | ImageElement
  | FileElement
  | Model3dElement
  | PdfAnnotationElement
  | SectionElement
  | PriceElement;
```

### 4.2 Go Backend Types

```go
package elements

// ElementBase holds fields common to all element kinds.
type ElementBase struct {
    ID              string     `json:"id"`
    Label           string     `json:"label"`
    FieldState      string     `json:"field_state"` // "standard", "required", "disabled"
    Hidden          *bool      `json:"hidden,omitempty"`
    Required        *bool      `json:"required,omitempty"`
    Description     *string    `json:"description,omitempty"`
    Span            *int       `json:"span,omitempty"`
    DisableStacking *bool      `json:"disable_stacking,omitempty"`
}

// Element is a discriminated union for all form element kinds.
type Element struct {
    Kind string `json:"kind"`
    ElementBase

    // Input elements
    Placeholder     *string `json:"placeholder,omitempty"`
    DefaultValue    interface{} `json:"default_value,omitempty"` // string | number
    Min             *float64 `json:"min,omitempty"`
    Max             *float64 `json:"max,omitempty"`
    Step            *float64 `json:"step,omitempty"`
    ShowTotalPrice  *bool    `json:"show_total_price,omitempty"`

    // Selection elements
    DefaultSelectedOption *string  `json:"default_selected_option,omitempty"`
    Options               []Option `json:"options,omitempty"`
    AllowQuantity         *bool    `json:"allow_quantity,omitempty"`

    // Media elements
    ImageURL      *string            `json:"image_url,omitempty"`
    AcceptedTypes []string           `json:"accepted_types,omitempty"`
    MaxFiles      *int               `json:"max_files,omitempty"`
    OutputMapping map[string]string  `json:"output_mapping,omitempty"`

    // Container elements
    SectionLayout *string    `json:"section_layout,omitempty"`
    Columns       [][]Element `json:"columns,omitempty"`

    // Pricing elements
    Price     *float64 `json:"price,omitempty"`
    SKU       *string  `json:"sku,omitempty"`
    ProductID *string  `json:"product_id,omitempty"`
    CostPrice *float64 `json:"cost_price,omitempty"`
}

// Option represents a selectable choice.
type Option struct {
    ID              string  `json:"id"`
    SKU             string  `json:"sku"`
    ProductName     string  `json:"product_name"`
    Label           *string `json:"label,omitempty"`
    Price           *float64 `json:"price,omitempty"`
    CostPrice       *float64 `json:"cost_price,omitempty"`
    PhotoURL        *string `json:"photo_url,omitempty"`
    ImageURL        *string `json:"image_url,omitempty"`
    Description     *string `json:"description,omitempty"`
    MinQuantity     *int    `json:"min_quantity,omitempty"`
    MaxQuantity     *int    `json:"max_quantity,omitempty"`
    AllowQuantity   *bool   `json:"allow_quantity,omitempty"`
    Hidden          *bool   `json:"hidden,omitempty"`
    DefaultHidden   *bool   `json:"default_hidden,omitempty"`
    ProductID       *string `json:"product_id,omitempty"`
    IsProductLinked *bool   `json:"is_product_linked,omitempty"`
    PDFFiles        []PdfFile `json:"pdf_files,omitempty"`
    Model3DURL      *string `json:"model3d_url,omitempty"`
    IsOptionalItem  *bool   `json:"is_optional_item,omitempty"`
}
```

**Note:** Go uses a flat struct with `omitempty` tags (same pattern as `CalculationStep` and `ConditionNode`). The `kind` field determines which other fields are relevant. This avoids interface complexity while maintaining a clean JSON contract.

---

## 5. Page & Configuration Data

```typescript
interface Page {
  id: string;
  name: string;
  description?: string;
  elements: Element[];  // ← now typed discriminated union
  hidden?: boolean;
  columnLayout?: 1 | 2;
}

interface ConfigurationData {
  pages: Page[];
  // Future: version, metadata, etc.
}
```

---

## 6. Dual-Format Compatibility

### 6.1 Read Path (Backend)

```go
func UnmarshalConfigurationData(data []byte) (*ConfigurationData, error) {
    // 1. Try new format (look for "kind" field on first element)
    var cfg ConfigurationData
    if err := json.Unmarshal(data, &cfg); err == nil && hasKind(cfg) {
        return &cfg, nil
    }

    // 2. Detect legacy format: { pages: [{ elements: [{ type: "text", ... }] }] }
    // 3. Convert legacy → new format:
    //    - type: "text" → kind: "text"
    //    - camelCase → snake_case
    //    - Lift type-specific fields (same pattern as quote builder blocks)
    // 4. Return always in new format
}

func hasKind(cfg ConfigurationData) bool {
    if len(cfg.Pages) == 0 || len(cfg.Pages[0].Elements) == 0 {
        return true // empty config = any format
    }
    return cfg.Pages[0].Elements[0].Kind != ""
}
```

### 6.2 Write Path

```go
func MarshalConfigurationData(cfg *ConfigurationData) ([]byte, error) {
    // Always output new discriminated union format
    return json.Marshal(cfg)
}
```

### 6.3 Legacy → New Field Mapping

| Legacy Path | New Path |
|------------|----------|
| `pages[].elements[].type` | `pages[].elements[].kind` |
| `pages[].elements[].fieldState` | `pages[].elements[].field_state` |
| `pages[].elements[].defaultValue` | `pages[].elements[].default_value` |
| `pages[].elements[].defaultSelectedOption` | `pages[].elements[].default_selected_option` |
| `pages[].elements[].showTotalPrice` | `pages[].elements[].show_total_price` |
| `pages[].elements[].sectionLayout` | `pages[].elements[].section_layout` |
| `pages[].elements[].imageUrl` | `pages[].elements[].image_url` |
| `pages[].elements[].acceptedTypes` | `pages[].elements[].accepted_types` |
| `pages[].elements[].maxFiles` | `pages[].elements[].max_files` |
| `pages[].elements[].outputMapping` | `pages[].elements[].output_mapping` |
| `pages[].elements[].productId` | `pages[].elements[].product_id` |
| `pages[].elements[].costPrice` | `pages[].elements[].cost_price` |
| `pages[].elements[].disableStacking` | `pages[].elements[].disable_stacking` |
| `pages[].elements[].options[].productName` | `pages[].elements[].options[].product_name` |
| `pages[].elements[].options[].photoUrl` | `pages[].elements[].options[].photo_url` |
| `pages[].elements[].options[].imageUrl` | `pages[].elements[].options[].image_url` |
| `pages[].elements[].options[].minQuantity` | `pages[].elements[].options[].min_quantity` |
| `pages[].elements[].options[].maxQuantity` | `pages[].elements[].options[].max_quantity` |
| `pages[].elements[].options[].allowQuantity` | `pages[].elements[].options[].allow_quantity` |
| `pages[].elements[].options[].defaultHidden` | `pages[].elements[].options[].default_hidden` |
| `pages[].elements[].options[].isProductLinked` | `pages[].elements[].options[].is_product_linked` |
| `pages[].elements[].options[].pdfFiles` | `pages[].elements[].options[].pdf_files` |
| `pages[].elements[].options[].model3dUrl` | `pages[].elements[].options[].model3d_url` |
| `pages[].elements[].options[].isOptionalItem` | `pages[].elements[].options[].is_optional_item` |
| `pages[].columnLayout` | `pages[].column_layout` |

---

## 7. Eight-Phase Rollout Plan

### Phase 1: Type Definitions & Conversion Layer (Week 1)
**Goal:** Define types and conversion functions without changing runtime behavior.

**Backend:**
- Create `internal/domain/configurators/elements/` package
- Add `Element`, `ElementBase`, `Option`, `Page`, `ConfigurationData` structs
- Implement `UnmarshalConfigurationData()` and `MarshalConfigurationData()` with dual-format support
- Write comprehensive round-trip tests (legacy → new → JSON)

**Frontend:**
- Add `features/configurators/types/element-typed.types.ts`
- Define discriminated union for all element kinds
- Add `fromLegacyElement()` and `toLegacyElement()` conversion functions
- Add type guards: `isTextElement()`, `isSectionElement()`, etc.
- Write unit tests for conversions

**Files:**
- `internal/domain/configurators/elements/types.go` (new)
- `internal/domain/configurators/elements/json.go` (new)
- `internal/domain/configurators/elements/json_test.go` (new)
- `src/features/configurators/types/element-typed.types.ts` (new)
- `src/features/configurators/utils/elementConverters.ts` (new)
- `src/features/configurators/utils/elementConverters.test.ts` (new)

**Deliverable:** Types and converters ready, not yet used in production code.

---

### Phase 2: Backend API Dual-Format Support (Week 2)
**Goal:** Backend reads both formats, writes new format. No frontend changes yet.

**Backend:**
- Update `Configurator` struct: `ConfigurationData` field uses typed `ConfigurationData`
- Update `GET /v1/configurators/{id}/config` — returns new format
- Update `PUT /v1/configurators/{id}/config` — accepts both formats, validates, stores new format
- Update `PATCH /v1/configurators/{id}/configuration-data` — same dual-format logic
- Add validation: `ValidateConfigurationData()` checks element kinds, required fields per kind
- Update repository layer to use typed structs

**Key decision:** The DB still stores JSONB. The migration is application-layer only (same as calculations).

**Files:**
- `internal/domain/configurators/service.go`
- `internal/transport/http/handlers/configurators.go`
- `internal/data/repositories/configurators.go`

**Deliverable:** Backend API serves and accepts new format. Frontend still receives old format (but backend is ready).

---

### Phase 3: Form Builder — Type Integration (Week 3-4)
**Goal:** Form builder uses discriminated union internally. Wrap in feature flag.

**Frontend:**
- Add feature flag: `dev-typed-elements`
- Update `useFormBuilderViewModel` to convert legacy → typed on load, typed → legacy on save
- Update element rendering in form builder canvas: switch on `element.kind`
- Update element property panels:
  - `TextElementProperties` — only text fields
  - `NumberElementProperties` — only number fields
  - `SelectElementProperties` — only select fields
  - etc.
- Update drag-and-drop to maintain typed elements
- Update element creation (add new element) to construct correct typed element

**Files:**
- `src/features/configurators/hooks/useFormBuilderViewModel.ts`
- `src/features/configurators/components/form-builder/FormBuilderCanvas.tsx`
- `src/features/configurators/components/form-builder/element-properties/*.tsx` (new per-type panels)
- `src/features/configurators/components/form-builder/ElementPalette.tsx`

**Deliverable:** Form builder uses typed elements internally. Feature flag controls rollout.

---

### Phase 4: Runtime & Constraint Evaluation (Week 4-5)
**Goal:** Runtime form preview and constraint evaluator work with typed elements.

**Frontend:**
- Update `RuntimePage` / `RuntimeElement` to use typed discriminated union
- Update constraint evaluator to branch on `element.kind`:
  ```typescript
  switch (element.kind) {
    case "select":
    case "radio":
    case "checkbox":
    case "multiselect":
      // Evaluate option-based conditions
      return evaluateOptionCondition(element, condition);
    case "number":
    case "range":
      // Evaluate numeric conditions
      return evaluateNumberCondition(element, condition);
    // ... etc
  }
  ```
- Update `useFormPreviewData` to pass typed elements to evaluators
- Update `useConstraintActions` to work with typed elements

**Backend (edge function):**
- Update `generate-pdf` edge function to accept new format
- Update element rendering in PDF to branch on `kind`

**Files:**
- `src/features/configurators/lib/conditionGroupEvaluator.ts`
- `src/features/configurators/lib/constraintEvaluator.ts`
- `src/features/configurators/utils/constraintActionProcessor.ts`
- `src/features/configurators/hooks/useFormPreviewData.ts`
- `src/features/configurators/hooks/useConstraintActions.ts`
- `supabase/functions/generate-pdf/index.ts`

**Deliverable:** Runtime evaluation works with typed elements. Feature flag still controls form builder.

---

### Phase 5: Quote Builder Integration (Week 5-6)
**Goal:** Quote builder consumes typed elements from configuration data.

**Frontend:**
- Update `QuoteBuilderElement` to use typed discriminated union
- Update `getConfigurationPages()` to return typed elements
- Update `quoteBuilder.service.ts` sync functions (syncLabels, syncImages) to branch on `element.kind`
- Update `configurationParser.ts` to parse typed elements
- Update `configurationHelpers.ts` to work with typed elements

**Files:**
- `src/features/quotations/types.ts`
- `src/features/quotations/services/quoteBuilder.service.ts`
- `src/features/quotations/lib/configurationParser.ts`
- `src/features/quotations/lib/configurationHelpers.ts`

**Deliverable:** Quote builder works with typed elements.

---

### Phase 6: PDF Payload Builder (Week 6)
**Goal:** PDF generation consumes typed elements.

**Frontend:**
- Update `pdfPayloadBuilder.ts` to branch on `element.kind`
- Update `PdfElement` interface to be discriminated union (optional — can keep flat for PDF payload)
- Update element flattening logic in `configurationHelpers.ts`

**Backend (edge function):**
- Update PDF template rendering to handle new element format

**Files:**
- `src/features/quotations/utils/pdfPayloadBuilder.ts`
- `supabase/functions/generate-pdf/pdf-renderer.ts` (or equivalent)

**Deliverable:** PDF generation works with typed elements.

---

### Phase 7: Import Configurator Edge Function (Week 6-7)
**Goal:** Import/export configurator handles new format.

**Backend:**
- Update `supabase/functions/import-configurator/tools.ts`
- Update JSON Schema for element types from flat to discriminated union
- Update import validation to check `kind` field
- Update export to output new format

**Files:**
- `supabase/functions/import-configurator/tools.ts`
- `supabase/functions/import-configurator/element-schema.ts` (new)

**Deliverable:** Import/export supports new format.

---

### Phase 8: Migration & Cleanup (Week 7-8)
**Goal:** Migrate existing configs, remove legacy support, enable feature flag globally.

**Database Migration:**
- SQL script transforms `configuration_data` JSON from flat to discriminated union
- **Challenge:** `configuration_data` is nested JSONB inside `configurators` table
- **Approach:** Application-layer migration — backend converts on read, writes new format on save
- **Lazy migration:** Existing configs convert when opened + saved in form builder
- **Batch migration:** Optional SQL script for bulk conversion (risky due to nested structure)

**Frontend:**
- Remove feature flag `dev-typed-elements`
- Remove `fromLegacyElement()` / `toLegacyElement()` conversion functions
- Remove legacy `Element` interface (keep as `ElementLegacy` briefly, then delete)

**Backend:**
- Remove legacy format read support from `UnmarshalConfigurationData()`
- Update OpenAPI spec to only document new format
- Remove deprecated SQL validation functions (if any)

**Files:**
- `supabase/migrations/YYYYMMDD_migrate_configuration_data_to_discriminated_union.sql` (optional)
- Cleanup across all files from Phases 1-7

**Deliverable:** All configs use new format. Legacy code removed.

---

## 8. Adding a New Element Type (After Refactor)

### Before (Flat)

1. Add `"ai_prompt"` to `FieldType` union
2. Add 3 optional fields to `Element` interface
3. Update ALL element handling code (form builder, runtime, quote builder, PDF, import)
4. Add validation: "if type === 'ai_prompt', require promptTemplate"

### After (Discriminated Union)

1. Add `"ai_prompt"` to `ElementKind` union
2. Add interface:
   ```typescript
   interface AiPromptElement extends ElementBase {
     kind: "ai_prompt";
     promptTemplate: string;
     outputFormat?: string;
     maxTokens?: number;
   }
   ```
3. Add to `Element` union
4. Add component: `AiPromptElementProperties.tsx`
5. Add runtime handler in constraint evaluator (if needed)
6. Add quote builder handler (if needed)
7. Add PDF renderer (if needed)

**Key difference:** Steps 3-7 are isolated to the new type. No existing code needs changes.

---

## 9. Validation Strategy

### Backend Validation

```go
func ValidateElement(element Element) error {
    switch element.Kind {
    case "text":
        // text has no required fields beyond base
    case "number":
        if element.Min != nil && element.Max != nil && *element.Min > *element.Max {
            return fmt.Errorf("number element: min cannot be greater than max")
        }
    case "select", "radio", "checkbox", "multiselect":
        if len(element.Options) == 0 {
            return fmt.Errorf("%s element requires at least one option", element.Kind)
        }
    case "section":
        if element.SectionLayout == nil {
            return fmt.Errorf("section element requires section_layout")
        }
        for ci, col := range element.Columns {
            for ri, nested := range col {
                if err := ValidateElement(nested); err != nil {
                    return fmt.Errorf("section.columns[%d][%d]: %w", ci, ri, err)
                }
            }
        }
    case "file":
        if element.MaxFiles != nil && *element.MaxFiles < 1 {
            return fmt.Errorf("file element: max_files must be at least 1")
        }
    default:
        return fmt.Errorf("unknown element kind: %q", element.Kind)
    }
    return nil
}
```

### Frontend Type Guards

```typescript
export function isTextElement(element: Element): element is TextElement {
  return element.kind === "text";
}

export function isSectionElement(element: Element): element is SectionElement {
  return element.kind === "section";
}

export function isSelectionElement(element: Element): element is SelectElement | RadioElement | CheckboxElement | MultiselectElement {
  return ["select", "radio", "checkbox", "multiselect"].includes(element.kind);
}

export function hasOptions(element: Element): element is SelectElement | RadioElement | CheckboxElement | MultiselectElement {
  return isSelectionElement(element);
}
```

---

## 10. OpenAPI Schema (Partial)

```yaml
components:
  schemas:
    Element:
      oneOf:
        - $ref: '#/components/schemas/TextElement'
        - $ref: '#/components/schemas/NumberElement'
        - $ref: '#/components/schemas/RangeElement'
        - $ref: '#/components/schemas/SelectElement'
        - $ref: '#/components/schemas/RadioElement'
        - $ref: '#/components/schemas/CheckboxElement'
        - $ref: '#/components/schemas/MultiselectElement'
        - $ref: '#/components/schemas/ImageElement'
        - $ref: '#/components/schemas/FileElement'
        - $ref: '#/components/schemas/Model3dElement'
        - $ref: '#/components/schemas/PdfAnnotationElement'
        - $ref: '#/components/schemas/SectionElement'
        - $ref: '#/components/schemas/PriceElement'
      discriminator:
        propertyName: kind
        mapping:
          text: '#/components/schemas/TextElement'
          number: '#/components/schemas/NumberElement'
          range: '#/components/schemas/RangeElement'
          select: '#/components/schemas/SelectElement'
          radio: '#/components/schemas/RadioElement'
          checkbox: '#/components/schemas/CheckboxElement'
          multiselect: '#/components/schemas/MultiselectElement'
          image: '#/components/schemas/ImageElement'
          file: '#/components/schemas/FileElement'
          model3d: '#/components/schemas/Model3dElement'
          pdf_annotation: '#/components/schemas/PdfAnnotationElement'
          section: '#/components/schemas/SectionElement'
          price: '#/components/schemas/PriceElement'

    ElementBase:
      type: object
      required: [id, label, field_state]
      properties:
        id:
          type: string
        label:
          type: string
        field_state:
          type: string
          enum: [standard, required, disabled]
        hidden:
          type: boolean
        required:
          type: boolean
        description:
          type: string
        span:
          type: integer
        disable_stacking:
          type: boolean

    TextElement:
      allOf:
        - $ref: '#/components/schemas/ElementBase'
        - type: object
          required: [kind]
          properties:
            kind:
              type: string
              enum: [text]
            placeholder:
              type: string
            default_value:
              type: string

    NumberElement:
      allOf:
        - $ref: '#/components/schemas/ElementBase'
        - type: object
          required: [kind]
          properties:
            kind:
              type: string
              enum: [number]
            placeholder:
              type: string
            default_value:
              type: number
            min:
              type: number
            max:
              type: number
            step:
              type: number
            show_total_price:
              type: boolean

    SelectElement:
      allOf:
        - $ref: '#/components/schemas/ElementBase'
        - type: object
          required: [kind, options]
          properties:
            kind:
              type: string
              enum: [select]
            placeholder:
              type: string
            default_selected_option:
              type: string
            options:
              type: array
              items:
                $ref: '#/components/schemas/Option'

    SectionElement:
      allOf:
        - $ref: '#/components/schemas/ElementBase'
        - type: object
          required: [kind, section_layout, columns]
          properties:
            kind:
              type: string
              enum: [section]
            section_layout:
              type: string
              enum: ["1", "2", "2x1", "1x2", "3", "4"]
            columns:
              type: array
              items:
                type: array
                items:
                  $ref: '#/components/schemas/Element'

    Option:
      type: object
      required: [id, sku, product_name]
      properties:
        id:
          type: string
        sku:
          type: string
        product_name:
          type: string
        label:
          type: string
        price:
          type: number
        cost_price:
          type: number
        photo_url:
          type: string
        image_url:
          type: string
        description:
          type: string
        min_quantity:
          type: integer
        max_quantity:
          type: integer
        allow_quantity:
          type: boolean
        hidden:
          type: boolean
        default_hidden:
          type: boolean
        product_id:
          type: string
        is_product_linked:
          type: boolean
        pdf_files:
          type: array
          items:
            $ref: '#/components/schemas/PdfFile'
        model3d_url:
          type: string
        is_optional_item:
          type: boolean
```

---

## 11. AI Agent Interface

### Tool Design

```typescript
// Tool: create_element
interface CreateElementTool {
  name: "create_element";
  parameters: {
    kind: "text" | "number" | "select" | "radio" | "checkbox" | "multiselect" | "range" | "image" | "file" | "model3d" | "pdf_annotation" | "section" | "price";
    label: string;
    // kind-specific fields
    placeholder?: string;
    default_value?: string | number;
    min?: number;
    max?: number;
    step?: number;
    options?: Array<{ id: string; sku: string; product_name: string; label?: string; price?: number }>;
    section_layout?: "1" | "2" | "2x1" | "1x2" | "3" | "4";
    columns?: Array<Array<Element>>;
    accepted_types?: string[];
    max_files?: number;
    // ... etc
  };
}

// Tool: create_page
interface CreatePageTool {
  name: "create_page";
  parameters: {
    name: string;
    elements: Element[];
  };
}

// Tool: create_configurator
interface CreateConfiguratorTool {
  name: "create_configurator";
  parameters: {
    name: string;
    pages: Page[];
  };
}
```

### Why This Helps AI Agents

| Before (Flat) | After (Discriminated Union) |
|--------------|----------------------------|
| "Create a select element with type=select, options=[...], and also min=5 max=10" | "Create a select element with options=[...]" |
| AI can set `min` on a `select` (nonsensical but valid TypeScript) | `SelectElement` has no `min` field — compile error |
| 25 optional fields to reason about | 5-10 fields per type, all relevant |
| No per-type documentation possible | OpenAPI discriminator gives exact schema per kind |

---

## 12. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Form builder drag-and-drop breaks** | Medium | High | Extensive testing in Phase 3; feature flag allows rollback |
| **Constraint evaluator regression** | Medium | High | Phase 4 includes full test suite; compare behavior before/after |
| **PDF generation fails for old quotes** | Low | High | Phase 6 tests with legacy snapshots; edge function dual-format support |
| **Import configurator breaks** | Low | High | Phase 7 integration tests; maintain backward compatibility during transition |
| **Migration corrupts existing configs** | Low | Critical | Lazy migration (convert on save, not bulk); backups; staging validation |
| **Performance degradation** | Low | Medium | Typed structs may unmarshal slightly slower; benchmark if concerned |
| **Frontend bundle size increase** | Low | Low | More type definitions but tree-shaken in production |

---

## 13. Comparison: Adding a New Type

### Before (Flat Interface)

```typescript
// Step 1: Add to union
type FieldType = "text" | "number" | ... | "ai_prompt"; // ← add here

// Step 2: Add optional fields to shared interface
interface Element {
  // ... existing 25 fields ...
  promptTemplate?: string;     // ← only for ai_prompt
  outputFormat?: string;       // ← only for ai_prompt
  maxTokens?: number;          // ← only for ai_prompt
}

// Step 3: Add validation everywhere
function validateElement(element: Element) {
  if (element.type === "ai_prompt" && !element.promptTemplate) {
    throw new Error("ai_prompt requires promptTemplate");
  }
  // Other types can now accidentally have promptTemplate set
}

// Step 4: Update ALL components
// - Form builder property panel
// - Runtime evaluator
// - Quote builder
// - PDF generator
// - Import/export
```

### After (Discriminated Union)

```typescript
// Step 1: Add to unions
type ElementKind = "text" | "number" | ... | "ai_prompt";
type Element = TextElement | NumberElement | ... | AiPromptElement;

// Step 2: Add new interface (isolated)
interface AiPromptElement extends ElementBase {
  kind: "ai_prompt";
  promptTemplate: string;
  outputFormat?: string;
  maxTokens?: number;
}

// Step 3: Add component (isolated)
// AiPromptElementProperties.tsx

// Step 4: Add runtime handler (isolated)
// Only if ai_prompt needs special constraint/evaluation logic
```

**No existing code needs changes.**

---

## 14. Decision Log

| Date | Decision | Context |
|------|----------|---------|
| 2026-05-15 | `kind` (not `type`) | Aligns with all other discriminated union refactors |
| 2026-05-15 | Extract `ElementBase` | 6 fields are universal; avoids repetition |
| 2026-05-15 | 8 incremental phases | Blast radius too large for monolithic refactor |
| 2026-05-15 | Feature flag per phase | Allows rollback without reverting all changes |
| 2026-05-15 | Lazy migration (convert on save) | Too risky to bulk-migrate all configurator JSONB |
| 2026-05-15 | Flat Go struct with `omitempty` | Same proven pattern as `CalculationStep` |
| 2026-05-15 | 8-10 week estimate | Large but manageable with phased approach |

---

## 15. Open Questions

1. **Should `Option` also be a discriminated union?** Options have `isProductLinked` which changes available fields. Or is `Option` simple enough to keep flat?
2. **Section columns:** Should `columns` contain `Element[][]` or a dedicated `Column` type? Columns have layout properties too.
3. **Layout fields:** `span` and `disableStacking` are layout-related. Should they be in `ElementBase` or a `LayoutConfig` sub-object?
4. **Pricing fields on non-price elements:** Some non-price elements have `price`, `sku`, `productId` (e.g. select options with product links). Is the current model correct?
5. **File element:** `acceptedTypes` and `maxFiles` are file-specific. Should we extract a `FileConfig` object?
6. **Migration strategy:** Lazy migration (convert on save) is safest but slow. Do we need a batch migration script for staging/production?
7. **AI worker impact:** The AI worker parses configurators. Does it need updates to handle the new element format?
8. **Portal impact:** The customer portal renders forms. Does it share element types with the main frontend?

---

## 16. Related Documents

- [Constraint Discriminated Union RFC](./constraint-discriminated-union-rfc.md)
- [Quote Builder Discriminated Union RFC](./quote-builder-discriminated-union-rfc.md)
- [Backend Calculation Migration](./backend-calculation-migration.md)
- Frontend: `src/features/configurators/types/form.types.ts`
- Frontend: `src/features/configurators/hooks/useFormBuilderViewModel.ts`
- Frontend: `src/features/quotations/lib/configurationParser.ts`
- Backend: `internal/domain/configurators/service.go`
- Backend: `internal/data/repositories/configurators.go`
