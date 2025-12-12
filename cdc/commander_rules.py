import mtg_data
from collections import Counter

def get_commander_color_identity(commander_name):
    """
    Retrieves the color identity of a commander.
    Returns a set of colors (e.g., {'W', 'U', 'B', 'R', 'G'}) or an empty set if not found.
    """
    commander_details = mtg_data.get_card_details(commander_name)
    if commander_details and "colorIdentity" in commander_details:
        return set(commander_details["colorIdentity"])
    return set()

def validate_card_list(cards_in_deck, commander_name):
    """
    Validates a list of cards against Commander deck building rules.
    Args:
        cards_in_deck (list): A list of card names intended for the deck.
        commander_name (str): The name of the chosen commander.

    Returns:
        list: A list of validation messages (errors or warnings).
    """
    validation_messages = []

    # Ensure commander is in the decklist and eligible
    commander_details = mtg_data.get_card_details(commander_name)
    if not commander_details:
        validation_messages.append(f"Error: Commander '{commander_name}' not found in card database.")
        return validation_messages
    if not mtg_data.is_eligible_commander(commander_details):
        validation_messages.append(f"Error: '{commander_name}' is not an eligible commander.")
        return validation_messages
    
    commander_color_identity = get_commander_color_identity(commander_name)

    # Deck size validation
    # Commander is usually counted as 1 of the 100 cards, so 99 other cards + 1 commander.
    # For now, let's assume cards_in_deck is the 99 non-commander cards.
    # We will adjust this based on actual UI input later.
    # Assuming cards_in_deck does NOT include the commander for this check
    total_deck_size = len(cards_in_deck) + 1 # +1 for commander

    if total_deck_size != 100:
        validation_messages.append(f"Warning: Deck size is {total_deck_size}. Commander decks must be exactly 100 cards (including commander).")

    # Singleton rule validation (excluding basic lands)
    card_counts = Counter(cards_in_deck)
    for card_name, count in card_counts.items():
        if count > 1:
            card_details = mtg_data.get_card_details(card_name)
            if not card_details or (card_details and "Basic Land" not in card_details.get("type", "")):
                validation_messages.append(f"Error: '{card_name}' appears {count} times. Non-basic cards must adhere to the singleton rule.")
    
    # Color Identity validation
    all_cards_to_check = cards_in_deck + [commander_name] # Include commander for color identity check
    for card_name in all_cards_to_check:
        card_details = mtg_data.get_card_details(card_name)
        if card_details:
            card_ci = set(card_details.get("colorIdentity", []))
            # Check if all colors in card's color identity are within commander's color identity
            if not card_ci.issubset(commander_color_identity):
                validation_messages.append(
                    f"Error: '{card_name}' has color identity {sorted(list(card_ci))} which is outside of commander's color identity {sorted(list(commander_color_identity))}.")
        else:
            # This case should ideally be caught by _load_all_printings_efficiently earlier,
            # but good to have a fallback.
            validation_messages.append(f"Warning: '{card_name}' not found in card database for color identity check.")

    return validation_messages