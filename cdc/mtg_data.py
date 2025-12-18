import ijson
import json
import os
import re
import sys
import requests
import logging
from collections import defaultdict
import urllib.parse

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_base_path():
    """
    Retorna o caminho base para dados, lidando com execução normal e empacotada pelo PyInstaller.
    """
    if hasattr(sys, "_MEIPASS"):
        # Dentro de um bundle PyInstaller
        return sys._MEIPASS
    else:
        # Execução normal de script
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class MTGDataManager:
    """
    Gerencia o carregamento, cache e acesso aos dados de cartas de Magic: The Gathering.
    """

    def __init__(self, all_printings_path=None):
        """
        Inicializa o gerenciador de dados.

        Args:
            all_printings_path (str, optional): Caminho para o arquivo AllPrintings.json.
                                               Se não for fornecido, usa o padrão.
        """
        if all_printings_path is None:
            self.all_printings_path = os.path.join(get_base_path(), "AllPrintings.json")
        else:
            self.all_printings_path = all_printings_path

        self._all_cards_data = None  # Cache para os dados das cartas

    def _load_all_printings(self):
        """
        Carrega e processa o arquivo AllPrintings.json usando um parser de streaming (ijson)
        para otimizar o uso de memória. Cria um dicionário de cartas, priorizando
        criaturas lendárias em casos de nomes duplicados.
        """
        if self._all_cards_data is not None:
            return

        self._all_cards_data = {}
        logging.info(f"Carregando dados de {self.all_printings_path} usando ijson...")
        cards_processed_count = 0

        try:
            with open(self.all_printings_path, "rb") as f:
                # Usar ijson.items para iterar diretamente sobre os objetos de carta
                all_sets = ijson.items(f, 'data')
                for sets in all_sets:
                    for set_code, set_data in sets.items():
                        if 'cards' in set_data and isinstance(set_data['cards'], list):
                            for card in set_data['cards']:
                                if 'name' in card:
                                    card_name_lower = card['name'].lower()
                                    
                                    # Lógica para priorizar criaturas lendárias
                                    if card_name_lower not in self._all_cards_data or \
                                    ("Legendary" in card.get("supertypes", []) and \
                                    "Creature" in card.get("types", [])):
                                        self._all_cards_data[card_name_lower] = card

                                    cards_processed_count += 1
                                    if cards_processed_count % 5000 == 0:
                                        logging.info(f"Processadas {cards_processed_count} cartas...")

            logging.info(f"Carregamento concluído. Total de {len(self._all_cards_data)} cartas únicas processadas.")

        except FileNotFoundError:
            logging.error(f"Erro: AllPrintings.json não encontrado em {self.all_printings_path}")
            self._all_cards_data = {}
        except ijson.JSONError as e:
            logging.error(f"Erro ao parsear AllPrintings.json com ijson: {e}")
            self._all_cards_data = {}
        except Exception as e:
            logging.error(f"Um erro inesperado ocorreu ao carregar AllPrintings.json: {e}")
            self._all_cards_data = {}

    def get_card_details(self, card_name):
        """
        Busca os detalhes de uma carta a partir dos dados cacheados.

        Args:
            card_name (str): O nome da carta.

        Returns:
            dict: Detalhes da carta ou None se não encontrada.
        """
        if self._all_cards_data is None:
            self._load_all_printings()
        return self._all_cards_data.get(card_name.lower())

    @staticmethod
    def is_eligible_commander(card_details):
        """
        Verifica se uma carta é um comandante elegível (criatura lendária).
        """
        if card_details and "type" in card_details:
            return "Legendary Creature" in card_details["type"]
        return False

    @staticmethod
    def get_edhrec_recommendations(commander_name):
        """
        Busca recomendações do EDHREC para um dado comandante.
        """
        # Limpa e formata o nome do comandante para a URL
        base_name = re.sub(r"[^\w\s-]", "", commander_name.lower()).replace(" ", "-")
        # Codifica o nome para garantir que seja seguro para a URL
        formatted_name = urllib.parse.quote(base_name)
        
        edhrec_url = f"https://json.edhrec.com/pages/commanders/{formatted_name}.json"
        logging.info(f"Buscando dados do EDHREC para {commander_name} em: {edhrec_url}")

        try:
            # Define um timeout para evitar que a aplicação fique presa indefinidamente
            response = requests.get(edhrec_url, timeout=10)
            # Lança uma exceção para respostas com status de erro (4xx ou 5xx)
            response.raise_for_status()
            data = response.json()

            # Extrai as recomendações de forma segura, verificando a existência das chaves
            recommendations = {
                card["name"]
                for cardlist in data.get("container", {})
                .get("json_dict", {})
                .get("cardlists", [])
                if cardlist  # Garante que a lista de cartas não é None
                for card in cardlist.get("cardviews", [])
                if card and "name" in card  # Garante que a carta e seu nome existem
            }
            logging.info(f"Recomendações do EDHREC para {commander_name} buscadas com sucesso. Encontradas {len(recommendations)} cartas.")
            return sorted(list(recommendations))

        except requests.exceptions.RequestException as e:
            logging.error(f"Erro ao buscar dados do EDHREC para {commander_name}: {e}")
        except json.JSONDecodeError as e:
            # Ocorre se a resposta não for um JSON válido
            logging.error(f"Erro ao decodificar JSON do EDHREC para {commander_name}: {e}")
        except Exception as e:
            # Captura outras exceções inesperadas
            logging.error(f"Erro inesperado ao buscar recomendações do EDHREC: {e}")
        return None

    @staticmethod
    def get_card_price_from_scryfall(card_name):
        """
        Busca o preço em USD de uma carta no Scryfall de forma segura.
        """
        logging.info(f"Buscando preço no Scryfall para a carta: '{card_name}'")
        try:
            # Codifica o nome da carta para garantir que seja seguro para a URL
            encoded_card_name = urllib.parse.quote(card_name)
            scryfall_url = f"https://api.scryfall.com/cards/named?exact={encoded_card_name}"

            # Define um timeout e trata exceções de requisição
            response = requests.get(scryfall_url, timeout=5)
            response.raise_for_status()
            card_data = response.json()

            # Extrai o preço de forma segura
            prices = card_data.get("prices", {})
            price_str = prices.get("usd") or prices.get("usd_foil")
            
            # Converte o preço para float, tratando o caso de ser None
            price = float(price_str) if price_str else None
            
            if price is not None:
                logging.info(f"Preço encontrado para '{card_name}': US${price:.2f}")
            else:
                logging.warning(f"Preço não disponível no Scryfall para '{card_name}'.")
            return price

        except requests.exceptions.RequestException as e:
            logging.warning(f"Erro na API do Scryfall para '{card_name}': {e}")
        except (ValueError, TypeError) as e:
            # Ocorre se a conversão do preço para float falhar
            logging.warning(f"Erro ao processar o preço para '{card_name}': {e}")
        except Exception as e:
            # Captura outras exceções inesperadas
            logging.error(f"Erro inesperado ao buscar preço para '{card_name}': {e}")
        return None

    @staticmethod
    def get_usd_to_brl_exchange_rate():
        """
        Busca a taxa de câmbio USD para BRL.
        """
        logging.info("Buscando taxa de câmbio USD para BRL...")
        exchange_rate_url = "https://api.exchangerate-api.com/v4/latest/USD"
        try:
            response = requests.get(exchange_rate_url, timeout=5)
            response.raise_for_status()
            data = response.json()
            if "rates" in data and "BRL" in data["rates"]:
                rate = float(data["rates"]["BRL"])
                logging.info(f"Taxa de câmbio USD-BRL encontrada: 1 USD = {rate:.2f} BRL.")
                return rate
            else:
                logging.warning("Taxa BRL não encontrada na resposta da API.")
                return None
        except requests.exceptions.RequestException as e:
            logging.error(f"Erro ao buscar taxa de câmbio: {e}")
        except (ValueError, TypeError) as e:
            logging.error(f"Erro ao processar taxa de câmbio: {e}")
        return None


# Instância única para ser usada em toda a aplicação
mtg_data_manager = MTGDataManager()
