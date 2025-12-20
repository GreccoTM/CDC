import ijson
import json
import os
import re
import sys
import requests
import logging
from collections import defaultdict
import urllib.parse
import unicodedata
import time

# Importa o gerenciador de preços LigaMagic
try:
    from ligamagic import ligamagic_manager
    LIGAMAGIC_AVAILABLE = True
except ImportError:
    logging.warning("Módulo LigaMagic não disponível. Preços brasileiros não estarão disponíveis.")
    LIGAMAGIC_AVAILABLE = False
    ligamagic_manager = None

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

        # ===================================================================
        # CONFIGURAÇÃO DO CACHE DE PREÇOS SCRYFALL
        # ===================================================================
        # Define o caminho para o arquivo de cache no diretório 'logs'
        logs_dir = os.path.join(get_base_path(), "logs")

        # Cria o diretório 'logs' se não existir
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)

        # Inicializa o cache de preços do Scryfall
        self.price_cache_path = os.path.join(logs_dir, "price_cache.json")
        self.price_cache = {}  # Dicionário em memória para armazenar preços consultados
        self._load_price_cache()  # Carrega cache existente do disco

        # ===================================================================
        # CACHE DE TAXA DE CÂMBIO
        # ===================================================================
        # A taxa de câmbio USD→BRL é consultada uma vez e reutilizada conforme
        # configuração do usuário (padrão: 10 minutos)
        # Isso reduz drasticamente o número de chamadas à API de câmbio
        self._exchange_rate_cache = None  # Última taxa de câmbio consultada
        self._exchange_rate_timestamp = 0  # Timestamp da última consulta
        # Nota: O TTL agora vem de config_manager.get_exchange_rate_ttl_seconds()

    def _load_price_cache(self):
        """
        Carrega o cache de preços do Scryfall do arquivo JSON.

        O cache armazena preços em USD consultados anteriormente,
        evitando consultas repetidas à API do Scryfall.

        Estrutura do cache:
        {
            "card_name": {
                "price": float,      # Preço em USD
                "timestamp": float   # Quando foi consultado (Unix timestamp)
            }
        }
        """
        try:
            # Verifica se o arquivo de cache existe
            if os.path.exists(self.price_cache_path):
                # Abre e carrega o JSON do disco
                with open(self.price_cache_path, "r", encoding="utf-8") as f:
                    self.price_cache = json.load(f)
                logging.info(f"Cache de preços carregado com {len(self.price_cache)} itens.")
        except Exception as e:
            # Em caso de erro, registra no log e continua com cache vazio
            logging.error(f"Erro ao carregar cache de preços: {e}")
            self.price_cache = {}

    def _save_price_cache(self):
        """
        Salva o cache de preços do Scryfall em arquivo JSON.

        Chamado após cada consulta bem-sucedida à API do Scryfall
        para persistir o cache e reutilizá-lo em futuras execuções.
        """
        try:
            # Salva o dicionário em formato JSON com indentação para legibilidade
            with open(self.price_cache_path, "w", encoding="utf-8") as f:
                json.dump(self.price_cache, f, ensure_ascii=False, indent=2)
            logging.debug(f"Cache Scryfall salvo com {len(self.price_cache)} itens.")
        except Exception as e:
            # Registra erro mas não interrompe a execução
            logging.error(f"Erro ao salvar cache de preços: {e}")

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

    def _validate_card_name(self, edhrec_name):
        """
        Valida e corrige o nome de uma carta do EDHREC contra AllPrintings.json.

        O EDHREC pode retornar nomes abreviados ou ligeiramente diferentes.
        Este método encontra o nome canônico correto e completo da carta.

        Args:
            edhrec_name (str): Nome da carta retornado pelo EDHREC

        Returns:
            str or None: Nome canônico correto da carta, ou None se não encontrada
        """
        # Se os dados não foram carregados ainda, retorna o nome original
        if self._all_cards_data is None:
            return edhrec_name

        # ===================================================================
        # BUSCA EXATA (Case-Insensitive)
        # ===================================================================
        # Primeiro tenta busca exata ignorando maiúsculas/minúsculas
        # Nota: As chaves do dicionário estão em lowercase, mas card['name'] tem capitalização correta
        card_lower = edhrec_name.lower()
        if card_lower in self._all_cards_data:
            canonical_name = self._all_cards_data[card_lower]['name']
            logging.debug(f"✓ Validação exata: '{edhrec_name}' → '{canonical_name}'")
            return canonical_name

        # ===================================================================
        # BUSCA POR CARTAS DE DUPLA FACE
        # ===================================================================
        # Cartas como "Delver of Secrets // Insectile Aberration"
        # O EDHREC pode retornar apenas "Delver of Secrets"
        for card_key, card_data in self._all_cards_data.items():
            card_name = card_data.get('name', '')
            if " // " in card_name:
                # Verifica se o nome do EDHREC corresponde à face frontal
                front_face = card_name.split(" // ")[0].strip()
                if front_face.lower() == edhrec_name.lower():
                    logging.debug(f"✓ Validação dupla face: '{edhrec_name}' → '{card_name}'")
                    return card_name

        # ===================================================================
        # BUSCA POR CARTAS AVENTURA (Adventure)
        # ===================================================================
        # Cartas como "Bonecrusher Giant // Stomp"
        # Alguns comandantes têm estrutura diferente no EDHREC
        if " // " in edhrec_name:
            front_part = edhrec_name.split(" // ")[0].strip()
            for card_key, card_data in self._all_cards_data.items():
                card_name = card_data.get('name', '')
                if card_name.lower().startswith(front_part.lower()):
                    logging.debug(f"✓ Validação aventura: '{edhrec_name}' → '{card_name}'")
                    return card_name

        # ===================================================================
        # NÃO ENCONTRADA
        # ===================================================================
        # Carta não foi encontrada em nenhuma forma
        logging.warning(f"⚠️  Carta '{edhrec_name}' do EDHREC não encontrada em AllPrintings.json")
        # Retorna o nome original para não quebrar o fluxo
        return edhrec_name

    def validate_card_name(self, card_name):
        """
        Valida e corrige o nome de uma carta contra AllPrintings.json.

        Este método é útil para garantir que nomes de cartas inseridos pelo usuário
        ou vindos de fontes externas estejam no formato correto e completo.

        Funcionalidades:
        - Busca exata (case-insensitive)
        - Suporte a cartas de dupla face (ex: "Delver of Secrets // Insectile Aberration")
        - Suporte a cartas aventura (ex: "Bonecrusher Giant // Stomp")

        Args:
            card_name (str): Nome da carta a ser validado

        Returns:
            str: Nome canônico correto da carta (pode ser o mesmo se já estiver correto)

        Examples:
            >>> validate_card_name("sol ring")
            "Sol Ring"

            >>> validate_card_name("delver of secrets")
            "Delver of Secrets // Insectile Aberration"
        """
        return self._validate_card_name(card_name)

    def get_edhrec_recommendations(self, commander_name):
        """
        Busca recomendações do EDHREC para um dado comandante.
        """
        # Trata cartas de dupla face (ex: "Aclazotz // Temple") usando apenas o nome da frente
        if " // " in commander_name:
            commander_name_clean = commander_name.split(" // ")[0]
        else:
            commander_name_clean = commander_name

        # Normaliza o nome: remove acentos e caracteres especiais para criar um slug
        # Ex: "Arwen Undómiel" -> "arwen-undomiel"
        normalized_name = unicodedata.normalize('NFKD', commander_name_clean).encode('ASCII', 'ignore').decode('ASCII')
        base_name = re.sub(r"[^\w\s-]", "", normalized_name.lower()).replace(" ", "-")
        
        # Codifica o nome para garantir que seja seguro para a URL (embora agora deva ser apenas ASCII)
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
            logging.info(f"Recomendações brutas do EDHREC: {len(recommendations)} cartas")

            # ===================================================================
            # VALIDAÇÃO DOS NOMES CONTRA AllPrintings.json
            # ===================================================================
            # CRÍTICO: Valida cada nome para garantir que está correto e completo
            # Isso garante que as buscas de preço funcionarão corretamente
            logging.info(f"Validando nomes das cartas contra AllPrintings.json...")

            recommendations_validated = []
            for edhrec_name in recommendations:
                validated_name = self._validate_card_name(edhrec_name)
                if validated_name:
                    recommendations_validated.append(validated_name)

            logging.info(f"✓ Validação concluída: {len(recommendations_validated)} cartas validadas")
            logging.info(f"Recomendações do EDHREC para {commander_name} buscadas com sucesso. Encontradas {len(recommendations_validated)} cartas.")

            return sorted(recommendations_validated)

        except requests.exceptions.RequestException as e:
            logging.error(f"Erro ao buscar dados do EDHREC para {commander_name}: {e}")
        except json.JSONDecodeError as e:
            # Ocorre se a resposta não for um JSON válido
            logging.error(f"Erro ao decodificar JSON do EDHREC para {commander_name}: {e}")
        except Exception as e:
            # Captura outras exceções inesperadas
            logging.error(f"Erro inesperado ao buscar recomendações do EDHREC: {e}")
        return None

    def get_card_price_from_scryfall(self, card_name):
        """
        Busca o preço em USD de uma carta no Scryfall de forma segura, usando cache configurável.

        O tempo de validade do cache é definido pelo usuário em Configurações > Preferências.
        """
        # Importa o gerenciador de configurações
        from config import config_manager

        current_time = time.time()

        # Obtém o TTL configurado pelo usuário (em segundos)
        cache_ttl = config_manager.get_price_cache_ttl_seconds()

        # Verificar Cache
        if card_name in self.price_cache:
            cache_entry = self.price_cache[card_name]
            cache_age = current_time - cache_entry.get("timestamp", 0)

            # Se o cache ainda é válido
            if cache_age < cache_ttl:
                time_remaining = cache_ttl - cache_age
                hours_left = int(time_remaining / 3600)
                logging.info(f"Preço Scryfall de cache para '{card_name}': US${cache_entry['price']} (cache válido por {hours_left}h)")
                return cache_entry['price']

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
            price_str = prices.get("usd") or prices.get("usd_foil") or prices.get("usd_etched")
            
            # Converte o preço para float, tratando o caso de ser None
            price = float(price_str) if price_str else None
            
            # Atualizar Cache
            if price is not None:
                logging.info(f"Preço encontrado para '{card_name}': US${price:.2f}")
                self.price_cache[card_name] = {"price": price, "timestamp": current_time}
                self._save_price_cache()
            else:
                logging.warning(f"Preço não disponível no Scryfall para '{card_name}'.")
                # Opcional: Cachear falhas por um tempo menor para evitar spam? 
                # Por enquanto, não cacheamos falhas.
                
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

    def get_card_price_brl_from_ligamagic(self, card_name):
        """
        Busca o preço em BRL de uma carta no LigaMagic de forma segura, usando cache.
        Esta é a fonte primária para preços brasileiros.

        Args:
            card_name (str): O nome da carta

        Returns:
            float or None: Preço em BRL ou None se não encontrado/disponível
        """
        if not LIGAMAGIC_AVAILABLE or ligamagic_manager is None:
            logging.warning("LigaMagic não disponível. Use get_card_price_from_scryfall como alternativa.")
            return None

        try:
            price_brl = ligamagic_manager.fetch_price(card_name)
            return price_brl
        except Exception as e:
            logging.error(f"Erro ao buscar preço LigaMagic para '{card_name}': {e}")
            return None

    def get_card_price_brl(self, card_name, prefer_local=True):
        """
        Busca o preço em BRL de uma carta, usando LigaMagic como fonte primária
        e Scryfall + conversão como fallback.

        Args:
            card_name (str): O nome da carta
            prefer_local (bool): Se True, tenta LigaMagic primeiro. Se False, usa apenas Scryfall.

        Returns:
            dict: {"price": float, "source": "ligamagic"|"scryfall", "currency": "BRL"}
                  ou None se não encontrado
        """
        # Tenta LigaMagic primeiro (preços brasileiros diretos)
        if prefer_local and LIGAMAGIC_AVAILABLE:
            price_brl = self.get_card_price_brl_from_ligamagic(card_name)
            if price_brl is not None:
                return {
                    "price": price_brl,
                    "source": "ligamagic",
                    "currency": "BRL"
                }
            logging.info(f"LigaMagic não retornou preço para '{card_name}', tentando Scryfall...")

        # Fallback: Scryfall (USD) + conversão
        price_usd = self.get_card_price_from_scryfall(card_name)
        if price_usd is None:
            return None

        exchange_rate = self.get_usd_to_brl_exchange_rate()
        if exchange_rate is None:
            logging.warning(f"Taxa de câmbio não disponível, retornando preço em USD para '{card_name}'")
            return {
                "price": price_usd,
                "source": "scryfall",
                "currency": "USD"
            }

        price_brl = price_usd * exchange_rate
        return {
            "price": price_brl,
            "source": "scryfall",
            "currency": "BRL"
        }

    def get_usd_to_brl_exchange_rate(self):
        """
        Busca a taxa de câmbio USD para BRL com cache configurável.

        O tempo de validade do cache é definido pelo usuário em Configurações > Preferências.
        """
        # Importa o gerenciador de configurações
        from config import config_manager

        current_time = time.time()

        # Obtém o TTL configurado pelo usuário (em segundos)
        cache_ttl = config_manager.get_exchange_rate_ttl_seconds()

        # Verifica se o cache ainda é válido
        if self._exchange_rate_cache is not None:
            cache_age = current_time - self._exchange_rate_timestamp
            if cache_age < cache_ttl:
                # Calcula tempo restante em minutos
                time_remaining = cache_ttl - cache_age
                minutes_left = int(time_remaining / 60)
                logging.info(f"Taxa de câmbio de cache: 1 USD = {self._exchange_rate_cache:.2f} BRL (válida por {minutes_left}min)")
                return self._exchange_rate_cache

        logging.info("Buscando taxa de câmbio USD para BRL...")
        exchange_rate_url = "https://api.exchangerate-api.com/v4/latest/USD"
        try:
            response = requests.get(exchange_rate_url, timeout=5)
            response.raise_for_status()
            data = response.json()
            if "rates" in data and "BRL" in data["rates"]:
                rate = float(data["rates"]["BRL"])
                logging.info(f"Taxa de câmbio USD-BRL encontrada: 1 USD = {rate:.2f} BRL.")

                # Atualiza o cache
                self._exchange_rate_cache = rate
                self._exchange_rate_timestamp = current_time

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
