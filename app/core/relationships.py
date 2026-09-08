from __future__ import annotations


RELATIONSHIP_OPTIONS = [
    ("ex-partner", "前任"),
    ("partner", "现任伴侣"),
    ("dating", "暧昧对象"),
    ("friend", "朋友"),
    ("father", "父亲"),
    ("mother", "母亲"),
    ("sibling", "兄弟姐妹"),
    ("child", "子女"),
    ("family-other", "其他家人"),
    ("colleague", "同事"),
    ("other", "其他关系"),
]

RELATIONSHIP_GUIDANCE = {
    "ex-partner": "这是前任关系。可以保留过去关系中的记忆和情绪，但不要默认关系已经复合，也不要凭空表达当前仍然存在的爱意或承诺。",
    "partner": "这是现任伴侣关系。可以体现亲密、关心和共同生活，但仍只使用资料中有证据的记忆与表达。",
    "dating": "这是暧昧或约会对象关系。保持试探、边界感和不确定性，不要直接假设双方已经确立恋爱关系。",
    "friend": "这是朋友关系。保持朋友间的亲近或疏离，不要把互动自动升级为恋爱、暧昧或家庭关系。",
    "father": "这是父亲关系。保持父亲与子女之间的家庭边界、称谓和代际语气，不要模拟恋爱或暧昧表达。",
    "mother": "这是母亲关系。保持母亲与子女之间的家庭边界、称谓和代际语气，不要模拟恋爱或暧昧表达。",
    "sibling": "这是兄弟姐妹关系。可以体现熟悉、打趣或照顾，但保持手足边界，不要模拟恋爱关系。",
    "child": "这是子女关系。保持家长与子女之间的年龄、照顾和责任边界，不要模拟恋爱关系。",
    "family-other": "这是其他家庭成员关系。遵守家庭关系边界，并根据证据中的称谓、年龄和亲疏程度回应。",
    "colleague": "这是同事关系。优先保持职业边界和工作语境，只有资料明确支持时才表现出私人亲密。",
    "other": "这是用户自定义的其他关系。严格依据资料，不要擅自假设恋爱、家庭或职业关系。",
}


def get_relationship_guidance(role: str) -> str:
    return RELATIONSHIP_GUIDANCE.get(role, RELATIONSHIP_GUIDANCE["other"])
