# Exa + Zotero Integration Contract

## Purpose

Exa and Zotero are external adapters of Avereth. They do not become a second workflow state machine or source of truth.

## Exa role

Exa is a discovery adapter only:

- terminology expansion;
- collision discovery;
- literature discovery;
- web and document discovery.

Exa results enter as candidate evidence. Search snippets, rankings, and summaries cannot directly become final-source evidence.

## Zotero role

Zotero is the user's personal literature library:

- item metadata;
- attachments;
- reading state;
- citation key management;
- BibTeX export.

The canonical project identity remains `Source ID` in `literature_registry.json`.

## Identity chain

```
Exa discovery
    -> Source ID candidate
    -> Zotero item mapping
    -> content verification
    -> final-source
    -> references.bib
    -> manuscript citation
```

The project keeps two receipt-bound supporting snapshots instead of copying
external caches into the source registry:

- `reference_materials/integrations/exa_runs/manifest.json` indexes immutable
  `avereth-exa-run/v1` bundles and their SHA-256 values;
- `reference_materials/integrations/zotero_snapshot.json` records the selected
  Source ID to Zotero item/citation-key identity mapping.

`literature_registry.json` remains canonical. In `cnki-acquisition/v3`, an Exa
query may point to its run artifact and a source may retain an Exa discovery
event or a Zotero identity link. Those fields record provenance; they do not
change citation permission.

## Constraints

- External adapters must return structured facts only.
- They cannot advance workflow stages.
- They cannot create independent receipt systems.
- Exa is a semantic discovery channel, not an international academic-content
  channel; Exa results must remain `candidate-only` until original-content
  verification changes the canonical channel.
- Zotero presence, attachments, collections, or tags cannot promote a source.
- `identity_digest` is SHA-256 over canonical JSON containing `server_id`,
  `library_id`, `source_id`, `item_key`, `item_version`, `citation_key`, the
  lower-cased DOI, and sorted attachment keys; the offline validator recomputes
  it instead of trusting a supplied digest.
- Ambiguous matches require review.
- All mutations must support dry-run, atomic apply, backup, and rollback.
