"""Doc-to-training pipeline.

Ingests markdown, PDF, and text documents and extracts structured
creative strategy knowledge (principles, frameworks, examples,
anti-patterns) into the training corpus format used by base_training.py.

Components:
  - ingester: LLM-powered extraction from raw docs → structured JSON
  - store: Versioned corpus files in app/knowledge/corpus/
"""
