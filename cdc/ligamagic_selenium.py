"""
Módulo para buscar preços no LigaMagic usando Selenium (para páginas com JavaScript).
Usado apenas como fallback quando o scraping simples não funciona.
"""

import logging
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class LigaMagicSeleniumScraper:
    """
    Scraper usando Selenium para cartas que usam JavaScript.
    Mantém o navegador aberto para reutilização.
    """

    def __init__(self):
        self.driver = None
        self._init_driver()

    def _init_driver(self):
        """Inicializa o navegador Chrome em modo headless."""
        try:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            logging.info("🌐 Selenium Chrome driver inicializado com sucesso")

        except Exception as e:
            logging.error(f"❌ Erro ao inicializar Selenium: {e}")
            self.driver = None

    def fetch_price(self, card_name):
        """
        Busca o preço de uma carta usando Selenium.

        Args:
            card_name (str): Nome da carta

        Returns:
            float or None: Menor preço em BRL ou None
        """
        if not self.driver:
            logging.error("Selenium driver não disponível")
            return None

        try:
            # Monta URL
            url = f"https://www.ligamagic.com.br/?view=cards/card&card={card_name}"
            logging.info(f"🔍 Selenium: Buscando '{card_name}' em {url}")

            # Acessa página
            self.driver.get(url)

            # Aguarda até 10 segundos para elementos de preço carregarem
            wait = WebDriverWait(self.driver, 10)

            # Espera pelo container de preços
            wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "price-mkp"))
            )

            # Aguarda um pouco para garantir que tudo carregou
            time.sleep(1)

            # Busca todos os elementos de preço
            price_elements = self.driver.find_elements(By.CSS_SELECTOR, "div.price-mkp div.min div.price")

            if not price_elements:
                logging.warning(f"⚠️  Selenium: Nenhum preço encontrado para '{card_name}'")
                return None

            # Extrai e converte preços
            prices = []
            for el in price_elements:
                price_text = el.text.strip()
                try:
                    # Remove "R$", pontos e troca vírgula por ponto
                    clean_price = price_text.replace("R$", "").replace(".", "").replace(",", ".").strip()
                    price_value = float(clean_price)
                    if price_value > 0:
                        prices.append(price_value)
                except (ValueError, AttributeError):
                    continue

            if not prices:
                logging.warning(f"⚠️  Selenium: Preços inválidos para '{card_name}'")
                return None

            # Retorna o menor preço
            best_price = min(prices)
            logging.info(f"✅ Selenium: Preço encontrado para '{card_name}': R$ {best_price:.2f} (de {len(prices)} edições)")
            return best_price

        except TimeoutException:
            logging.warning(f"⏱️  Selenium: Timeout aguardando preços para '{card_name}'")
            return None

        except WebDriverException as e:
            logging.error(f"❌ Selenium WebDriver error para '{card_name}': {e}")
            return None

        except Exception as e:
            logging.error(f"❌ Selenium erro inesperado para '{card_name}': {e}")
            return None

    def close(self):
        """Fecha o navegador."""
        if self.driver:
            try:
                self.driver.quit()
                logging.info("🔒 Selenium driver fechado")
            except Exception as e:
                logging.error(f"Erro ao fechar Selenium: {e}")
            finally:
                self.driver = None

    def __del__(self):
        """Garante que o navegador será fechado ao destruir o objeto."""
        self.close()


# Instância singleton (será criada apenas quando necessário)
_selenium_scraper = None


def get_selenium_scraper():
    """Retorna a instância singleton do scraper Selenium."""
    global _selenium_scraper
    if _selenium_scraper is None:
        _selenium_scraper = LigaMagicSeleniumScraper()
    return _selenium_scraper


if __name__ == "__main__":
    # Teste
    scraper = LigaMagicSeleniumScraper()

    test_cards = [
        "Spirited Companion",
        "Selfless Spirit",
        "Sol Ring"
    ]

    for card in test_cards:
        print(f"\n{'='*60}")
        price = scraper.fetch_price(card)
        if price:
            print(f"✅ {card}: R$ {price:.2f}")
        else:
            print(f"❌ {card}: Não encontrado")

    scraper.close()
