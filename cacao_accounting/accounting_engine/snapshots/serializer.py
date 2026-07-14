# SPDX-License-Identifier: Apache-2.0
# SPDX-FileCopyrightText: 2025 - 2026 William José Moreno Reyes

"""Snapshot serialization logic."""

from __future__ import annotations
import json
import hashlib
from decimal import Decimal
from datetime import date, datetime
from dataclasses import is_dataclass, asdict
from typing import Any, Dict
from cacao_accounting.accounting_engine.common.context import CalculationContext


class EngineJSONEncoder(json.JSONEncoder):
    """Engine JSON Encoder."""

    def default(self, obj):
        """Serialize as default."""
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        if is_dataclass(obj):
            return asdict(obj)
        return super().default(obj)


class SnapshotSerializer:
    """Serializes calculation results for audit and historical reproducibility."""

    def serialize(self, context: CalculationContext, results: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize snapshot."""
        context_data = asdict(context)
        results_data = {}
        for engine, result in results.items():
            if engine in ("fiscal", "landed_cost", "settlement") and result:
                results_data[engine] = asdict(result)
            else:
                results_data[engine] = result

        snapshot: Dict[str, Any] = {
            "metadata": {
                "version": "1.1",
                "engine_version": "2.0.0",
                "timestamp": datetime.now().isoformat(),
                "event_type": context.event_type,
                "document_type": context.document_type,
            },
            "context": context_data,
            "results": results_data,
        }
        try:
            canonized = json.dumps(snapshot, cls=EngineJSONEncoder, sort_keys=True)
            snapshot["metadata"]["fingerprint"] = hashlib.sha256(canonized.encode()).hexdigest()
        except (TypeError, ValueError) as e:
            snapshot["errors"] = [f"Serialization error: {str(e)}"]
        return snapshot

    def to_json(self, snapshot: Dict[str, Any]) -> str:
        """To JSON."""
        return json.dumps(snapshot, cls=EngineJSONEncoder, indent=2)
