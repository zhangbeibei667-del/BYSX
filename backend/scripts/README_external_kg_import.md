# External TCM KG Import Notes

This project now supports two levels of KG enhancement:

1. `clinical_supplement` overlay under `integrated_entities_graphrag/data/`
   - Small, reviewed additions for common demo gaps.
   - Loaded automatically by `LocalGraphRAGService`.
   - Current examples: 胃火炽盛、阳明胃热、清胃散、玉女煎、温胆汤、八正散、益胃汤.

2. Batch import script for open-source KG exports:
   - Script: `backend/scripts/import_external_kg.py`
   - Intended for selected files from `AI-HPC-Research-Team/TCM_knowledge_graph`.
   - Also usable for similarly named CSV/TSV relation files.

## Recommended AI-HPC subsets

Prefer importing the relation subsets closest to the teaching Agent:

- `syndrome2tcm_symptom`
- `prescription2symptom`
- `prescription2medicinal_material`
- `herb2symptom`
- `herb2syndrome`

These improve:

- symptom normalization;
- symptom → syndrome reasoning;
- syndrome/formula recommendation;
- formula → herb explanations.

## Important: GitHub ZIP is not the full processed KG

The GitHub ZIP may only contain:

- `data/` raw examples;
- `processed_code/`;
- no `merge_result/` directory.

Do not import the raw sample directly into the running demo unless you have
checked the entity names.  Some raw folders use IDs such as `SMSY00001` without
the final aligned Chinese syndrome name, which can pollute frontend results.

For production/demo enhancement, prefer the processed files under:

```text
merge_result/entity/*.csv
merge_result/relation/*.csv
```

If `merge_result` is missing, either:

1. run the upstream processing scripts after downloading all required source
   databases described in their README; or
2. use our reviewed `clinical_supplement` overlay for small demo gaps.

## Example

```powershell
python backend\scripts\import_external_kg.py `
  --input-dir D:\datasets\TCM_knowledge_graph\merge_result `
  --output-dir integrated_entities_graphrag\data `
  --source AI-HPC-TCM-KG `
  --limit 50000
```

The script writes:

- `integrated_entities_graphrag/data/entities/entities_external_import.json`
- `integrated_entities_graphrag/data/relations/relations_external_import.json`

Restart the backend after importing.

## Notes

- Do not blindly import every relation type into the teaching demo; the source KG
  is much larger and noisier than the current app needs.
- Import a subset first, validate results with `/api/agent/case`, then expand.
- If a dataset license is non-commercial, keep that restriction in project docs.
