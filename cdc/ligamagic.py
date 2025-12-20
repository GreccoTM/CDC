import requests
from bs4 import BeautifulSoup
import re
import json
import os
import time
import logging
import urllib.parse

# Importa Selenium apenas quando necessário
try:
    from ligamagic_selenium import get_selenium_scraper
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    logging.warning("Selenium não disponível. Cartas com JavaScript usarão apenas Scryfall.")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
}

class LigaMagicPriceManager:
    """
    Gerencia a busca de preços de cartas Magic no site LigaMagic.
    Implementa cache persistente com TTL de 12 horas e rate limiting.
    """

    def __init__(self, cache_path=None):
        """
        Inicializa o gerenciador de preços LigaMagic.

        O gerenciador usa cache persistente para armazenar preços já consultados,
        reduzindo a necessidade de fazer requisições repetidas ao site.

        Args:
            cache_path (str, optional): Caminho customizado para o arquivo de cache.
                                       Se None, usa o diretório padrão 'logs/ligamagic_cache.json'
        """
        if cache_path is None:
            # Define o caminho padrão no diretório 'logs'
            script_dir = os.path.dirname(os.path.abspath(__file__))
            logs_dir = os.path.join(script_dir, "logs")

            # Cria o diretório 'logs' se não existir
            if not os.path.exists(logs_dir):
                os.makedirs(logs_dir)

            # Define o caminho completo do arquivo de cache
            self.cache_path = os.path.join(logs_dir, "ligamagic_cache.json")
        else:
            # Usa o caminho fornecido pelo usuário
            self.cache_path = cache_path

        # Dicionário para armazenar o cache em memória
        # Estrutura: {"nome_carta": {"price": float, "timestamp": float, "reason": str}}
        self.cache = {}

        # Carrega o cache existente do disco (se houver)
        self._load_cache()

        # ===================================================================
        # RATE LIMITING (Controle de Taxa de Requisições)
        # ===================================================================
        # Para evitar sobrecarga no servidor do LigaMagic e possíveis bloqueios,
        # implementamos um sistema de rate limiting que garante um intervalo
        # mínimo entre requisições consecutivas

        self._last_request_time = 0  # Timestamp da última requisição feita
        self._min_request_interval = 1.5  # Intervalo mínimo: 1.5 segundos entre requisições

    def _load_cache(self):
        """
        Carrega o cache de preços do arquivo JSON no disco.

        O cache contém informações sobre preços consultados anteriormente,
        incluindo tanto sucessos (preços encontrados) quanto falhas (cartas
        não encontradas ou que usam JavaScript). Isso evita consultas repetidas
        e melhora significativamente a performance do programa.

        Se o arquivo não existir ou houver erro na leitura, inicia com cache vazio.
        """
        try:
            # Verifica se o arquivo de cache existe
            if os.path.exists(self.cache_path):
                # Abre o arquivo em modo leitura com encoding UTF-8 (suporta acentuação)
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    # Carrega o JSON do arquivo para o dicionário em memória
                    self.cache = json.load(f)
                logging.info(f"Cache LigaMagic carregado com {len(self.cache)} itens.")
            # Se o arquivo não existe, o cache permanece vazio (inicializado no __init__)
        except Exception as e:
            # Se houver qualquer erro ao carregar, registra no log e usa cache vazio
            # Isso garante que o programa continue funcionando mesmo com cache corrompido
            logging.error(f"Erro ao carregar cache LigaMagic: {e}")
            self.cache = {}

    def _save_cache(self):
        """
        Salva o cache de preços em arquivo JSON no disco.

        Este método é chamado sempre que um novo preço é consultado (sucesso ou falha),
        garantindo que o cache seja persistido e possa ser reutilizado em futuras execuções.

        Formato do JSON:
        - ensure_ascii=False: Permite caracteres especiais (acentuação)
        - indent=2: Formata o JSON de forma legível para humanos
        """
        try:
            # Abre o arquivo em modo escrita (sobrescreve se existir)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                # Serializa o dicionário em formato JSON e salva no arquivo
                # ensure_ascii=False: Mantém caracteres UTF-8 (é, ã, ç, etc.)
                # indent=2: Adiciona indentação de 2 espaços para facilitar leitura
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
            logging.info(f"Cache LigaMagic salvo com {len(self.cache)} itens.")
        except Exception as e:
            # Registra erro mas não interrompe a execução
            # O programa pode continuar, apenas não terá cache persistido
            logging.error(f"Erro ao salvar cache LigaMagic: {e}")

    @staticmethod
    def _parse_brl_price(price_str):
        """
        Converte string de preço brasileiro para float.

        Args:
            price_str (str): String no formato 'R$ 1.234,56'

        Returns:
            float or None: Valor numérico ou None se conversão falhar
        """
        try:
            clean_str = price_str.replace("R$", "").replace(".", "").replace(",", ".").strip()
            return float(clean_str)
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def _uses_javascript(soup):
        """
        Verifica se a página usa JavaScript para carregar preços.

        Args:
            soup (BeautifulSoup): Objeto soup da página

        Returns:
            bool: True se usa JavaScript
        """
        js_price_container = soup.find("div", class_="container-show-price-mkp")
        return js_price_container is not None

    def _validate_card_result(self, soup, card_name):
        """
        Valida se a página retornada é realmente de uma carta Magic.
        Verifica a presença de elementos típicos de páginas de cartas.

        Args:
            soup (BeautifulSoup): Objeto soup da página
            card_name (str): Nome da carta buscada

        Returns:
            bool: True se parece ser uma página de carta válida
        """
        # Verifica se existem elementos de preço (indicativo de carta)
        price_elements = soup.find_all("div", class_="price-avg")
        if not price_elements:
            logging.warning(f"Nenhum elemento de preço encontrado para '{card_name}'")
            return False

        # Verifica se há referência a "Magic" ou tipos de carta no conteúdo
        page_text = soup.get_text().lower()
        magic_indicators = ["magic", "mana", "card", "carta", "creature", "instant", "sorcery"]
        has_magic_content = any(indicator in page_text for indicator in magic_indicators)

        if not has_magic_content:
            logging.warning(f"Página não parece ser de carta Magic para '{card_name}'")
            return False

        return True

    def fetch_price(self, card_name):
        """
        Busca o preço de uma carta no LigaMagic com cache e validação.
        Cache inclui tanto sucessos quanto falhas para evitar requisições repetidas.

        Args:
            card_name (str): Nome da carta

        Returns:
            float or None: Preço em BRL ou None se não encontrado
        """
        current_time = time.time()

        # ===================================================================
        # VERIFICAÇÃO DE CACHE
        # ===================================================================
        # Importa o gerenciador de configurações para obter o TTL personalizado
        from config import config_manager

        # Obtém o TTL configurado pelo usuário (em segundos)
        cache_ttl = config_manager.get_price_cache_ttl_seconds()

        # Verifica se a carta já está em cache e se ainda é válida
        if card_name in self.cache:
            cache_entry = self.cache[card_name]
            # Calcula há quanto tempo a entrada foi cacheada
            cache_age = current_time - cache_entry.get("timestamp", 0)

            # Se o cache ainda é válido (não expirou)
            if cache_age < cache_ttl:
                price = cache_entry.get('price')
                if price is None:
                    # Falha cacheada - carta não está disponível no LigaMagic
                    hours_ago = int((current_time - cache_entry['timestamp']) / 3600)
                    reason = cache_entry.get('reason', 'unknown')
                    if reason == 'invalid_result':
                        logging.info(f"📋 Cache LigaMagic: '{card_name}' usa JavaScript (verificado há {hours_ago}h) - usando Scryfall")
                    else:
                        logging.info(f"📋 Cache LigaMagic: '{card_name}' não disponível (verificado há {hours_ago}h) - usando Scryfall")
                    return None
                else:
                    # Sucesso cacheado - calcula tempo restante
                    time_remaining = cache_ttl - cache_age
                    hours_remaining = int(time_remaining / 3600)
                    logging.info(f"Preço LigaMagic de cache para '{card_name}': R$ {price:.2f} (cache válido por mais {hours_remaining}h)")
                    return price

        # Rate limiting: aguarda se necessário
        time_since_last_request = current_time - self._last_request_time
        if time_since_last_request < self._min_request_interval:
            wait_time = self._min_request_interval - time_since_last_request
            logging.info(f"Rate limiting: aguardando {wait_time:.1f}s antes de buscar '{card_name}'")
            time.sleep(wait_time)

        logging.info(f"Buscando preço LigaMagic para '{card_name}'")

        try:
            # Monta URL de busca
            url = "https://www.ligamagic.com.br/"
            params = {"view": "cards/search", "card": card_name}

            # Atualiza timestamp da última requisição
            self._last_request_time = time.time()

            # Faz requisição com timeout
            response = requests.get(url, params=params, headers=HEADERS, timeout=15)
            response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')

            # ===================================================================
            # DETECÇÃO DE JAVASCRIPT E VALIDAÇÃO
            # ===================================================================
            # Verifica se a página usa JavaScript para carregar preços
            uses_javascript = self._uses_javascript(soup)
            logging.debug(f"'{card_name}' - Usa JavaScript: {uses_javascript}")

            # Valida se a página parece ser de uma carta Magic
            is_valid = self._validate_card_result(soup, card_name)
            logging.debug(f"'{card_name}' - Validação passou: {is_valid}")

            # Se não validou E não usa JavaScript, é resultado inválido
            # (página errada, carta não existe, etc.)
            if not is_valid and not uses_javascript:
                logging.warning(f"❌ Resultado inválido para '{card_name}' (não validou e não usa JavaScript) - cacheando falha")
                self.cache[card_name] = {
                    "price": None,
                    "timestamp": current_time,
                    "reason": "invalid_result"
                }
                self._save_cache()
                return None

            # Se detectou JavaScript, tenta com Selenium
            if uses_javascript and SELENIUM_AVAILABLE:
                logging.info(f"🌐 '{card_name}' usa JavaScript - tentando com Selenium...")
                try:
                    selenium_scraper = get_selenium_scraper()
                    price = selenium_scraper.fetch_price(card_name)

                    if price is not None:
                        # Sucesso! Cacheia o resultado
                        self.cache[card_name] = {
                            "price": price,
                            "timestamp": current_time,
                            "source": "selenium"
                        }
                        self._save_cache()
                        return price
                    else:
                        # Selenium não encontrou - cacheia falha
                        logging.warning(f"Selenium não encontrou preço para '{card_name}' - cacheando falha")
                        self.cache[card_name] = {
                            "price": None,
                            "timestamp": current_time,
                            "reason": "selenium_not_found"
                        }
                        self._save_cache()
                        return None

                except Exception as e:
                    logging.error(f"Erro ao usar Selenium para '{card_name}': {e}")
                    # Continua para cachear falha abaixo

            elif uses_javascript and not SELENIUM_AVAILABLE:
                logging.warning(f"'{card_name}' usa JavaScript mas Selenium não está disponível - cacheando falha")
                self.cache[card_name] = {
                    "price": None,
                    "timestamp": current_time,
                    "reason": "javascript_no_selenium"
                }
                self._save_cache()
                return None

            # Encontra todos os preços médios (várias edições)
            avg_prices_elements = soup.find_all("div", class_="price-avg")

            valid_prices = []
            for el in avg_prices_elements:
                price_val = self._parse_brl_price(el.text)
                if price_val is not None and price_val > 0:
                    valid_prices.append(price_val)

            if not valid_prices:
                logging.warning(f"Nenhum preço válido encontrado para '{card_name}' - cacheando falha")
                # Cachea a falha para evitar requisições futuras
                self.cache[card_name] = {
                    "price": None,
                    "timestamp": current_time,
                    "reason": "no_prices_found"
                }
                self._save_cache()
                return None

            # Estratégia: menor preço (edição mais barata)
            best_price = min(valid_prices)

            logging.info(f"Preço LigaMagic encontrado para '{card_name}': R$ {best_price:.2f} (de {len(valid_prices)} edições)")

            # Atualiza cache
            self.cache[card_name] = {
                "price": best_price,
                "timestamp": current_time,
                "editions_count": len(valid_prices)
            }
            self._save_cache()

            return best_price

        except requests.exceptions.Timeout:
            logging.error(f"Timeout ao buscar preço LigaMagic para '{card_name}'")
        except requests.exceptions.RequestException as e:
            logging.error(f"Erro de requisição LigaMagic para '{card_name}': {e}")
        except Exception as e:
            logging.error(f"Erro inesperado ao buscar preço LigaMagic para '{card_name}': {e}")

        return None


# Instância singleton para uso no aplicativo
ligamagic_manager = LigaMagicPriceManager()


def test_interactive():
    """Função de teste interativo para debug."""
    print("=== Teste Interativo LigaMagic ===")
    print("Digite 'sair' para encerrar\n")

    manager = LigaMagicPriceManager()

    while True:
        card_name = input("Nome da carta: ").strip()

        if card_name.lower() in ['sair', 'exit', 'quit', '']:
            break

        print(f"\n🔍 Buscando '{card_name}'...")
        price = manager.fetch_price(card_name)

        if price:
            print(f"✅ Preço: R$ {price:.2f}\n")
        else:
            print(f"❌ Preço não encontrado\n")

        print("-" * 50)


if __name__ == "__main__":
    # Testes automatizados
    print("=== Testes Automatizados ===\n")
    manager = LigaMagicPriceManager()

    test_cards = [
        "Sol Ring",
        "Black Lotus",
        "Island",
        "Lightning Bolt",
        "Mana Crypt"
    ]

    for card in test_cards:
        price = manager.fetch_price(card)
        if price:
            print(f"✅ {card}: R$ {price:.2f}")
        else:
            print(f"❌ {card}: Não encontrado")

    # Teste interativo
    print("\n" + "=" * 50)
    choice = input("\nExecutar teste interativo? (s/n): ").strip().lower()
    if choice == 's':
        test_interactive()
