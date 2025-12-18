import logging
from mtg_data import mtg_data_manager
from collections import Counter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_commander_color_identity(commander_name):
    """
    Retrieves the color identity of a commander.
    Returns a set of colors (e.g., {'W', 'U', 'B', 'R', 'G'}) or an empty set if not found.
    """
    commander_details = mtg_data_manager.get_card_details(commander_name)
    if commander_details and "colorIdentity" in commander_details:
        return set(commander_details["colorIdentity"])
    return set()


def validate_card_list(cards_in_deck, commander_name):
    """
    Validates a list of cards against Commander deck building rules with improved efficiency.
    """
    validation_messages = []

    # 1. Validação do Comandante
    commander_details = mtg_data_manager.get_card_details(commander_name)
    if not commander_details:
        validation_messages.append(f"Erro: Comandante '{commander_name}' não encontrado.")
        return validation_messages
    if not mtg_data_manager.is_eligible_commander(commander_details):
        validation_messages.append(f"Erro: '{commander_name}' não é um comandante elegível.")
        return validation_messages

    commander_color_identity = set(commander_details.get("colorIdentity", []))

    # 2. Validação do Tamanho do Deck
    total_deck_size = len(cards_in_deck) + 1  # +1 para o comandante
    if total_deck_size != 100:
        validation_messages.append(
            f"Aviso: O deck tem {total_deck_size} cartas. Deve ter exatamente 100."
        )

    # 3. Validação de Singleton e Identidade de Cor em uma única passagem
    card_counts = Counter(cards_in_deck)
    for card_name, count in card_counts.items():
        card_details = mtg_data_manager.get_card_details(card_name)

        if not card_details:
            logging.warning(f"'{card_name}' não encontrado no banco de dados para validação.")
            validation_messages.append(f"Aviso: '{card_name}' não foi encontrado no banco de dados.")
            continue

        # Validação de Singleton (regra da cópia única)
        is_basic_land = "Basic Land" in card_details.get("type", "")
        if count > 1 and not is_basic_land:
            validation_messages.append(
                f"Erro: '{card_name}' aparece {count} vezes (viola a regra de singleton)."
            )

        # Validação da Identidade de Cor
        card_ci = set(card_details.get("colorIdentity", []))
        if not card_ci.issubset(commander_color_identity):
            validation_messages.append(
                f"Erro: A identidade de cor de '{card_name}' {sorted(list(card_ci))} "
                f"não corresponde à do comandante {sorted(list(commander_color_identity))}."
            )

    return validation_messages
