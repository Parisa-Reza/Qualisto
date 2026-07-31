import re


class ClaimExtractor:

    @staticmethod
    def extract(text: str) -> list[str]:

        if not text or not text.strip():
            return []

        sentences = re.split(r"(?<=[.!?])\s+", text.strip())

        claims = []

        for sentence in sentences:
            sentence = sentence.strip()

            if not sentence:
                continue

            if ClaimExtractor._is_factual(sentence):
                claims.append(sentence)

        return claims

    @staticmethod
    def _is_factual(sentence: str) -> bool:

        subjective_patterns = [
            r"\bbeautiful\b",
            r"\bamazing\b",
            r"\bbest\b",
            r"\bwonderful\b",
            r"\bincredible\b",
            r"\bfantastic\b",
            r"\bunforgettable\b",
            r"\bperfect\b",
        ]

        for pattern in subjective_patterns:
            if re.search(pattern, sentence, re.IGNORECASE):
                return False

        factual_patterns = [
            r"\bis\b",
            r"\bare\b",
            r"\bwas\b",
            r"\bwere\b",
            r"\bhas\b",
            r"\bhave\b",
            r"\bcontains\b",
            r"\blocated\b",
            r"\bopened\b",
            r"\bbuilt\b",
            r"\bpopulation\b",
            r"\bkm\b",
            r"\bkilometers?\b",
            r"\b\d+\b",
        ]

        return any(
            re.search(pattern, sentence, re.IGNORECASE)
            for pattern in factual_patterns
        )