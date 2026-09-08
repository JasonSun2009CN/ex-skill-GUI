"""无 GUI 的引擎层冒烟测试"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.evidence_parser import parse_text, label_turns, format_for_llm
from app.core.validators.profile_validator import validate_profile
from app.core.validators.skill_validator import validate_skill_dir
from app.core.imitation_generator import _build_subject_snapshot, ImitationGenerator
from pathlib import Path
import tempfile

SAMPLE_CHAT = """
————— 2024-05-01 —————
Joanna  10:23
早呀~今天起得好早

我  10:25
哈哈 被你吵醒啦 昨晚睡得好吗

Joanna  10:26
还不错~就是有点想你🥺
等下要去图书馆

我  10:28
加油哦！晚上一起吃饭？

Joanna  10:30
好呀！[Happy]

Joanna  10:30
去哪里吃呀 想吃寿司🍣
"""

print("== 1. evidence_parser ==")
turns = parse_text(SAMPLE_CHAT)
print(f"  parse_text: {len(turns)} turns")
for t in turns[:3]:
    print(f"    [{t.speaker}] {t.timestamp} -> {t.content[:30]}")

labeled = label_turns(turns, "Joanna", "我")
subject_n = sum(1 for t in labeled if t.speaker == "subject")
user_n = sum(1 for t in labeled if t.speaker == "user")
print(f"  label_turns: user={user_n} subject={subject_n}")

fmt = format_for_llm(labeled, 500)
print(f"  format_for_llm: {len(fmt)} chars, starts with: {fmt[:60]!r}")

print("\n== 2. profile_validator (空内容) ==")
errs = validate_profile("")
print(f"  empty profile errors: {len(errs)} -> {[e.code for e in errs]}")

MINIMAL_VALID = """---
schema_version: "1.0"
profile_type: "personality-speech-analysis"
subject_alias: "Joanna"
subject_role: "ex-partner"
generated_at: "2024-01-01T00:00:00Z"
primary_language: "zh-CN"
confidence: 0.5
status: "complete"
---

# Personality & Speech Profile — Joanna

## 1. Executive Summary
test

## 2. Core Personality Metrics
| Dimension | Score | Weight | Evidence |
|-----------|-------|--------|----------|

## 3. Communication Style
### 3.1 Sentence structure
x
### 3.2 Message segmentation
x
### 3.3 Vocabulary & register
x
### 3.4 Address terms & nicknames
x
### 3.5 Slang & colloquialisms
x
### 3.6 Punctuation, capitalization & formatting
x
### 3.7 Emoji, sticker & audio usage
x
### 3.8 Quantitative Communication Metrics (benchmarks)
#### 3.8.1 Message length
x
#### 3.8.2 Message frequency
x
#### 3.8.3 Reply length by input type
| Input type | Expected messages | Expected total chars | Example input → reply |
|-----------|-------------------|----------------------|----------------------|
#### 3.8.4 Tone modulation & cadence
x

## 4. Emotional Profile
### 4.1 Emotional range & dominant emotions
x
### 4.2 Emotional intensity & expressiveness
x
### 4.3 Emotional triggers
x
### 4.4 Emotion regulation style
x
### 4.5 Affection signaling
x
### 4.6 Mood fluctuation & stability
x
### 4.7 Attachment-style hypothesis
x

## 5. Tonal Characteristics by Context
| Context | Dominant tone | Intensity (0–1) | Example |
|---------|---------------|-----------------|---------|

## 6. Mentality & Psychology
### 6.1 Worldview & values
x
### 6.2 Self-perception & self-esteem signals
x
### 6.3 Motivation & goals
x
### 6.4 Defense mechanisms & coping
x
### 6.5 Decision-making style
x
### 6.6 Relationship attitudes & expectations
x
### 6.7 Cognitive style
x

## 7. Thematic Preferences
| Topic | Engagement (initiate / expand / deflect) | Example |
|-------|------------------------------------------|---------|

## 8. Response Latency & Engagement Dynamics
x

## 9. Idioms, Recurring Phrases & Linguistic Quirks
| Phrase / quirk | Type | Weight (0–1) | Example |
|----------------|------|--------------|---------|

## 10. Relationship Dynamics & Temporal Evolution
### 10.1 Power balance & reciprocity
x
### 10.2 Affection asymmetry
x
### 10.3 Conflict & teasing patterns
x
### 10.4 Temporal evolution
x

## 11. Memory Moments & Significant Events
### 11.1 Event list
| # | Period / timestamp | Event (what happened) | Subject's role | Observed emotional markers | Detailed emotional interpretation (inference) | Intensity (0–1) | Evidence quote |
|---|--------------------|-----------------------|----------------|----------------------------|-----------------------------------------------|-----------------|----------------|
### 11.2 Event-level emotional narrative
x

## 12. Annotated Sample Excerpts
x

## 13. Deep Interpretation & Synthesis
x

## 14. Simulation Guidance (for downstream AI)
### 14.1 Do
x
### 14.2 Avoid
x
### 14.3 Voice rules
x

## 15. Machine-Readable Profile (JSON)
```json
{
  "schema_version": "1.0",
  "subject": {"alias": "Joanna", "role": "ex-partner", "primary_language": "zh-CN"},
  "confidence": 0.5,
  "status": "complete",
  "personality_metrics": [],
  "communication_style": {"sentence_structure":"","message_segmentation":"","vocabulary_register":"","address_terms":[],"code_switching_triggers":[],"slang":[],"punctuation_capitalization":[],"emoji_sticker_audio_usage":""},
  "communication_metrics": {"message_length":{"mean_chars":0,"median_chars":0,"min_chars":0,"max_chars":0,"pct_le_8_chars":0,"pct_le_12_chars":0,"length_buckets":{}},"message_frequency":{"messages_per_turn_mean":0,"messages_per_turn_median":0,"single_message_turn_pct":0,"burst_distribution":{}},"reply_length_by_input_type":[],"tone_modulation":[],"cadence":{"reply_latency_engaged":"","reply_latency_disengaged":"","laughter_length_scale":"","voice_note_when":""}},
  "emotional_profile": {"range":"","dominant_emotions":[],"intensity":0,"expressiveness":0,"regulation":"","affection_signaling":"","mood_stability":0,"triggers":[],"attachment_style_hypothesis":""},
  "tones": [],
  "mentality": {"worldview":"","values":[],"self_perception":"","motivation":[],"defense_mechanisms":[],"decision_making":"","relationship_attitudes":"","cognitive_style":""},
  "themes": [],
  "response_latency": "",
  "linguistic_features": [],
  "relationship_dynamics": {"power_balance":"","reciprocity":"","affection_asymmetry":"","conflict_style":"","closeness":""},
  "temporal_evolution": [],
  "memory_moments": [],
  "sample_excerpts": [],
  "interpretation": [],
  "simulation_guidance": {"do":[],"avoid":[],"voice_rules":[]},
  "limitations": []
}
```

## 16. Limitations & Disclaimer
x
"""

print("\n== 3. profile_validator (完整最小样例) ==")
errs = validate_profile(MINIMAL_VALID)
fatal = [e for e in errs if e.severity == "error"]
warns = [e for e in errs if e.severity == "warning"]
print(f"  errors={len(fatal)} warnings={len(warns)}")
for e in errs[:10]:
    print(f"    [{e.severity}] {e.code}: {e.message[:80]}")

print("\n== 4. _build_subject_snapshot ==")
snapshot = _build_subject_snapshot(MINIMAL_VALID)
print(f"  generated {len(snapshot)} chars")
for line in snapshot.splitlines()[:8]:
    print(f"    {line[:100]}")

print("\n== 5. ImitationGenerator → validate_skill_dir ==")
with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    profile_path = tmp / "Joanna_personality_profile.md"
    profile_path.write_text(MINIMAL_VALID, encoding="utf-8")

    from app.core.paths import SKILLS_DIR
    from unittest.mock import patch
    with patch("app.core.imitation_generator.SKILLS_DIR", tmp / "skills"):
        gen = ImitationGenerator()
        skill_dir = gen.generate(profile_path)
        print(f"  generated skill dir: {skill_dir}")
        print(f"  files: {list(skill_dir.rglob('*'))}")
        errs = validate_skill_dir(skill_dir)
        fatal = [e for e in errs if e.severity == "error"]
        print(f"  validation: errors={len(fatal)} warnings={len(errs)-len(fatal)}")
        for e in errs:
            print(f"    [{e.severity}] {e.code}: {e.message}")

print("\n✅ 所有引擎层冒烟测试完成，无异常")
