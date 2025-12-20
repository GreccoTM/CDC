"""
Módulo de gerenciamento de configurações do CDC (Commander Deck Check).

Este módulo é responsável por:
- Carregar configurações do arquivo JSON
- Salvar configurações alteradas pelo usuário
- Fornecer valores padrão caso o arquivo não exista
- Validar os valores fornecidos pelo usuário

Arquivo de configurações: logs/config.json
"""

import json
import os
import logging

# Valores padrão das configurações
DEFAULT_CONFIG = {
    # ========================================================================
    # CACHE DE PREÇOS (LigaMagic e Scryfall)
    # ========================================================================
    # Tempo em HORAS que um preço consultado permanece válido em cache
    # Valor padrão: 12 horas
    # Valores aceitos: 1 a 168 horas (1 semana)
    "price_cache_hours": 12,

    # ========================================================================
    # CACHE DE TAXA DE CÂMBIO (USD → BRL)
    # ========================================================================
    # Tempo em MINUTOS que a taxa de câmbio permanece válida em cache
    # Valor padrão: 10 minutos
    # Valores aceitos: 1 a 1440 minutos (24 horas)
    "exchange_rate_cache_minutes": 10,
}


class ConfigManager:
    """
    Gerenciador de configurações do programa.

    Responsável por carregar, validar, salvar e fornecer acesso às
    configurações personalizáveis pelo usuário.
    """

    def __init__(self, config_path=None):
        """
        Inicializa o gerenciador de configurações.

        Args:
            config_path (str, optional): Caminho customizado para o arquivo de configurações.
                                        Se None, usa 'logs/config.json'
        """
        if config_path is None:
            # Define o caminho padrão no diretório 'logs'
            script_dir = os.path.dirname(os.path.abspath(__file__))
            logs_dir = os.path.join(script_dir, "logs")

            # Cria o diretório 'logs' se não existir
            if not os.path.exists(logs_dir):
                os.makedirs(logs_dir)

            # Define o caminho completo do arquivo de configurações
            self.config_path = os.path.join(logs_dir, "config.json")
        else:
            self.config_path = config_path

        # Dicionário com as configurações atuais
        self.config = {}

        # Carrega as configurações do disco (ou usa padrões se não existir)
        self._load_config()

    def _load_config(self):
        """
        Carrega as configurações do arquivo JSON.

        Se o arquivo não existir ou estiver corrompido, usa valores padrão
        e cria o arquivo com os padrões.
        """
        try:
            # Verifica se o arquivo de configurações existe
            if os.path.exists(self.config_path):
                # Abre e carrega o JSON
                with open(self.config_path, "r", encoding="utf-8") as f:
                    loaded_config = json.load(f)

                # Mescla com valores padrão (caso faltem chaves no arquivo)
                self.config = {**DEFAULT_CONFIG, **loaded_config}
                logging.info(f"Configurações carregadas de {self.config_path}")
            else:
                # Arquivo não existe, usa valores padrão
                self.config = DEFAULT_CONFIG.copy()
                logging.info("Arquivo de configurações não encontrado, usando valores padrão")

                # Cria o arquivo com os valores padrão
                self._save_config()

        except Exception as e:
            # Em caso de erro, usa valores padrão
            logging.error(f"Erro ao carregar configurações: {e}")
            self.config = DEFAULT_CONFIG.copy()

    def _save_config(self):
        """
        Salva as configurações atuais no arquivo JSON.

        Formato do JSON:
        - ensure_ascii=False: Permite caracteres UTF-8
        - indent=2: Formata de forma legível
        """
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            logging.info(f"Configurações salvas em {self.config_path}")
        except Exception as e:
            logging.error(f"Erro ao salvar configurações: {e}")

    def get(self, key, default=None):
        """
        Obtém o valor de uma configuração.

        Args:
            key (str): Chave da configuração
            default: Valor padrão se a chave não existir

        Returns:
            Valor da configuração ou default
        """
        return self.config.get(key, default)

    def set(self, key, value):
        """
        Define o valor de uma configuração e salva no arquivo.

        Args:
            key (str): Chave da configuração
            value: Novo valor
        """
        self.config[key] = value
        self._save_config()

    def get_price_cache_ttl_seconds(self):
        """
        Retorna o TTL do cache de preços em SEGUNDOS.

        Returns:
            int: Tempo em segundos (horas * 3600)
        """
        hours = self.config.get("price_cache_hours", 12)
        return hours * 3600  # Converte horas para segundos

    def get_exchange_rate_ttl_seconds(self):
        """
        Retorna o TTL do cache de taxa de câmbio em SEGUNDOS.

        Returns:
            int: Tempo em segundos (minutos * 60)
        """
        minutes = self.config.get("exchange_rate_cache_minutes", 10)
        return minutes * 60  # Converte minutos para segundos

    def update_settings(self, price_cache_hours, exchange_rate_minutes):
        """
        Atualiza múltiplas configurações de uma vez.

        Valida os valores antes de salvar.

        Args:
            price_cache_hours (int): Horas de cache de preços (1-168)
            exchange_rate_minutes (int): Minutos de cache de câmbio (1-1440)

        Returns:
            tuple: (success: bool, message: str)
        """
        # ===================================================================
        # VALIDAÇÃO DOS VALORES
        # ===================================================================

        # Valida cache de preços (1 hora a 1 semana)
        try:
            price_hours = int(price_cache_hours)
            if price_hours < 1 or price_hours > 168:
                return False, "Cache de preços deve estar entre 1 e 168 horas (1 semana)"
        except (ValueError, TypeError):
            return False, "Cache de preços deve ser um número válido"

        # Valida cache de taxa de câmbio (1 minuto a 24 horas)
        try:
            exchange_minutes = int(exchange_rate_minutes)
            if exchange_minutes < 1 or exchange_minutes > 1440:
                return False, "Cache de taxa de câmbio deve estar entre 1 e 1440 minutos (24 horas)"
        except (ValueError, TypeError):
            return False, "Cache de taxa de câmbio deve ser um número válido"

        # ===================================================================
        # ATUALIZAÇÃO E SALVAMENTO
        # ===================================================================
        self.config["price_cache_hours"] = price_hours
        self.config["exchange_rate_cache_minutes"] = exchange_minutes
        self._save_config()

        logging.info(f"Configurações atualizadas: Cache preços={price_hours}h, Taxa câmbio={exchange_minutes}min")
        return True, "Configurações salvas com sucesso!"


# Instância singleton para uso no aplicativo
config_manager = ConfigManager()
