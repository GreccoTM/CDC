import json
import os
import requests
import re
import sys
from collections import defaultdict

# Function to get the base path for PyInstaller or normal execution
def get_base_path():
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller creates a temporary folder and stores path in _MEIPASS
        return sys._MEIPASS
    else:
        # Normal execution
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ALL_PRINTINGS_PATH = os.path.join(get_base_path(), "AllPrintings.json")

# Placeholder for the efficiently loaded data
_all_cards_data = None

def _load_all_printings_efficiently():
    """
    Parses the AllPrintings.json file efficiently to extract only
    card names, types, and color identity, storing them in a dictionary for quick lookup.
    This avoids loading the entire massive JSON file into memory.
    Handles duplicate card names by prioritizing "Legendary Creature" types.
    """
    global _all_cards_data
    if _all_cards_data is not None:
        return _all_cards_data

    _all_cards_data = {}
    print(f"Loading data from {ALL_PRINTINGS_PATH} efficiently...")
    cards_processed_count = 0

    try:
        with open(ALL_PRINTINGS_PATH, 'r', encoding='utf-8') as f:
            full_data = json.load(f)
            if "data" in full_data:
                for set_code, set_data in full_data["data"].items():
                    if "cards" in set_data:
                        for card in set_data["cards"]:
                            cards_processed_count += 1
                            card_name = card.get("name")
                            card_type = card.get("type")
                            card_color_identity = card.get("colorIdentity", []) # Assuming colorIdentity is a list of strings
                            
                            if card_name and card_type:
                                lower_card_name = card_name.lower()
                                
                                # Prioritize "Legendary Creature" type for duplicate card names
                                if lower_card_name not in _all_cards_data:
                                    _all_cards_data[lower_card_name] = {
                                        "name": card_name,
                                        "type": card_type,
                                        "colorIdentity": card_color_identity
                                    }
                                else:
                                    # If existing entry is not legendary, but new one is, update it
                                    if "Legendary Creature" in card_type and \
                                       "Legendary Creature" not in _all_cards_data[lower_card_name]["type"]:
                                        _all_cards_data[lower_card_name] = {
                                            "name": card_name,
                                            "type": card_type,
                                            "colorIdentity": card_color_identity
                                        }

        print(f"Finished processing {cards_processed_count} total cards from file.")
        print(f"Finished loading {len(_all_cards_data)} unique cards into dictionary.")

    except FileNotFoundError:
        print(f"Error: AllPrintings.json not found at {ALL_PRINTINGS_PATH}")
        _all_cards_data = {} # Initialize as empty to prevent repeated errors
    except json.JSONDecodeError as e:
        print(f"Error decoding AllPrintings.json: {e}")
        _all_cards_data = {}
    except Exception as e:
        print(f"An unexpected error occurred during AllPrintings loading: {e}")
        _all_cards_data = {}

    return _all_cards_data

def get_all_printings_data_cached():
    """
    Returns the cached or efficiently loaded AllPrintings data.
    """
    global _all_cards_data
    if _all_cards_data is None:
        _all_cards_data = _load_all_printings_efficiently()
    return _all_cards_data


def get_card_details(card_name):
    """
    Looks up card details from the efficiently loaded AllPrintings data.
    Returns a dictionary of card details (name, type, colorIdentity) or None if not found.
    """
    data = get_all_printings_data_cached()
    return data.get(card_name.lower())

def is_eligible_commander(card_details):
    """
    Checks if a card is eligible to be a commander.
    Simplified for now: must be a Legendary Creature.
    """
    if card_details and "type" in card_details:
        return "Legendary Creature" in card_details["type"]
    return False

def get_edhrec_recommendations(commander_name):
    """
    Fetches EDHREC recommendations for a given commander, extracting from multiple relevant sections.
    """
    # Format commander name for EDHREC URL
    formatted_name = commander_name.lower()
    # Remove all non-alphanumeric characters except spaces and hyphens, then replace spaces with hyphens
    formatted_name = re.sub(r"[^\w\s-]", "", formatted_name)
    formatted_name = re.sub(r"\s+", "-", formatted_name)
    edhrec_url = f"https://json.edhrec.com/pages/commanders/{formatted_name}.json"
    
    print(f"Fetching EDHREC data for {commander_name} from: {edhrec_url}")

    try:
        response = requests.get(edhrec_url)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        data = response.json()
        
        all_recommendations = set() # Use a set to automatically handle duplicates
        
        if "container" in data and "json_dict" in data["container"] and "cardlists" in data["container"]["json_dict"]:
            for cardlist in data["container"]["json_dict"]["cardlists"]:
                # Extract from relevant sections. Prioritize "Top Cards" if available.
                # Other useful tags might be "highsynergycards", "creatures", "instants", "sorceries", etc.
                if cardlist.get("tag") in ["topcards", "highsynergycards", "creatures", "instants", "sorceries", "artifacts", "enchantments", "lands", "planeswalkers"]:
                    for card_info in cardlist.get("cardviews", []): # cardviews instead of cards
                        rec_name = card_info.get("name")
                        if rec_name:
                            all_recommendations.add(rec_name)
        
        recommendations_list = sorted(list(all_recommendations))
        print(f"Found {len(recommendations_list)} EDHREC recommendations for {commander_name}.")
        return recommendations_list

    except requests.exceptions.RequestException as e:
        print(f"Error fetching EDHREC data for {commander_name}: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error decoding EDHREC JSON for {commander_name}: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None

def get_card_price_from_scryfall(card_name):
    """
    Busca o preço em USD de uma carta utilizando a API do Scryfall.

    Args:
        card_name (str): O nome da carta a ser pesquisada.

    Returns:
        float: O preço da carta em USD, ou None se não encontrado/houver erro.
    """
    scryfall_url = f"https://api.scryfall.com/cards/named?exact={card_name}"
    
    try:
        response = requests.get(scryfall_url, timeout=5)
        response.raise_for_status() # Lança exceção para erros HTTP (4xx ou 5xx)
        card_data = response.json()
        
        # Verifica se a carta possui preços e retorna o preço em USD
        if "prices" in card_data and "usd" in card_data["prices"] and card_data["prices"]["usd"] is not None:
            return float(card_data["prices"]["usd"])
        elif "prices" in card_data and "usd_foil" in card_data["prices"] and card_data["prices"]["usd_foil"] is not None:
            return float(card_data["prices"]["usd_foil"])
        else:
            return None # Preço não encontrado
            
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar preço no Scryfall para '{card_name}': {e}")
        return None
    except ValueError:
        print(f"Erro de conversão de preço para '{card_name}'.")
        return None
    except Exception as e:
        print(f"Ocorreu um erro inesperado ao buscar preço para '{card_name}': {e}")
        return None

def get_usd_to_brl_exchange_rate():
    """
    Busca a taxa de câmbio atual de USD para BRL usando api.exchangerate-api.com.

    Returns:
        float: A taxa de câmbio USD para BRL, ou um valor padrão (5.0) em caso de erro.
    """
    exchange_rate_url = "https://api.exchangerate-api.com/v4/latest/USD"
    try:
        response = requests.get(exchange_rate_url, timeout=5)
        response.raise_for_status()
        data = response.json()
        if "rates" in data and "BRL" in data["rates"]:
            return float(data["rates"]["BRL"])
        else:
            print("Erro: Taxa de câmbio BRL não encontrada na resposta da API.")
            return None # Valor padrão em caso de não encontrar a taxa
    except requests.exceptions.RequestException as e:
        print(f"Erro ao buscar taxa de câmbio: {e}. Retornando None.")
        return None # Valor padrão em caso de erro de conexão ou API
    except Exception as e:
        print(f"Ocorreu um erro inesperado ao buscar taxa de câmbio: {e}. Retornando None.")
        return None # Valor padrão para outros erros