import stanza
import re

# Завантаження моделей (один раз)
stanza.download('uk')
stanza.download('ru')

# Ініціалізація пайплайнів
nlp_uk = stanza.Pipeline(lang='uk', processors='tokenize,mwt,pos,lemma')
nlp_ru = stanza.Pipeline(lang='ru', processors='tokenize,pos,lemma')


# Нормалізація тексту
def normalize_text(text: str) -> list[str]:
    cleaned_text = re.sub(r"[^\w\s]", "", text.lower())

    # Обробка тексту обома мовами
    doc_uk = nlp_uk(cleaned_text)
    doc_ru = nlp_ru(cleaned_text)

    normalized = set()  # Використовуємо set для уникнення дублювання

    # Лемматизація для української мови
    for sentence in doc_uk.sentences:
        for word in sentence.words:
            normalized.add(word.lemma)

    # Лемматизація для російської мови
    for sentence in doc_ru.sentences:
        for word in sentence.words:
            normalized.add(word.lemma)

    return list(normalized)  # Повертаємо список з унікальними лемами



