"""
Climate Auditor — ClimateBERT Text Validator

Ported from harshith branch and adapted for async pipeline integration.
Uses the HuggingFace Inference API with ClimateBERT (distilroberta-base)
to validate whether extracted text chunks are genuinely climate-relevant
before passing them to the LLM for facility extraction.

This acts as a quality filter: chunks about office furniture, marketing, etc.
get filtered out, and only real emissions/facility disclosures go through.
"""

import os
from typing import Dict, Optional

import httpx


class ClimateAuditorAgent:
    """Validates text climate-relevance using ClimateBERT on HuggingFace."""

    def __init__(
        self,
        token: Optional[str] = None,
        model_id: str = "climatebert/distilroberta-base-climate-detector",
    ):
        self._token = token or os.getenv("HF_TOKEN", "")
        self.api_url = f"https://router.huggingface.co/hf-inference/models/{model_id}"
        self._available = bool(self._token)

    @property
    def available(self) -> bool:
        return self._available

    async def validate_climate_disclosure(self, text: str) -> Dict:
        """Determine if text contains a relevant climate disclosure.

        Returns:
            {
                "is_climate_relevant": bool,
                "confidence": float (0-1),
                "original_label": str,
            }
        """
        if not self._available:
            # No HF token — skip validation, assume relevant
            return {"is_climate_relevant": True, "confidence": 1.0, "original_label": "skipped"}

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    self.api_url,
                    headers={"Authorization": f"Bearer {self._token}"},
                    json={"inputs": text[:512]},  # ClimateBERT max ~512 tokens
                )
                resp.raise_for_status()
                output = resp.json()

            # Output format: [[{"label": "yes", "score": 0.99}, ...]]
            if output and isinstance(output, list) and isinstance(output[0], list):
                top = sorted(output[0], key=lambda x: x["score"], reverse=True)[0]
                return {
                    "is_climate_relevant": top["label"] == "yes",
                    "confidence": round(top["score"], 4),
                    "original_label": top["label"],
                }

        except Exception as e:
            # API error — don't block pipeline, assume relevant
            print(f"ClimateBERT validation error: {e}")

        return {"is_climate_relevant": True, "confidence": 0.0, "original_label": "error"}

    async def filter_relevant_chunks(
        self, chunks: list[Dict], min_confidence: float = 0.5
    ) -> list[Dict]:
        """Filter a list of RAG chunks, keeping only climate-relevant ones.

        Each chunk should have a "content" key with the text.
        """
        if not self._available:
            return chunks  # No filtering without HF token

        filtered = []
        for chunk in chunks:
            text = chunk.get("content", "")
            if not text:
                continue

            result = await self.validate_climate_disclosure(text)
            if result["is_climate_relevant"] or result["confidence"] < min_confidence:
                chunk["climate_validation"] = result
                filtered.append(chunk)

        return filtered if filtered else chunks  # Fallback: return all if none pass
