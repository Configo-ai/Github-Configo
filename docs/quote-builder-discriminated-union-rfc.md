# RFC: Quote Builder Block Discriminated Union Refactor

**Status:** Exploratory / Research  
**Scope:** Quote builder blocks (`selected_fields`)  
**Author:** AI Agent  
**Related:** [Constraint Discriminated Union RFC](./constraint-discriminated-union-rfc.md)

---

## 1. Executive Summary

This RFC proposes applying the discriminated union pattern to **quote builder blocks**. Currently, quote builder uses a single flat `Block` interface with `type: BlockType` and `data: { [key: string]: any }`, making it impossible for AI agents to generate valid block configurations with confidence.

The refactor introduces typed block definitions with explicit `kind` fields, typed `data` per block type, and dual-format backward compatibility.

---

## 2. Problem Statement

### 2.1 Current Flat Format

```typescript
interface Block {
  id: string;
  type: "section" | "table" | "text" | "image" | "product" | "product-table" | "gallery";
  label: string;
  data?: { [key: string]: any }; // ← completely untyped
  children?: Block[];
  parentId?: string | null;
  collapsed?: boolean;
}
```

**AI Agent Pain Points:**
- **`data` is `any`:** AI must guess which fields are valid per block type
- **No validation:** Backend accepts `map[string]any` — invalid blocks silently fail at PDF generation time
- **Type-specific fields scattered:** `fields`, `images`, `columns`, `settings`, `fieldIds` all live in the same `data` bag
- **Hard to document:** Cannot generate OpenAPI schema for dynamic `data`

### 2.2 What Block Types Actually Need

| Block Type | Required Data Fields |
|-----------|---------------------|
| `section` | `columns: Block[][]`, `layout?: string` |
| `table` | `fields: QuoteBuilderFormField[]` |
| `text` | `description?: string`, `fields?: QuoteBuilderFormField[]` |
| `image` | `images: QuoteBuilderImageField[]`, `settings?: BlockSettings` |
| `gallery` | `fieldIds: string[]`, `settings?: BlockSettings` |
| `product` | `settings?: BlockSettings` |
| `product-table` | `settings?: BlockSettings` |

**Common fields** (all block types):
- `id`, `label`, `kind` (was `type`)
- `showOnPdf`, `showOnlyIfValue`, `showOnlyIfSelected`, `showFieldLabels`, `showFieldImages`, `showOnlyIfContent`, `fullWidth`, `showEvenIfEmpty`

---

## 3. Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Scope** | Quote builder blocks only | Well-defined, limited blast radius |
| **Field naming** | `kind` (not `type`) | Aligns with constraint/calculation pattern |
| **Common fields** | Extract shared base interface | Avoids repetition; AI knows what all blocks have |
| **Block-specific data** | Typed `data` per block kind | Each block has exactly the fields it needs |
| **Backward compatibility** | Dual-format (read old+new, write new only) | Same proven approach |
| **Migration** | SQL data migration (one-time) | Transform all existing `selected_fields` JSON |
| **OpenAPI** | Full schema with discriminator | AI agents consume schema programmatically |
| **Timeline** | Exploratory / research | Document now; implement after constraints |

---

## 4. Target Architecture

### 4.1 Block Discriminated Union

```typescript
// TypeScript (frontend)

interface BlockBase {
  id: string;
  label: string;
  showOnPdf?: boolean;
  showOnlyIfValue?: boolean;
  showOnlyIfSelected?: boolean;
  showFieldLabels?: boolean;
  showFieldImages?: boolean;
  showOnlyIfContent?: boolean;
  fullWidth?: boolean;
  showEvenIfEmpty?: boolean;
}

interface SectionBlock extends BlockBase {
  kind: "section";
  layout?: "1-col" | "2-col";
  columns: Block[][];
}

interface TableBlock extends BlockBase {
  kind: "table";
  fields: QuoteBuilderFormField[];
}

interface TextBlock extends BlockBase {
  kind: "text";
  description?: string;
  fields?: QuoteBuilderFormField[];
}

interface ImageBlock extends BlockBase {
  kind: "image";
  images: QuoteBuilderImageField[];
  settings?: BlockSettings;
}

interface GalleryBlock extends BlockBase {
  kind: "gallery";
  fieldIds: string[];
  settings?: BlockSettings;
}

interface ProductBlock extends BlockBase {
  kind: "product";
  settings?: BlockSettings;
}

interface ProductTableBlock extends BlockBase {
  kind: "product-table";
  settings?: BlockSettings;
}

type Block =
  | SectionBlock
  | TableBlock
  | TextBlock
  | ImageBlock
  | GalleryBlock
  | ProductBlock
  | ProductTableBlock;
```

```go
// Go (backend)

// BlockBase holds fields common to all block kinds.
type BlockBase struct {
    ID               string `json:"id"`
    Label            string `json:"label"`
    ShowOnPdf        *bool  `json:"show_on_pdf,omitempty"`
    ShowOnlyIfValue  *bool  `json:"show_only_if_value,omitempty"`
    ShowOnlyIfSelected *bool `json:"show_only_if_selected,omitempty"`
    ShowFieldLabels  *bool  `json:"show_field_labels,omitempty"`
    ShowFieldImages  *bool  `json:"show_field_images,omitempty"`
    ShowOnlyIfContent *bool `json:"show_only_if_content,omitempty"`
    FullWidth        *bool  `json:"full_width,omitempty"`
    ShowEvenIfEmpty  *bool  `json:"show_even_if_empty,omitempty"`
}

type Block struct {
    Kind string `json:"kind"`
    BlockBase

    // kind == "section"
    Layout  *string  `json:"layout,omitempty"`   // "1-col", "2-col"
    Columns [][]Block `json:"columns,omitempty"`

    // kind == "table" | "text"
    Fields []QuoteBuilderFormField `json:"fields,omitempty"`

    // kind == "text"
    Description *string `json:"description,omitempty"`

    // kind == "image"
    Images   []QuoteBuilderImageField `json:"images,omitempty"`
    Settings *BlockSettings           `json:"settings,omitempty"`

    // kind == "gallery"
    FieldIDs []string `json:"field_ids,omitempty"`

    // kind == "product" | "product-table"
    // Settings already covered above
}
```

### 4.2 BlockSettings (shared by image, gallery, product, product-table)

```typescript
interface BlockSettings {
  showPrice?: boolean;
  showSku?: boolean;
  showDescription?: boolean;
  columns?: number;        // gallery: number of columns
  imageSize?: "small" | "medium" | "large";
  [key: string]: unknown; // extensibility for future settings
}
```

```go
type BlockSettings struct {
    ShowPrice       *bool   `json:"show_price,omitempty"`
    ShowSku         *bool   `json:"show_sku,omitempty"`
    ShowDescription *bool   `json:"show_description,omitempty"`
    Columns         *int    `json:"columns,omitempty"`
    ImageSize       *string `json:"image_size,omitempty"`
}
```

---

## 5. Dual-Format Compatibility

### 5.1 Legacy → New Format Mapping

```go
func UnmarshalBlocks(data []byte) ([]Block, error) {
    // 1. Try new format (look for "kind" field)
    var blocks []Block
    if err := json.Unmarshal(data, &blocks); err == nil && len(blocks) > 0 && blocks[0].Kind != "" {
        return blocks, nil
    }

    // 2. Detect legacy format: { type: "table", data: { fields: [...] } }
    // 3. Convert legacy → new format:
    //    - type: "table" → kind: "table"
    //    - data.fields → fields (lifted to block level)
    //    - data.images → images
    //    - data.columns → columns
    //    - data.fieldIds → field_ids
    //    - data.settings → settings
    //    - data.description → description
    //    - data.layout → layout
    //    - Other data.* booleans → BlockBase fields
    // 4. Return always in new format
}
```

### 5.2 Legacy → New Field Mapping

| Legacy Path | New Path |
|------------|----------|
| `type` | `kind` |
| `data.fields` | `fields` |
| `data.images` | `images` |
| `data.columns` | `columns` |
| `data.fieldIds` | `field_ids` |
| `data.settings` | `settings` |
| `data.description` | `description` |
| `data.layout` | `layout` |
| `data.showOnPdf` | `show_on_pdf` |
| `data.showOnlyIfValue` | `show_only_if_value` |
| `data.showOnlyIfSelected` | `show_only_if_selected` |
| `data.showFieldLabels` | `show_field_labels` |
| `data.showFieldImages` | `show_field_images` |
| `data.showOnlyIfContent` | `show_only_if_content` |
| `data.fullWidth` | `full_width` |
| `data.showEvenIfEmpty` | `show_even_if_empty` |

**Key change:** Block-specific data is lifted from `data.*` to top-level block fields. This eliminates the `any` bag and makes each block self-describing.

---

## 6. Backend Implementation

### 6.1 New Package: `internal/domain/quotes/blocks`

```
internal/domain/quotes/
├── service.go              # existing
├── blocks/
│   ├── types.go            # Block, BlockBase, BlockSettings
│   ├── json.go             # Marshal/Unmarshal (dual-format)
│   ├── json_test.go        # Round-trip tests
│   └── validate.go         # ValidateBlocks()
```

### 6.2 Updated Quote Builder Config Struct

```go
// Before (any passthrough)
type QuoteBuilderConfig struct {
    ConfiguratorID   string          `json:"configurator_id"`
    OrganizationID   string          `json:"organization_id"`
    SelectedFields   json.RawMessage `json:"selected_fields"` // WAS: any
    CreatedAt        string          `json:"created_at"`
    UpdatedAt        string          `json:"updated_at"`
}

// After (typed)
type QuoteBuilderConfig struct {
    ConfiguratorID   string         `json:"configurator_id"`
    OrganizationID   string         `json:"organization_id"`
    SelectedFields   []blocks.Block `json:"selected_fields"`
    CreatedAt        string         `json:"created_at"`
    UpdatedAt        string         `json:"updated_at"`
}
```

### 6.3 Validation

```go
func ValidateBlocks(blocks []Block) error {
    for i, block := range blocks {
        if err := validateBlock(block); err != nil {
            return fmt.Errorf("blocks[%d]: %w", i, err)
        }
    }
    return nil
}

func validateBlock(block Block) error {
    switch block.Kind {
    case "section":
        if block.Columns == nil {
            return fmt.Errorf("section block requires columns")
        }
        for ci, col := range block.Columns {
            for ri, nested := range col {
                if err := validateBlock(nested); err != nil {
                    return fmt.Errorf("columns[%d][%d]: %w", ci, ri, err)
                }
            }
        }
    case "table":
        if len(block.Fields) == 0 {
            return fmt.Errorf("table block requires at least one field")
        }
    case "text":
        // optional fields and description
    case "image":
        if len(block.Images) == 0 {
            return fmt.Errorf("image block requires at least one image")
        }
    case "gallery":
        if len(block.FieldIDs) == 0 {
            return fmt.Errorf("gallery block requires at least one field ID")
        }
    case "product", "product-table":
        // settings optional
    default:
        return fmt.Errorf("unknown block kind: %q", block.Kind)
    }
    return nil
}
```

### 6.4 Handler Updates

```go
// internal/transport/http/handlers/quotes.go

type UpsertQuoteBuilderConfigRequest struct {
    ConfiguratorID   string         `json:"configurator_id"`
    OrganizationID   string         `json:"organization_id"`
    SelectedFields   []blocks.Block `json:"selected_fields"`
}

func (h *QuotesHandler) UpsertQuoteBuilderConfig(w http.ResponseWriter, r *http.Request) {
    var req UpsertQuoteBuilderConfigRequest
    if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
        response.WriteError(w, http.StatusBadRequest, "invalid_request", "request body must be valid JSON")
        return
    }

    if err := blocks.ValidateBlocks(req.SelectedFields); err != nil {
        response.WriteError(w, http.StatusBadRequest, "validation_error", err.Error())
        return
    }

    result, err := h.svc.UpsertQuoteBuilderConfig(r.Context(), map[string]any{
        "configurator_id": req.ConfiguratorID,
        "organization_id": req.OrganizationID,
        "selected_fields": req.SelectedFields,
    })
    // ... rest of handler
}
```

---

## 7. Frontend Implementation

### 7.1 Type Updates

```typescript
// features/quotations/types.ts (refactored)

// Re-export from new typed module
export type {
  Block,
  SectionBlock,
  TableBlock,
  TextBlock,
  ImageBlock,
  GalleryBlock,
  ProductBlock,
  ProductTableBlock,
  BlockBase,
  BlockSettings,
} from "./quote-builder-typed.types";
```

### 7.2 New File: `quote-builder-typed.types.ts`

```typescript
export interface BlockBase {
  id: string;
  label: string;
  showOnPdf?: boolean;
  showOnlyIfValue?: boolean;
  showOnlyIfSelected?: boolean;
  showFieldLabels?: boolean;
  showFieldImages?: boolean;
  showOnlyIfContent?: boolean;
  fullWidth?: boolean;
  showEvenIfEmpty?: boolean;
}

export interface SectionBlock extends BlockBase {
  kind: "section";
  layout?: "1-col" | "2-col";
  columns: Block[][];
}

export interface TableBlock extends BlockBase {
  kind: "table";
  fields: QuoteBuilderFormField[];
}

export interface TextBlock extends BlockBase {
  kind: "text";
  description?: string;
  fields?: QuoteBuilderFormField[];
}

export interface ImageBlock extends BlockBase {
  kind: "image";
  images: QuoteBuilderImageField[];
  settings?: BlockSettings;
}

export interface GalleryBlock extends BlockBase {
  kind: "gallery";
  fieldIds: string[];
  settings?: BlockSettings;
}

export interface ProductBlock extends BlockBase {
  kind: "product";
  settings?: BlockSettings;
}

export interface ProductTableBlock extends BlockBase {
  kind: "product-table";
  settings?: BlockSettings;
}

export type Block =
  | SectionBlock
  | TableBlock
  | TextBlock
  | ImageBlock
  | GalleryBlock
  | ProductBlock
  | ProductTableBlock;

export interface BlockSettings {
  showPrice?: boolean;
  showSku?: boolean;
  showDescription?: boolean;
  columns?: number;
  imageSize?: "small" | "medium" | "large";
  [key: string]: unknown;
}

// Type guards
export function isSectionBlock(block: Block): block is SectionBlock {
  return block.kind === "section";
}

export function isTableBlock(block: Block): block is TableBlock {
  return block.kind === "table";
}

export function isImageBlock(block: Block): block is ImageBlock {
  return block.kind === "image";
}

export function isGalleryBlock(block: Block): block is GalleryBlock {
  return block.kind === "gallery";
}
```

### 7.3 Component Updates

Update quote builder components to use discriminated unions:

```typescript
// QuoteBuilderCanvas.tsx — simplified example
function renderBlock(block: Block): React.ReactNode {
  switch (block.kind) {
    case "section":
      return <SectionBlock block={block} />;
    case "table":
      return <TableBlock block={block} />;
    case "text":
      return <TextBlock block={block} />;
    case "image":
      return <ImageBlock block={block} />;
    case "gallery":
      return <GalleryBlock block={block} />;
    case "product":
      return <ProductBlock block={block} />;
    case "product-table":
      return <ProductTableBlock block={block} />;
  }
}
```

### 7.4 Service Updates

Update `quoteBuilder.service.ts` to use typed blocks:

```typescript
// quoteBuilder.service.ts

async getQuoteBuilderConfig(configuratorId: string): Promise<QuoteBuilderConfigRow | null> {
  const config = await backendClient.get<QuoteBuilderConfigRow | null>(
    `/v1/quote-builder-configs/${encodeURIComponent(configuratorId)}`
  );

  if (!config?.selected_fields) {
    return config;
  }

  // Unmarshal handles dual-format (legacy flat + new discriminated union)
  const blocks = blocks.UnmarshalBlocks(config.selected_fields);
  
  // Validate and sanitize
  const validBlocks = blocks.filter(b => VALID_BLOCK_KINDS.includes(b.kind));
  
  return {
    ...config,
    selected_fields: validBlocks,
  };
}
```

---

## 8. Database Migration

### 8.1 Migration Script

**File:** `supabase/migrations/YYYYMMDD_migrate_quote_builder_blocks_to_discriminated_union.sql`

```sql
-- Migrate quote_builder_configs.selected_fields from legacy format to new discriminated union format
-- This is idempotent — blocks already in new format are unchanged.

CREATE OR REPLACE FUNCTION public.migrate_quote_builder_blocks(blocks jsonb)
RETURNS jsonb AS $$
DECLARE
  result jsonb := '[]'::jsonb;
  block jsonb;
  migrated jsonb;
BEGIN
  IF jsonb_typeof(blocks) != 'array' THEN
    RETURN blocks;
  END IF;

  FOR block IN SELECT jsonb_array_elements(blocks) LOOP
    -- Already migrated?
    IF block ? 'kind' THEN
      result := result || jsonb_build_array(block);
      CONTINUE;
    END IF;

    migrated := migrate_single_block(block);
    result := result || jsonb_build_array(migrated);
  END LOOP;

  RETURN result;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION public.migrate_single_block(block jsonb)
RETURNS jsonb AS $$
DECLARE
  block_type text;
  data jsonb;
  result jsonb;
BEGIN
  block_type := COALESCE(block->>'type', '');
  data := COALESCE(block->'data', '{}'::jsonb);

  -- Build base object with common fields
  result := jsonb_build_object(
    'id', block->>'id',
    'label', block->>'label',
    'kind', block_type
  );

  -- Migrate common boolean fields from data
  IF data ? 'showOnPdf' THEN
    result := jsonb_set(result, '{show_on_pdf}', to_jsonb((data->>'showOnPdf')::boolean));
  END IF;
  IF data ? 'showOnlyIfValue' THEN
    result := jsonb_set(result, '{show_only_if_value}', to_jsonb((data->>'showOnlyIfValue')::boolean));
  END IF;
  IF data ? 'showOnlyIfSelected' THEN
    result := jsonb_set(result, '{show_only_if_selected}', to_jsonb((data->>'showOnlyIfSelected')::boolean));
  END IF;
  IF data ? 'showFieldLabels' THEN
    result := jsonb_set(result, '{show_field_labels}', to_jsonb((data->>'showFieldLabels')::boolean));
  END IF;
  IF data ? 'showFieldImages' THEN
    result := jsonb_set(result, '{show_field_images}', to_jsonb((data->>'showFieldImages')::boolean));
  END IF;
  IF data ? 'showOnlyIfContent' THEN
    result := jsonb_set(result, '{show_only_if_content}', to_jsonb((data->>'showOnlyIfContent')::boolean));
  END IF;
  IF data ? 'fullWidth' THEN
    result := jsonb_set(result, '{full_width}', to_jsonb((data->>'fullWidth')::boolean));
  END IF;
  IF data ? 'showEvenIfEmpty' THEN
    result := jsonb_set(result, '{show_even_if_empty}', to_jsonb((data->>'showEvenIfEmpty')::boolean));
  END IF;

  -- Migrate kind-specific fields (lifted from data to top level)
  CASE block_type
    WHEN 'section' THEN
      IF data ? 'layout' THEN
        result := jsonb_set(result, '{layout}', to_jsonb(data->>'layout'));
      END IF;
      IF data ? 'columns' THEN
        -- Recursively migrate nested blocks in columns
        DECLARE
          columns jsonb := data->'columns';
          migrated_cols jsonb := '[]'::jsonb;
          col jsonb;
          migrated_col jsonb;
        BEGIN
          FOR col IN SELECT jsonb_array_elements(columns) LOOP
            migrated_col := '[]'::jsonb;
            FOR nested_block IN SELECT jsonb_array_elements(col) LOOP
              migrated_col := migrated_col || jsonb_build_array(migrate_single_block(nested_block));
            END LOOP;
            migrated_cols := migrated_cols || jsonb_build_array(migrated_col);
          END LOOP;
          result := jsonb_set(result, '{columns}', migrated_cols);
        END;
      ELSE
        result := jsonb_set(result, '{columns}', '[]'::jsonb);
      END IF;

    WHEN 'table' THEN
      IF data ? 'fields' THEN
        result := jsonb_set(result, '{fields}', data->'fields');
      ELSE
        result := jsonb_set(result, '{fields}', '[]'::jsonb);
      END IF;

    WHEN 'text' THEN
      IF data ? 'description' THEN
        result := jsonb_set(result, '{description}', to_jsonb(data->>'description'));
      END IF;
      IF data ? 'fields' THEN
        result := jsonb_set(result, '{fields}', data->'fields');
      END IF;

    WHEN 'image' THEN
      IF data ? 'images' THEN
        result := jsonb_set(result, '{images}', data->'images');
      ELSE
        result := jsonb_set(result, '{images}', '[]'::jsonb);
      END IF;
      IF data ? 'settings' THEN
        result := jsonb_set(result, '{settings}', data->'settings');
      END IF;

    WHEN 'gallery' THEN
      IF data ? 'fieldIds' THEN
        result := jsonb_set(result, '{field_ids}', data->'fieldIds');
      ELSIF data ? 'field_ids' THEN
        result := jsonb_set(result, '{field_ids}', data->'field_ids');
      ELSE
        result := jsonb_set(result, '{field_ids}', '[]'::jsonb);
      END IF;
      IF data ? 'settings' THEN
        result := jsonb_set(result, '{settings}', data->'settings');
      END IF;

    WHEN 'product', 'product-table' THEN
      IF data ? 'settings' THEN
        result := jsonb_set(result, '{settings}', data->'settings');
      END IF;

    ELSE
      -- Unknown block type: return as-is (preserves data for manual cleanup)
      result := block;
  END CASE;

  RETURN result;
END;
$$ LANGUAGE plpgsql;

-- Apply migration only to rows not yet migrated
UPDATE configurator.quote_builder_configs
SET selected_fields = migrate_quote_builder_blocks(selected_fields)
WHERE selected_fields IS NOT NULL
  AND jsonb_typeof(selected_fields) = 'array'
  AND jsonb_array_length(selected_fields) > 0
  AND NOT (selected_fields->0) ? 'kind';

-- Verify migration
SELECT
  id,
  CASE
    WHEN jsonb_typeof(selected_fields) = 'array' AND jsonb_array_length(selected_fields) > 0
    THEN (selected_fields->0) ? 'kind'
    ELSE true
  END as migrated
FROM configurator.quote_builder_configs;
```

---

## 9. OpenAPI Schema

```yaml
# openapi/openapi.yaml

components:
  schemas:
    Block:
      oneOf:
        - $ref: '#/components/schemas/SectionBlock'
        - $ref: '#/components/schemas/TableBlock'
        - $ref: '#/components/schemas/TextBlock'
        - $ref: '#/components/schemas/ImageBlock'
        - $ref: '#/components/schemas/GalleryBlock'
        - $ref: '#/components/schemas/ProductBlock'
        - $ref: '#/components/schemas/ProductTableBlock'
      discriminator:
        propertyName: kind
        mapping:
          section: '#/components/schemas/SectionBlock'
          table: '#/components/schemas/TableBlock'
          text: '#/components/schemas/TextBlock'
          image: '#/components/schemas/ImageBlock'
          gallery: '#/components/schemas/GalleryBlock'
          product: '#/components/schemas/ProductBlock'
          product-table: '#/components/schemas/ProductTableBlock'

    BlockBase:
      type: object
      required: [id, label]
      properties:
        id:
          type: string
        label:
          type: string
        show_on_pdf:
          type: boolean
        show_only_if_value:
          type: boolean
        show_only_if_selected:
          type: boolean
        show_field_labels:
          type: boolean
        show_field_images:
          type: boolean
        show_only_if_content:
          type: boolean
        full_width:
          type: boolean
        show_even_if_empty:
          type: boolean

    SectionBlock:
      allOf:
        - $ref: '#/components/schemas/BlockBase'
        - type: object
          required: [kind, columns]
          properties:
            kind:
              type: string
              enum: [section]
            layout:
              type: string
              enum: ["1-col", "2-col"]
            columns:
              type: array
              items:
                type: array
                items:
                  $ref: '#/components/schemas/Block'

    TableBlock:
      allOf:
        - $ref: '#/components/schemas/BlockBase'
        - type: object
          required: [kind, fields]
          properties:
            kind:
              type: string
              enum: [table]
            fields:
              type: array
              items:
                $ref: '#/components/schemas/QuoteBuilderFormField'

    TextBlock:
      allOf:
        - $ref: '#/components/schemas/BlockBase'
        - type: object
          required: [kind]
          properties:
            kind:
              type: string
              enum: [text]
            description:
              type: string
            fields:
              type: array
              items:
                $ref: '#/components/schemas/QuoteBuilderFormField'

    ImageBlock:
      allOf:
        - $ref: '#/components/schemas/BlockBase'
        - type: object
          required: [kind, images]
          properties:
            kind:
              type: string
              enum: [image]
            images:
              type: array
              items:
                $ref: '#/components/schemas/QuoteBuilderImageField'
            settings:
              $ref: '#/components/schemas/BlockSettings'

    GalleryBlock:
      allOf:
        - $ref: '#/components/schemas/BlockBase'
        - type: object
          required: [kind, field_ids]
          properties:
            kind:
              type: string
              enum: [gallery]
            field_ids:
              type: array
              items:
                type: string
            settings:
              $ref: '#/components/schemas/BlockSettings'

    ProductBlock:
      allOf:
        - $ref: '#/components/schemas/BlockBase'
        - type: object
          required: [kind]
          properties:
            kind:
              type: string
              enum: [product]
            settings:
              $ref: '#/components/schemas/BlockSettings'

    ProductTableBlock:
      allOf:
        - $ref: '#/components/schemas/BlockBase'
        - type: object
          required: [kind]
          properties:
            kind:
              type: string
              enum: [product-table]
            settings:
              $ref: '#/components/schemas/BlockSettings'

    BlockSettings:
      type: object
      properties:
        show_price:
          type: boolean
        show_sku:
          type: boolean
        show_description:
          type: boolean
        columns:
          type: integer
        image_size:
          type: string
          enum: [small, medium, large]

    QuoteBuilderFormField:
      type: object
      required: [id, label, type]
      properties:
        id:
          type: string
        label:
          type: string
        type:
          type: string
        options:
          type: array
          items:
            $ref: '#/components/schemas/QuoteBuilderOption'
        sku:
          type: string
        price:
          type: number
        imageUrl:
          type: string
        productId:
          type: string

    QuoteBuilderImageField:
      type: object
      required: [id, label]
      properties:
        id:
          type: string
        label:
          type: string
        imageUrl:
          type: string
```

---

## 10. AI Agent Interface

### 10.1 Tool Design

AI agent builders get structured tools for quote builder block creation:

```typescript
// Tool: create_block
interface CreateBlockTool {
  name: "create_block";
  parameters: {
    kind: "section" | "table" | "text" | "image" | "gallery" | "product" | "product-table";
    label: string;
    // kind-specific fields
    fields?: Array<{ id: string; label: string; type: string }>;
    images?: Array<{ id: string; label: string; imageUrl?: string }>;
    fieldIds?: string[];
    columns?: Array<Array<Block>>;
    description?: string;
    settings?: BlockSettings;
  };
}

// Tool: create_quote_builder_config
interface CreateQuoteBuilderConfigTool {
  name: "create_quote_builder_config";
  parameters: {
    configurator_id: string;
    blocks: Block[];
  };
}
```

### 10.2 Why This Helps AI Agents

| Before (flat format) | After (discriminated union) |
|---------------------|----------------------------|
| "Create a block with type=table, data.fields=[...]" | "Create a table block with fields=[...]" |
| AI must know about `data` wrapper and which fields go inside | Each `kind` has its fields at top level |
| Invalid combinations silently accepted | Backend validation rejects invalid blocks |
| No OpenAPI schema for block data | Full discriminator schema |

---

## 11. Rollout Plan

### Phase 1: Backend Types (1 day)
- Create `internal/domain/quotes/blocks/` package
- Add `Block`, `BlockBase`, `BlockSettings` structs
- Implement dual-format JSON marshal/unmarshal
- Add validation functions
- Write unit tests

### Phase 2: Backend Integration (1-2 days)
- Update `QuoteBuilderConfig` struct to use typed `[]Block`
- Update handlers to use typed request DTOs
- Add validation to Upsert handler
- Update repository layer
- Run `TestNewRouter_NoRouteConflicts`

### Phase 3: OpenAPI (0.5 day)
- Add all block schema components
- Update QuoteBuilderConfig schema

### Phase 4: SQL Migration (0.5-1 day)
- Write migration script
- Test on staging database copy
- Verify idempotency

### Phase 5: Frontend Types (0.5-1 day)
- Add `quote-builder-typed.types.ts`
- Update `types.ts` to re-export
- Add type guards

### Phase 6: Frontend Components (2-3 days)
- Update QuoteBuilderCanvas to switch on `block.kind`
- Update each block component (TableBlock, ImageBlock, etc.) to accept typed props
- Update quoteBuilderService to use typed blocks
- Update blockHelpers (findBlockById, updateBlockById)
- Update tests

### Phase 7: PDF Payload Builder (1 day)
- Update pdfPayloadBuilder to branch on `block.kind`
- Update block rendering logic in PDF generation

### Phase 8: Cleanup (0.5 day)
- Remove legacy format read support from backend
- Remove deprecated `BlockData` interface with `[key: string]: any`

**Total estimated effort:** 7-10 days

---

## 12. Comparison: Before vs After

### 12.1 AI Agent Prompt

**Before:**
```json
{
  "type": "table",
  "label": "Selected Options",
  "data": {
    "fields": [
      { "id": "field-1", "label": "Color", "type": "select" }
    ],
    "showOnPdf": true,
    "showFieldLabels": true
  }
}
```

**After:**
```json
{
  "kind": "table",
  "label": "Selected Options",
  "fields": [
    { "id": "field-1", "label": "Color", "type": "select" }
  ],
  "show_on_pdf": true,
  "show_field_labels": true
}
```

### 12.2 Validation Example

**Before:**
```json
{
  "type": "image",
  "label": "Photos",
  "data": {
    "fields": [{ "id": "f1", "label": "X" }]
  }
}
```
- Backend accepts this (image block with `fields` instead of `images`)
- Runtime: image block fails silently in PDF generation

**After:**
```json
{
  "kind": "image",
  "label": "Photos",
  "fields": [{ "id": "f1", "label": "X" }]
}
```
- Backend validation: `"blocks[0]: image block requires images field"`
- AI gets clear error before PDF generation

---

## 13. Open Questions

1. **Should we keep `parentId` and `collapsed`?** These are UI state fields. Should they be in the API contract or handled client-side only?
2. **Block settings extensibility:** `BlockSettings` has `[key: string]: unknown` for forward compatibility. Should we be stricter?
3. **Legacy block types:** Some configs may have old block types not in `VALID_BLOCK_TYPES`. Migration filters them out — is silent dropping acceptable?
4. **Children vs columns:** `section` blocks use `columns` for nesting. Should we unify with a generic `children` field like constraints do?
5. **Frontend block builder state:** The quote builder UI maintains block state in a tree. Does the discriminated union make drag-and-drop reordering harder?

---

## 14. Decision Log

| Date | Decision | Context |
|------|----------|---------|
| 2026-05-15 | `kind` (not `type`) | Aligns with constraint/calculation pattern |
| 2026-05-15 | Lift data fields to top level | Eliminates `any` bag; each block self-describing |
| 2026-05-15 | Extract `BlockBase` for common fields | Avoids repetition; AI knows universal fields |
| 2026-05-15 | Dual-format compatibility | Same proven approach as calculations/constraints |
| 2026-05-15 | SQL data migration | One-time transform of all `selected_fields` JSON |
| 2026-05-15 | 7-10 day estimate | Smaller blast radius than constraints or configuration data |

---

## 15. Related Documents

- [Constraint Discriminated Union RFC](./constraint-discriminated-union-rfc.md)
- [Backend Calculation Migration](./backend-calculation-migration.md)
- Frontend: `src/features/quotations/types.ts`
- Frontend: `src/features/quotations/services/quoteBuilder.service.ts`
- Frontend: `src/features/quotations/utils/blockHelpers.ts`
- Backend: `internal/domain/quotes/service.go`
- Backend: `internal/transport/http/handlers/quotes.go`
