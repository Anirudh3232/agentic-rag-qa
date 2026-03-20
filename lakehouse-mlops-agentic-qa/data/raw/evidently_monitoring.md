# Evidently for ML Monitoring

Evidently is an open-source Python library for evaluating, testing, and monitoring machine-learning models and data pipelines. It generates interactive HTML reports and JSON snapshots.

## Common Report Types

- Data Drift: detects distribution shifts between a reference dataset and the current dataset using statistical tests such as the Kolmogorov-Smirnov test or Population Stability Index.
- Data Quality: checks for missing values, duplicates, and out-of-range values.
- Model Performance: tracks accuracy, precision, recall, and other classification or regression metrics over time.

## Integration with MLOps Pipelines

Evidently reports can be generated as a step in a CI/CD pipeline. A typical integration pattern:

1. After each pipeline run, generate a Data Quality and Data Drift report comparing the new data against a stored baseline.
2. Parse the JSON output to extract drift scores and quality metrics.
3. Feed these metrics into a promotion engine that decides whether the new model or data version should be promoted, held for canary evaluation, or rejected.

## When to Use Evidently

- Continuous training pipelines where data changes frequently.
- Regulatory environments that require auditable data-quality evidence.
- Any system where silent data drift could degrade model performance without immediate user-visible symptoms.
