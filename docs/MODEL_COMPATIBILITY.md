# Model compatibility

Every imported model needs its own registry entry with artifact checksum, exact model type/version, ordered feature names, preprocessing, timeframe, symbols, probability method, class order, dependency versions, and training metadata. Validation fails closed on any mismatch. A model trained for 60-minute bars cannot consume 15-minute, 5-minute, or daily data. The included deterministic baseline is a safe bootstrap only, not a copied trained model; use `scripts/import_models.py` and update the registry only after metadata is recovered and verified.

