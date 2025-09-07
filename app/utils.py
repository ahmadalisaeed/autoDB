from typing import List, Dict, Any
import json


def rows_to_text(rows: List[Dict[str, Any]]) -> List[str]:
    # Turn dict rows into flat "key: value" strings for embedding
    texts = []
    for row in rows:
        parts = []
        for k, v in row.items():
            parts.append(f"{k}: {v}")
        texts.append(" | ".join(parts))
    return texts


def robust_json_dump(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return str(obj)

