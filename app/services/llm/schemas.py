"""JSON output schemas for structured LLM responses.

Every worker gets a strict output schema so responses are deterministic
and machine-parseable. No free-form prose.
"""

from __future__ import annotations


OFFER_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "mechanism": {
            "type": "object",
            "properties": {
                "what_it_does": {"type": "string"},
                "how_it_works": {"type": "string"},
                "why_its_believable": {"type": "string"},
                "unique_factor": {"type": "string"},
            },
        },
        "cta_analysis": {
            "type": "object",
            "properties": {
                "primary_cta": {"type": "string"},
                "cta_type": {"type": "string"},
                "friction_level": {"type": "string"},
                "risk_reversal": {"type": "string"},
            },
        },
        "constraints": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "constraint": {"type": "string"},
                    "category": {"type": "string"},
                    "severity": {"type": "string"},
                },
            },
        },
        "proof_basis": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim": {"type": "string"},
                    "proof_type": {"type": "string"},
                    "strength": {"type": "string"},
                    "source": {"type": "string"},
                },
            },
        },
        "buyer_context": {
            "type": "object",
            "properties": {
                "primary_audience": {"type": "string"},
                "awareness_level": {"type": "string"},
                "buying_motivation": {"type": "string"},
                "key_objections": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
}


LANDING_PAGE_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "page_structure": {
            "type": "object",
            "properties": {
                "above_fold": {"type": "string"},
                "headline_hierarchy": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "level": {"type": "string"},
                            "text": {"type": "string"},
                            "function": {"type": "string"},
                        },
                    },
                },
                "section_flow": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "section_name": {"type": "string"},
                            "purpose": {"type": "string"},
                            "effectiveness": {"type": "string"},
                        },
                    },
                },
            },
        },
        "claims": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "claim_text": {"type": "string"},
                    "claim_type": {"type": "string"},
                    "section": {"type": "string"},
                    "supported_by": {"type": "string"},
                    "risk_level": {"type": "string"},
                },
            },
        },
        "proof_elements": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "element": {"type": "string"},
                    "proof_type": {"type": "string"},
                    "placement": {"type": "string"},
                    "effectiveness": {"type": "string"},
                },
            },
        },
        "friction_points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "friction": {"type": "string"},
                    "location": {"type": "string"},
                    "impact": {"type": "string"},
                    "fix": {"type": "string"},
                },
            },
        },
        "cta_analysis": {
            "type": "object",
            "properties": {
                "primary_cta_text": {"type": "string"},
                "cta_count": {"type": "integer"},
                "belief_transfer_before_cta": {"type": "string"},
                "friction_at_cta": {"type": "string"},
            },
        },
    },
}


VOC_ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "desire_clusters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "theme": {"type": "string"},
                    "intensity": {"type": "string"},
                    "exact_phrases": {"type": "array", "items": {"type": "string"}},
                    "frequency": {"type": "integer"},
                },
            },
        },
        "pain_clusters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "theme": {"type": "string"},
                    "intensity": {"type": "string"},
                    "exact_phrases": {"type": "array", "items": {"type": "string"}},
                    "frequency": {"type": "integer"},
                },
            },
        },
        "objections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "objection": {"type": "string"},
                    "underlying_fear": {"type": "string"},
                    "exact_phrases": {"type": "array", "items": {"type": "string"}},
                    "frequency": {"type": "integer"},
                },
            },
        },
        "language_patterns": {
            "type": "object",
            "properties": {
                "words_they_use": {"type": "array", "items": {"type": "string"}},
                "metaphors": {"type": "array", "items": {"type": "string"}},
                "emotional_triggers": {"type": "array", "items": {"type": "string"}},
            },
        },
    },
}


DESIRE_MAP_SCHEMA = {
    "type": "object",
    "properties": {
        "primary_wants": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "want": {"type": "string"},
                    "intensity": {"type": "string"},
                    "evidence_refs": {"type": "array", "items": {"type": "string"}},
                    "awareness_level_match": {"type": "string"},
                },
            },
        },
        "pain_escapes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pain": {"type": "string"},
                    "escape_desire": {"type": "string"},
                    "evidence_refs": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "identity_motives": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "identity": {"type": "string"},
                    "aspiration": {"type": "string"},
                    "evidence_refs": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
        "hidden_constraints": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "constraint": {"type": "string"},
                    "implication_for_copy": {"type": "string"},
                },
            },
        },
    },
}


PROOF_INVENTORY_SCHEMA = {
    "type": "object",
    "properties": {
        "proof_hierarchy": {
            "type": "object",
            "properties": {
                "scientific": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "claim": {"type": "string"},
                            "source": {"type": "string"},
                            "strength": {"type": "string"},
                            "usability": {"type": "string"},
                        },
                    },
                },
                "authority": {"type": "array", "items": {"type": "object"}},
                "social": {"type": "array", "items": {"type": "object"}},
                "product": {"type": "array", "items": {"type": "object"}},
                "logical": {"type": "array", "items": {"type": "object"}},
            },
        },
        "proof_gaps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "gap": {"type": "string"},
                    "impact": {"type": "string"},
                    "recommendation": {"type": "string"},
                },
            },
        },
        "strongest_proof_chain": {"type": "string"},
    },
}


DIFFERENTIATION_SCHEMA = {
    "type": "object",
    "properties": {
        "category_sameness": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "who_does_it": {"type": "string"},
                    "why_its_generic": {"type": "string"},
                },
            },
        },
        "unique_contrasts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "contrast_point": {"type": "string"},
                    "they_do": {"type": "string"},
                    "we_do": {"type": "string"},
                    "consequence_for_buyer": {"type": "string"},
                },
            },
        },
        "consequence_framing": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "if_they_choose_generic": {"type": "string"},
                    "if_they_choose_us": {"type": "string"},
                    "emotional_weight": {"type": "string"},
                },
            },
        },
    },
}


HOOK_TERRITORY_SCHEMA = {
    "type": "object",
    "properties": {
        "territories": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "territory_name": {"type": "string"},
                    "awareness_level": {"type": "string"},
                    "desire_anchor": {"type": "string"},
                    "proof_anchor": {"type": "string"},
                    "hook_examples": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "hook_text": {"type": "string"},
                                "hook_type": {"type": "string"},
                                "mechanism_connection": {"type": "string"},
                            },
                        },
                    },
                    "anti_generic_notes": {"type": "string"},
                },
            },
        },
    },
}


BRIEF_SCHEMA = {
    "type": "object",
    "properties": {
        "briefs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "brief_id": {"type": "string"},
                    "asset_type": {"type": "string"},
                    "awareness_level": {"type": "string"},
                    "hook": {"type": "string"},
                    "angle": {"type": "string"},
                    "mechanism_bridge": {"type": "string"},
                    "proof_sequence": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "emotional_arc": {"type": "string"},
                    "cta_setup": {"type": "string"},
                    "anti_generic_rules": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
            },
        },
    },
}


COPY_REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "generic_flags": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "flagged_text": {"type": "string"},
                    "why_generic": {"type": "string"},
                    "rewrite_direction": {"type": "string"},
                    "severity": {"type": "string"},
                },
            },
        },
        "specificity_score": {"type": "number"},
        "proof_density_score": {"type": "number"},
        "mechanism_presence": {"type": "boolean"},
        "overall_assessment": {"type": "string"},
    },
}


COMPRESSION_TAX_SCHEMA = {
    "type": "object",
    "properties": {
        "blocks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "original_text": {"type": "string"},
                    "role": {"type": "string"},
                    "action": {"type": "string"},
                    "revised_text": {"type": "string"},
                    "rationale": {"type": "string"},
                },
            },
        },
        "original_word_count": {"type": "integer"},
        "revised_word_count": {"type": "integer"},
        "reduction_percentage": {"type": "number"},
    },
}


ITERATION_HEADER_SCHEMA = {
    "type": "object",
    "properties": {
        "iteration_headers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "asset_type": {"type": "string"},
                    "asset_section": {"type": "string"},
                    "target": {"type": "string"},
                    "reason": {"type": "string"},
                    "evidence_basis": {"type": "string"},
                    "constraint": {"type": "string"},
                    "priority": {"type": "string"},
                    "expected_effect": {"type": "string"},
                    "test_hypothesis": {"type": "string"},
                },
            },
        },
    },
}


COPY_GENERATION_SCHEMA = {
    "type": "object",
    "properties": {
        "drafts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "draft_id": {"type": "string"},
                    "awareness_level": {"type": "string"},
                    "format": {"type": "string"},
                    "hook": {"type": "string"},
                    "body": {"type": "string"},
                    "cta": {"type": "string"},
                    "mechanism_bridge": {"type": "string"},
                    "proof_elements_used": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "anti_generic_check": {"type": "string"},
                    "word_count": {"type": "integer"},
                },
            },
        },
    },
}


HOOK_GENERATION_SCHEMA = {
    "type": "object",
    "properties": {
        "hooks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "hook_text": {"type": "string"},
                    "hook_type": {"type": "string"},
                    "awareness_level": {"type": "string"},
                    "proof_anchor": {"type": "string"},
                    "mechanism_connection": {"type": "string"},
                    "why_it_works": {"type": "string"},
                    "strength_score": {"type": "integer"},
                },
            },
        },
        "strength_pass_notes": {"type": "string"},
    },
}


HEADLINE_GENERATION_SCHEMA = {
    "type": "object",
    "properties": {
        "headlines": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "headline_text": {"type": "string"},
                    "headline_type": {"type": "string"},
                    "awareness_level": {"type": "string"},
                    "proof_anchor": {"type": "string"},
                    "character_count": {"type": "integer"},
                    "strength_score": {"type": "integer"},
                    "why_it_works": {"type": "string"},
                },
            },
        },
    },
}


ORGANIC_DISCOVERY_SCHEMA = {
    "type": "object",
    "properties": {
        "seeds": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "seed_text": {"type": "string"},
                    "source_type": {"type": "string"},
                    "source_platform": {"type": "string"},
                    "source_url": {"type": "string"},
                    "hook_extracted": {"type": "string"},
                    "format_type": {"type": "string"},
                    "angle_extracted": {"type": "string"},
                    "potential": {"type": "string"},
                    "relevance_to_offer": {"type": "string"},
                },
            },
        },
        "trend_signals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "trend": {"type": "string"},
                    "platform": {"type": "string"},
                    "relevance": {"type": "string"},
                },
            },
        },
    },
}


SWIPE_MINER_SCHEMA = {
    "type": "object",
    "properties": {
        "swipes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ad_text": {"type": "string"},
                    "advertiser": {"type": "string"},
                    "platform": {"type": "string"},
                    "format_type": {"type": "string"},
                    "running_duration": {"type": "string"},
                    "spend_signal": {"type": "string"},
                    "hook_analysis": {"type": "string"},
                    "angle_analysis": {"type": "string"},
                    "proof_elements": {"type": "array", "items": {"type": "string"}},
                    "seed_potential": {"type": "string"},
                },
            },
        },
        "competitive_themes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "theme": {"type": "string"},
                    "frequency": {"type": "integer"},
                    "saturation_level": {"type": "string"},
                },
            },
        },
    },
}


COVERAGE_MATRIX_SCHEMA = {
    "type": "object",
    "properties": {
        "segment_coverage": {
            "type": "object",
            "properties": {
                "active": {"type": "array", "items": {"type": "string"}},
                "untested": {"type": "array", "items": {"type": "string"}},
                "gap_severity": {"type": "string"},
            },
        },
        "awareness_coverage": {
            "type": "object",
            "properties": {
                "over_indexed": {"type": "string"},
                "under_indexed": {"type": "string"},
                "gap_severity": {"type": "string"},
            },
        },
        "cash_coverage": {
            "type": "object",
            "properties": {
                "concepts_tested": {"type": "integer"},
                "angles_tested": {"type": "integer"},
                "styles_tested": {"type": "integer"},
                "hooks_tested": {"type": "integer"},
                "clustering": {"type": "string"},
            },
        },
        "recommended_priorities": {
            "type": "array",
            "items": {"type": "string"},
        },
        "gap_report": {"type": "string"},
    },
}


IMAGE_CONCEPT_SCHEMA = {
    "type": "object",
    "properties": {
        "concepts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "concept_description": {"type": "string"},
                    "source": {"type": "string"},
                    "scroll_stop_score": {"type": "integer"},
                    "native_feed_score": {"type": "integer"},
                    "emotional_trigger": {"type": "string"},
                    "copy_alignment": {"type": "string"},
                    "format": {"type": "string"},
                    "production_method": {"type": "string"},
                },
            },
        },
    },
}


IMAGE_PROMPT_SCHEMA = {
    "type": "object",
    "properties": {
        "prompts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "concept_ref": {"type": "string"},
                    "prompt_text": {"type": "string"},
                    "tool": {"type": "string"},
                    "style_notes": {"type": "string"},
                    "format": {"type": "string"},
                    "native_enforcement": {"type": "string"},
                },
            },
        },
    },
}


REFLECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "durable_lessons": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "lesson": {"type": "string"},
                    "confidence": {"type": "number"},
                    "evidence_count": {"type": "integer"},
                    "evidence_summary": {"type": "string"},
                    "falsifiable_prediction": {"type": "string"},
                },
            },
        },
        "emerging_patterns": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "observation_count": {"type": "integer"},
                    "needs_more_evidence": {"type": "boolean"},
                },
            },
        },
        "strategic_shifts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "shift": {"type": "string"},
                    "from_state": {"type": "string"},
                    "to_state": {"type": "string"},
                    "recommended_action": {"type": "string"},
                },
            },
        },
    },
}
