"""Higiene de entrada de texto (camada pura, sem Flask).

Fonte ÚNICA da regra de quais caracteres são barrados nos campos do sistema:
emojis/pictogramas e caracteres de controle/invisíveis. Letras acentuadas e
pontuação comum passam — barrá-las criaria bugs. Usada no login e nos formulários
do admin; o backend é a autoridade (a validação do front é sempre burlável).
"""
import unicodedata

# Faixas de codepoints de emoji/pictograma (complementam a categoria Unicode 'C*').
_FAIXAS_EMOJI = (
    (0x1F000, 0x1FAFF),  # pictogramas, emoticons, transporte, símbolos suplementares
    (0x1F1E6, 0x1F1FF),  # indicadores regionais (bandeiras)
    (0x2600, 0x27BF),    # símbolos diversos e dingbats
    (0x2B00, 0x2BFF),    # setas/estrelas decorativas usadas como emoji
    (0xFE00, 0xFE0F),    # seletores de variação (estilo emoji)
)


def _caractere_proibido(ch):
    """True se o caractere é de controle/invisível (categoria Unicode 'C*') ou emoji."""
    if unicodedata.category(ch).startswith("C"):
        return True
    cp = ord(ch)
    return any(inicio <= cp <= fim for inicio, fim in _FAIXAS_EMOJI)


def contem_caractere_proibido(*textos):
    """True se ALGUM texto contém emoji/pictograma ou caractere de controle/invisível."""
    return any(_caractere_proibido(ch) for texto in textos if texto for ch in texto)
