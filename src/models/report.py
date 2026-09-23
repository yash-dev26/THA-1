"""Final structured output models."""

from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl

from src.models.evidence import Confidence


class ComparisonRow(BaseModel):
    dimension: str
    values: dict[str, str] = Field(default_factory=dict)


class CompetitorProfile(BaseModel):
    name: str
    focus: str
    evidence_claims: list[str]
    source_urls: list[HttpUrl]


class EvidenceRow(BaseModel):
    claim: str
    source_url: HttpUrl
    confidence: Confidence


class CompetitiveReport(BaseModel):
    subject: str
    executive_summary: str
    competitors: list[CompetitorProfile]
    comparison_table: list[ComparisonRow]
    evidence_table: list[EvidenceRow]

    def to_markdown(self) -> str:
        lines: list[str] = []
        lines.append(f"# Competitive Landscape: {self.subject}")
        lines.append("")
        lines.append("## Executive Summary")
        lines.append("")
        lines.append(self.executive_summary)
        lines.append("")
        lines.append("## Competitors")
        for comp in self.competitors:
            lines.append("")
            lines.append(f"### {comp.name}")
            lines.append(f"- Focus: {comp.focus}")
            lines.append("- Evidence:")
            for claim in comp.evidence_claims:
                lines.append(f"  - {claim}")
            lines.append("- Sources:")
            for url in comp.source_urls:
                lines.append(f"  - {url}")

        if self.comparison_table:
            lines.append("")
            lines.append("## Comparison")
            lines.append("")
            competitor_names = [c.name for c in self.competitors]
            header = "| Dimension | " + " | ".join(competitor_names) + " |"
            sep = "|---|" + "|".join(["---"] * len(competitor_names)) + "|"
            lines.append(header)
            lines.append(sep)
            for row in self.comparison_table:
                cells = [row.values.get(name, "—") for name in competitor_names]
                lines.append(f"| {row.dimension} | " + " | ".join(cells) + " |")

        if self.evidence_table:
            lines.append("")
            lines.append("## Evidence & Confidence")
            lines.append("")
            lines.append("| Claim | Source | Confidence |")
            lines.append("|---|---|---|")
            for row in self.evidence_table:
                lines.append(f"| {row.claim} | {row.source_url} | {row.confidence.value} |")

        return "\n".join(lines) + "\n"
