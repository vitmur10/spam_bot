import re
from const import ActionLog
# регулярка для виявлення рядків, що складаються переважно з літер, розділених комами
def is_scrambled_text(text):
    if not text:
        return False
    # ділимо текст на частини по комі
    parts = [p.strip() for p in text.split(',')]
    # рахуємо, скільки з них — одна літера
    single_letter_parts = [p for p in parts if re.fullmatch(r'[а-яА-Яa-zA-ZёЁіІїЇєЄ]', p)]
    if not parts:
        return False
    # якщо більше 70% частин — одиночні літери, вважаємо це "зашумленим" текстом
    return len(single_letter_parts) / len(parts) > 0.7

# обробка всіх об'єктів моделі
for obj in ActionLog.objects.all():
    if is_scrambled_text(obj.info):  # замініть `text_field` на свою назву поля
        obj.info = ""  # або "" якщо хочете залишити порожній рядок
        obj.save()
