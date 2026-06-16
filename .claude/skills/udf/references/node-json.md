# node.json Full Field Reference

node.json is validated by a **strict** schema when you register — unknown fields are rejected. The onboarding UI validates the contract before saving.

## Top-level fields

| Field | Type | Required | Notes |
|---|---|---|---|
| `version` | `"1.0"` (literal) | yes | Only accepted value |
| `nodeType` | `"config" \| "processing"` | yes | `config` = frontend-only (no container); `processing` = containerized |
| `name` | string, min 1 | yes | Display name; globally unique across all nodes (including soft-deleted). Slug is auto-generated from it |
| `shortDescription` | string, max 200 | no (default `""`) | Palette tooltip |
| `description` | string | no (default `""`) | Full description |
| `githubUrl` | URL | no* | Must be `github.com` (or `*.github.com`), no embedded credentials. *Required in practice for processing nodes — builds clone from it |
| `githubRef` | string, max 255 | no | Branch/tag/commit (default branch used if omitted) |
| `lucideIcon` | string, max 100 | no | Lucide icon name shown in palette/canvas |
| `color` | `#RRGGBB` | no | Node color |
| `hasInput` | boolean | no (default false) | Renders left input handle. If false, `inputDescription` must be `""` |
| `inputDescription` | string | no (default `""`) | Input handle tooltip |
| `config` | object of config fields | effectively yes | **Must contain the `name` field** (see below) |
| `hasOutput` | boolean | no (default false) | Renders right output handle. If false, `outputDescription` and `outputFiles` must be empty |
| `outputDescription` | string | no (default `""`) | Output handle tooltip |
| `outputFiles` | array | no (default `[]`) | See below |
| `implementation` | object | processing only | **Forbidden** for `config` nodes |

This table is exhaustive — the strict schema rejects any other field (commonly attempted ones: `actions`, `connections`, `outputs` as an object, `category`, `tags`, `resources`).

## The mandatory `name` config field

Every contract must include `config.name`. Locked properties: `type: "string"`, `label: "Name"`, `required: true`, `unique: true`. Customizable: `description`, `placeholder`, `validation.patternKey`.

At pipeline-execute time the user-entered value must match `^[a-zA-Z_][a-zA-Z0-9_]*$`, be ≤80 chars, and be unique within the pipeline. Save-time validation is lenient (allows empty/incomplete).

## Config field types

All fields share these base properties:

| Property | Type | Default | Notes |
|---|---|---|---|
| `type` | enum | required | See table below |
| `label` | string | required | UI label |
| `description` | string | `""` | Help text |
| `required` | boolean | `false` | |
| `default` | any | — | |
| `placeholder` | string | `""` | |
| `unique` | boolean | `false` | Value must be unique across pipeline nodes |
| `order` | number | — | Sort order in the form (lower first; `name` pinned top as fallback) |

| `type` | Extra properties | UI |
|---|---|---|
| `string` | `validation: { minLength, maxLength, patternKey, patternError }` | Text input |
| `number` | `validation: { minimum, maximum, integer, step }` | Number input |
| `boolean` | — | Switch |
| `select` | `options: [{ value, label }]` | Dropdown |
| `multi-select` | `options: [{ value, label }]` | Multi dropdown → array value |
| `date` | — | Date picker (YYYY-MM-DD) |
| `datetime` | — | Date+time picker (ISO string) |
| `code` | `language: "sql" \| "python" \| "javascript"` | Code textarea |
| `json` | `schema: {...}` (JSON Schema, optional) | JSON textarea (auto-parsed) |
| `key-value` | `key_label`, `value_label` | Dynamic key/value rows |
| `array` | `item_type: "string" \| "number"`, `min_items`, `max_items` (min ≤ max) | Dynamic list |
| `file` | `source: "uploads" \| "artifacts"`, `formats: ["parquet", ...]` | File browser over MinIO |

`patternKey` allowed values (custom regex is rejected): `identifier`, `snake_case`, `kebab_case`, `camelCase`, `PascalCase`, `slug`, `alphanumeric`, `lowercase`, `uppercase`, `numeric`.

Config field keys should be snake_case identifiers so `{{config.key}}` template references work.

## outputFiles

```json
{ "name": "result", "format": "parquet", "path": "{{artifacts}}/{{pipeline.name}}/{{execution.timestamp}}/{{node.name}}/result.parquet" }
```

| Property | Required | Notes |
|---|---|---|
| `name` | no (but recommended) | Logical name; must be unique within `outputFiles`. Downstream nodes see it in `inputs[].output.name` |
| `path` | yes (or legacy `format`) | Template expression resolved to a full S3 path at execution |
| `format` | no | Legacy; prefer encoding the type in the path extension |

Available template variables (resolved by the platform at execution): `{{uploads}}`, `{{artifacts}}`, `{{file}}`, `{{pipeline.name}}`, `{{execution.id}}`, `{{execution.timestamp}}`, `{{node.name}}`, `{{node.slug}}`, `{{config.<field_key>}}`. Unknown tokens are not validated — they silently resolve to an empty string at execution, so typos corrupt paths without an error.

## implementation

```json
{ "type": "container", "entrypoint": "python main.py", "dockerfilePath": "Dockerfile", "dockerContext": "." }
```

- `type`: literal `"container"` (only option).
- `entrypoint`: command must be one of `python`, `python3`, `node`, `java`, `bash`, `sh`, `/usr/bin/python(3)`, `/usr/bin/node`, `/bin/bash`, `/bin/sh`; max 500 chars; no shell metacharacters (`; | & $ () {} [] <> \ !` backticks) anywhere.
- `dockerfilePath` (default `"Dockerfile"`) and `dockerContext` (default `"."`): relative paths within the repo; `..`, leading `/`, `~`, and characters outside `[a-zA-Z0-9._/-]` are rejected.
