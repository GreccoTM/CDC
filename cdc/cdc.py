import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
import logging
import os
from PIL import Image, ImageTk

from mtg_data import mtg_data_manager
import commander_rules

# ============================================================================
# CONFIGURAÇÃO DE LOGGING
# ============================================================================
# Cria o diretório 'logs' se não existir
# Este diretório armazenará todos os logs e caches do programa
script_dir = os.path.dirname(os.path.abspath(__file__))
logs_dir = os.path.join(script_dir, "logs")
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)  # Cria o diretório recursivamente

# Define o caminho do arquivo de log principal
log_file_path = os.path.join(logs_dir, "cdc.log")

# Configura o sistema de logging
# level=DEBUG: Registra TODAS as mensagens (DEBUG, INFO, WARNING, ERROR, CRITICAL)
#              Útil para diagnosticar problemas e entender o fluxo do programa
# format: Define o formato das mensagens de log (data/hora - nível - mensagem)
# FileHandler: Salva os logs em arquivo (mode='a' = append, não sobrescreve)
# encoding='utf-8': Suporta caracteres especiais e acentuação
logging.basicConfig(
    level=logging.DEBUG,  # ALTERADO PARA DEBUG: mostra logs detalhados
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file_path, mode='a', encoding='utf-8'),
        # logging.StreamHandler()  # Descomente para ver logs no console também
    ],
    force=True  # Força reconfiguração mesmo se já foi configurado antes
)


class AppUI:
    """
    Responsável pela criação e gerenciamento de todos os componentes da interface gráfica.
    """
    def __init__(self, root):
        self.root = root
        self.stop_button = None # Initialize reference
        self._create_menu()
        self._create_widgets()


    def _create_menu(self):
        """
        Cria a barra de menu principal do programa.

        Menus disponíveis:
        - Configurações: Permite ajustar preferências do programa
        - Ajuda: Informações sobre o programa
        """
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # ===================================================================
        # MENU CONFIGURAÇÕES
        # ===================================================================
        config_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Configurações", menu=config_menu)
        config_menu.add_command(label="Preferências...", command=self._show_settings)

        # ===================================================================
        # MENU AJUDA
        # ===================================================================
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ajuda", menu=help_menu)
        help_menu.add_command(label="Sobre", command=self._show_about)

    def _show_about(self):
        """Mostra janela Sobre com informações do projeto e links clicáveis."""
        about_window = tk.Toplevel(self.root)
        about_window.title("Sobre")
        about_window.geometry("500x350")
        about_window.resizable(False, False)

        # Centraliza a janela
        about_window.transient(self.root)
        about_window.grab_set()

        # Frame principal
        main_frame = ttk.Frame(about_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Text widget para conteúdo com links
        text_widget = tk.Text(main_frame, wrap=tk.WORD, borderwidth=0,
                             highlightthickness=0, height=15, cursor="arrow")
        text_widget.pack(fill=tk.BOTH, expand=True)

        # Conteúdo
        text_widget.insert(tk.END, "Commander Deck Check (CDC)\n", "title")
        text_widget.insert(tk.END, "Versão 1.2\n\n", "version")
        text_widget.insert(tk.END, "Desenvolvido por: GreccoTM\n\n", "normal")
        text_widget.insert(tk.END, "Este projeto utiliza dados de:\n\n", "normal")

        # Links com descrições
        links = [
            ("MTGJSON", "https://mtgjson.com/"),
            ("EDHREC", "https://edhrec.com/"),
            ("Scryfall", "https://scryfall.com/"),
            ("LigaMagic", "https://www.ligamagic.com.br/")
        ]

        # Configuração de tags de estilo (antes de inserir)
        text_widget.tag_config("title", font=("TkDefaultFont", 16, "bold"))
        text_widget.tag_config("version", font=("TkDefaultFont", 10, "italic"))
        text_widget.tag_config("normal", font=("TkDefaultFont", 10))

        # Insere links com tags únicas e configuração
        for i, (name, url) in enumerate(links):
            tag_name = f"link_{i}"

            text_widget.insert(tk.END, "• ")
            text_widget.insert(tk.END, name, tag_name)
            text_widget.insert(tk.END, "\n")

            # Configura estilo para este link específico
            text_widget.tag_config(tag_name, foreground="blue", underline=1)

            # Adiciona eventos para este link específico
            text_widget.tag_bind(tag_name, "<Enter>",
                               lambda e, w=text_widget: w.config(cursor="hand2"))
            text_widget.tag_bind(tag_name, "<Leave>",
                               lambda e, w=text_widget: w.config(cursor="arrow"))
            text_widget.tag_bind(tag_name, "<Button-1>",
                               lambda e, u=url: self._open_url(u))

        text_widget.config(state=tk.DISABLED)

        # Botão Fechar
        close_button = ttk.Button(main_frame, text="Fechar",
                                  command=about_window.destroy)
        close_button.pack(pady=10)

    def _open_url(self, url):
        """Abre URL no navegador padrão."""
        import webbrowser
        webbrowser.open(url)

    def _show_settings(self):
        """
        Mostra janela de Configurações onde o usuário pode ajustar preferências.

        Configurações disponíveis:
        - Tempo de cache de preços de cartas (horas)
        - Tempo de cache de taxa de câmbio (minutos)
        """
        # Importa o gerenciador de configurações
        from config import config_manager

        # ===================================================================
        # CRIAÇÃO DA JANELA
        # ===================================================================
        settings_window = tk.Toplevel(self.root)
        settings_window.title("Configurações do CDC")

        # Define tamanho maior para garantir que todos os elementos apareçam
        settings_window.geometry("600x450")
        settings_window.resizable(True, True)  # Permite redimensionar para debug
        settings_window.minsize(550, 400)  # Tamanho mínimo

        # Centraliza a janela e torna modal
        settings_window.transient(self.root)
        settings_window.grab_set()

        # Frame principal com padding
        main_frame = ttk.Frame(settings_window, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Força atualização do layout
        settings_window.update_idletasks()

        # Título
        title_label = ttk.Label(main_frame, text="Preferências do CDC",
                               font=('TkDefaultFont', 14, 'bold'))
        title_label.pack(pady=(0, 20))

        # ===================================================================
        # SEÇÃO: CACHE DE PREÇOS
        # ===================================================================
        cache_frame = ttk.LabelFrame(main_frame, text="Cache de Preços das Cartas",
                                     padding="10")
        cache_frame.pack(fill=tk.X, pady=(0, 15))

        # Linha com label e campo de entrada
        price_cache_row = ttk.Frame(cache_frame)
        price_cache_row.pack(fill=tk.X)

        ttk.Label(price_cache_row, text="Tempo de validade do cache:").pack(side=tk.LEFT)

        # Campo de entrada (Spinbox para facilitar)
        price_cache_var = tk.IntVar(value=config_manager.get("price_cache_hours", 12))
        price_cache_spinbox = ttk.Spinbox(price_cache_row, from_=1, to=168,
                                          textvariable=price_cache_var,
                                          width=10)
        price_cache_spinbox.pack(side=tk.LEFT, padx=5)

        ttk.Label(price_cache_row, text="horas").pack(side=tk.LEFT)

        # Texto explicativo
        price_cache_help = ttk.Label(cache_frame,
                                     text="Define por quanto tempo os preços consultados\n"
                                          "ficam salvos em cache (1 a 168 horas = 1 semana)",
                                     foreground="gray", font=('TkDefaultFont', 9))
        price_cache_help.pack(pady=(5, 0))

        # ===================================================================
        # SEÇÃO: CACHE DE TAXA DE CÂMBIO
        # ===================================================================
        exchange_frame = ttk.LabelFrame(main_frame, text="Cache de Taxa de Câmbio (USD → BRL)",
                                       padding="10")
        exchange_frame.pack(fill=tk.X, pady=(0, 15))

        # Linha com label e campo de entrada
        exchange_rate_row = ttk.Frame(exchange_frame)
        exchange_rate_row.pack(fill=tk.X)

        ttk.Label(exchange_rate_row, text="Tempo de validade do cache:").pack(side=tk.LEFT)

        # Campo de entrada (Spinbox)
        exchange_rate_var = tk.IntVar(value=config_manager.get("exchange_rate_cache_minutes", 10))
        exchange_rate_spinbox = ttk.Spinbox(exchange_rate_row, from_=1, to=1440,
                                            textvariable=exchange_rate_var,
                                            width=10)
        exchange_rate_spinbox.pack(side=tk.LEFT, padx=5)

        ttk.Label(exchange_rate_row, text="minutos").pack(side=tk.LEFT)

        # Texto explicativo
        exchange_rate_help = ttk.Label(exchange_frame,
                                       text="Define por quanto tempo a taxa de conversão USD→BRL\n"
                                            "fica salva em cache (1 a 1440 minutos = 24 horas)",
                                       foreground="gray", font=('TkDefaultFont', 9))
        exchange_rate_help.pack(pady=(5, 0))

        # ===================================================================
        # BOTÕES DE AÇÃO
        # ===================================================================
        # Separador visual antes dos botões
        separator = ttk.Separator(main_frame, orient='horizontal')
        separator.pack(fill=tk.X, pady=(15, 10))

        # Frame para os botões
        button_frame = ttk.Frame(main_frame, relief=tk.RIDGE, borderwidth=2)
        button_frame.pack(fill=tk.X, pady=(10, 0), padx=5)

        def save_settings():
            """Salva as configurações e fecha a janela."""
            # Obtém os valores dos campos
            price_hours = price_cache_var.get()
            exchange_minutes = exchange_rate_var.get()

            # Tenta salvar usando o config_manager
            success, message = config_manager.update_settings(price_hours, exchange_minutes)

            if success:
                # Sucesso: mostra mensagem e fecha
                messagebox.showinfo("Configurações Salvas", message)
                logging.info(f"Usuário atualizou configurações: Cache preços={price_hours}h, Taxa câmbio={exchange_minutes}min")
                settings_window.destroy()
            else:
                # Erro de validação: mostra mensagem e mantém janela aberta
                messagebox.showerror("Erro de Validação", message)

        def restore_defaults():
            """Restaura os valores padrão."""
            if messagebox.askyesno("Restaurar Padrões",
                                  "Deseja restaurar as configurações padrão?\n\n"
                                  "• Cache de preços: 12 horas\n"
                                  "• Cache de taxa de câmbio: 10 minutos"):
                price_cache_var.set(12)
                exchange_rate_var.set(10)

        # Botão Restaurar Padrões (à esquerda)
        restore_button = ttk.Button(button_frame, text="Restaurar Padrões",
                                   command=restore_defaults)
        restore_button.pack(side=tk.LEFT, padx=10, pady=10)

        # Botão Cancelar (à direita)
        cancel_button = ttk.Button(button_frame, text="Cancelar",
                                   command=settings_window.destroy, width=12)
        cancel_button.pack(side=tk.RIGHT, padx=10, pady=10)

        # Botão Salvar (à direita, antes do Cancelar)
        save_button = ttk.Button(button_frame, text="Salvar",
                                command=save_settings, width=12)
        save_button.pack(side=tk.RIGHT, padx=10, pady=10)

        # Força atualização final do layout
        settings_window.update_idletasks()

    def _create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        main_v_pane = ttk.PanedWindow(main_frame, orient=tk.VERTICAL)
        main_v_pane.pack(fill=tk.BOTH, expand=True)

        top_h_pane = ttk.PanedWindow(main_v_pane, orient=tk.HORIZONTAL)
        main_v_pane.add(top_h_pane, weight=7)

        self._create_left_pane(top_h_pane)
        self._create_right_pane(top_h_pane)
        self._create_bottom_pane(main_v_pane)

        self.status_bar = ttk.Frame(self.root)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_label = ttk.Label(self.status_bar, text="Pronto", relief=tk.SUNKEN, anchor=tk.W, padding=5)
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)



    def _show_logs(self):
        log_viewer_window, log_text_widget = self._create_log_viewer_window()
        log_viewer_window.grab_set()  # Make it modal

        try:
            with open(log_file_path, "r", encoding="utf-8") as f:
                logs = f.read()
                log_text_widget.insert(tk.END, logs)
        except FileNotFoundError:
            log_text_widget.insert(tk.END, "O arquivo de log não foi encontrado.")
        except Exception as e:
            log_text_widget.insert(tk.END, f"Erro ao ler o arquivo de log: {e}")

        log_text_widget.config(state=tk.DISABLED) # Make text read-only
        log_text_widget.see(tk.END) # Scroll to the end
        
    def _create_log_viewer_window(self):
        log_viewer = tk.Toplevel(self.root)
        log_viewer.title("Logs da Aplicação")
        log_viewer.geometry("800x600")

        log_text_frame = ttk.Frame(log_viewer, padding="10")
        log_text_frame.pack(fill=tk.BOTH, expand=True)

        log_text = tk.Text(log_text_frame, wrap=tk.WORD, borderwidth=0, highlightthickness=0)
        log_scrollbar = ttk.Scrollbar(log_text_frame, orient="vertical", command=log_text.yview)
        log_text.config(yscrollcommand=log_scrollbar.set)
        log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.BOTH)

        buttons_frame = ttk.Frame(log_viewer, padding="10")
        buttons_frame.pack(fill=tk.X)

        clear_logs_button = ttk.Button(buttons_frame, text="Limpar Logs", command=lambda: self._clear_logs(log_text))
        clear_logs_button.pack(side=tk.LEFT, padx=5)

        return log_viewer, log_text

    def _clear_logs(self, log_text_widget):
        # Clear the Text widget
        log_text_widget.config(state=tk.NORMAL) # Enable editing to clear
        log_text_widget.delete("1.0", tk.END)
        log_text_widget.config(state=tk.DISABLED) # Disable editing again

        # Clear the log file
        try:
            with open(log_file_path, "w", encoding="utf-8") as f:
                f.write("")
            logging.info("Logs limpos pelo usuário.")
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível limpar o arquivo de log: {e}")



    def _create_left_pane(self, parent):
        left_pane = ttk.Frame(parent, padding=5)
        parent.add(left_pane, weight=1)
        left_pane.grid_rowconfigure(0, weight=1)
        left_pane.grid_columnconfigure(0, weight=1)

        commander_frame = ttk.LabelFrame(left_pane, text="Comandantes Disponíveis", padding="10")
        commander_frame.grid(row=0, column=0, sticky="nsew", pady=5)
        commander_frame.grid_rowconfigure(0, weight=1)
        commander_frame.grid_columnconfigure(0, weight=1)

        self.commander_listbox = tk.Listbox(commander_frame, borderwidth=0, highlightthickness=0)
        commander_scrollbar = ttk.Scrollbar(commander_frame, orient="vertical", command=self.commander_listbox.yview)
        self.commander_listbox.config(yscrollcommand=commander_scrollbar.set)
        self.commander_listbox.grid(row=0, column=0, sticky="nsew")
        commander_scrollbar.grid(row=0, column=1, sticky="ns")

    def _create_right_pane(self, parent):
        right_pane = ttk.Frame(parent, padding=5)
        parent.add(right_pane, weight=1)
        right_pane.grid_rowconfigure(0, weight=1)
        right_pane.grid_columnconfigure(0, weight=1)

        right_v_pane = ttk.PanedWindow(right_pane, orient=tk.VERTICAL)
        right_v_pane.grid(row=0, column=0, sticky="nsew")

        edhrec_frame = ttk.LabelFrame(right_v_pane, text="Recomendações EDHREC", padding="10")
        right_v_pane.add(edhrec_frame, weight=1)
        edhrec_frame.grid_rowconfigure(0, weight=1)
        edhrec_frame.grid_columnconfigure(0, weight=1)

        self.edhrec_text = tk.Text(edhrec_frame, wrap=tk.WORD, borderwidth=0, highlightthickness=0)
        edhrec_scrollbar = ttk.Scrollbar(edhrec_frame, orient="vertical", command=self.edhrec_text.yview)
        self.edhrec_text.config(yscrollcommand=edhrec_scrollbar.set)
        self.edhrec_text.grid(row=0, column=0, sticky="nsew")
        edhrec_scrollbar.grid(row=0, column=1, sticky="ns")

        collection_frame = ttk.LabelFrame(right_v_pane, text="Lista de Cartas (Deck/Coleção)", padding="10")
        right_v_pane.add(collection_frame, weight=1)
        collection_frame.grid_rowconfigure(0, weight=1)
        collection_frame.grid_columnconfigure(0, weight=1)

        self.collection_text = tk.Text(collection_frame, wrap=tk.WORD, borderwidth=0, highlightthickness=0)
        collection_scrollbar = ttk.Scrollbar(collection_frame, orient="vertical", command=self.collection_text.yview)
        self.collection_text.config(yscrollcommand=collection_scrollbar.set)
        self.collection_text.grid(row=0, column=0, sticky="nsew")
        collection_scrollbar.grid(row=0, column=1, sticky="ns")

        self.collection_buttons_frame = ttk.Frame(collection_frame)
        self.collection_buttons_frame.grid(row=1, column=0, sticky="ew", pady=5)

    def _create_bottom_pane(self, parent):
        comparison_results_frame = ttk.LabelFrame(parent, text="Resultados da Comparação", padding="10")
        parent.add(comparison_results_frame, weight=3)
        comparison_results_frame.grid_rowconfigure(0, weight=1)
        comparison_results_frame.grid_columnconfigure(0, weight=1)

        self.comparison_results_text = tk.Text(comparison_results_frame, wrap=tk.WORD, borderwidth=0, highlightthickness=0)
        comparison_scrollbar = ttk.Scrollbar(comparison_results_frame, orient="vertical", command=self.comparison_results_text.yview)
        self.comparison_results_text.config(yscrollcommand=comparison_scrollbar.set)
        self.comparison_results_text.grid(row=0, column=0, sticky="nsew")
        comparison_scrollbar.grid(row=0, column=1, sticky="ns")

        progress_total_frame = ttk.Frame(comparison_results_frame, padding="5")
        progress_total_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
        progress_total_frame.grid_columnconfigure(0, weight=1)

        style = ttk.Style(self.root)
        style.configure("Custom.Horizontal.TProgressbar", troughcolor="lightgray", background="steelblue")
        self.progress_bar = ttk.Progressbar(progress_total_frame, orient="horizontal", mode="determinate", style="Custom.Horizontal.TProgressbar")
        self.progress_bar.grid(row=0, column=0, sticky="ew", pady=2)
        
        self.stop_button = ttk.Button(progress_total_frame, text="Parar", state=tk.DISABLED)
        self.stop_button.grid(row=0, column=1, padx=5)

        self.total_cost_label = ttk.Label(progress_total_frame, text="Custo Total Estimado: R$ 0.00", anchor=tk.E)
        self.total_cost_label.grid(row=0, column=2, sticky="e", padx=5)


class CommanderDeckCheckApp:
    """
    Classe principal da aplicação, responsável pela lógica de negócio e orquestração.
    """
    def __init__(self, root):
        self.root = root
        self.root.title("Commander Deck Check (CDC)")
        self.root.geometry("1600x960")

        self.style = ttk.Style(self.root)
        self.style.theme_use("clam")

        self.selected_commander = None
        self.edhrec_recommendations = []
        self.total_missing_cost = 0.0
        self.stop_fetching_event = threading.Event()

        self.ui = AppUI(self.root)
        self._bind_events()
        self.queue = queue.Queue()
        self.ui.status_label.config(text="Pronto")

        # Carrega favicons
        self.favicons = self._load_favicons()

        # Carregamento inicial dos dados
        self._start_loading_data()

    def _start_loading_data(self):
        """ Inicia o carregamento dos dados em uma thread separada. """
        self._update_status("Carregando base de dados de cartas... Por favor, aguarde.")
        self._set_ui_state(tk.DISABLED)
        loading_thread = threading.Thread(target=self._loading_worker)
        loading_thread.start()
        self.root.after(100, self._check_loading_queue)

    def _loading_worker(self):
        """ Worker para carregar os dados. """
        try:
            mtg_data_manager._load_all_printings()
            self.queue.put(("loading_complete", None, None))
        except Exception as e:
            self.queue.put(("loading_error", str(e), None))

    def _check_loading_queue(self):
        """ Verifica a fila de mensagens para o carregamento inicial. """
        try:
            while True:
                msg_type, value1, _ = self.queue.get_nowait()
                if msg_type == "loading_complete":
                    self._update_status("Base de dados carregada. Pronto.")
                    self._set_ui_state(tk.NORMAL)
                    return
                elif msg_type == "loading_error":
                    self._handle_error("Falha crítica ao carregar base de dados.", value1, exit_on_ok=True)
                    return
        except queue.Empty:
            self.root.after(100, self._check_loading_queue)

    def _set_ui_state(self, state):
        """ Habilita ou desabilita os botões de interação. """
        for child in self.ui.collection_buttons_frame.winfo_children():
            try:
                child.config(state=state)
            except tk.TclError:
                pass

    def _bind_events(self):
        """
        Vincula os eventos da UI aos métodos da aplicação.
        Cria todos os botões de ação e conecta-os às suas respectivas funções.
        """
        # Vincula evento de seleção de comandante na listbox
        self.ui.commander_listbox.bind("<<ListboxSelect>>", self._on_commander_select)

        # Botões principais de ação (lado esquerdo)
        ttk.Button(self.ui.collection_buttons_frame, text="Carregar do Arquivo", command=self._load_cards_from_file).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(self.ui.collection_buttons_frame, text="Identificar Comandantes", command=self._identify_commanders).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(self.ui.collection_buttons_frame, text="Comparar", command=self._compare_with_collection).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        # Botões utilitários (lado direito)
        ttk.Button(self.ui.collection_buttons_frame, text="Limpar Cache", command=self._clear_price_cache).pack(side=tk.RIGHT, padx=5)
        ttk.Button(self.ui.collection_buttons_frame, text="Ver Logs", command=self.ui._show_logs).pack(side=tk.RIGHT, padx=5)

        # Configura o botão de parar comparação
        self.ui.stop_button.config(command=self._stop_comparison)

    def _load_favicons(self):
        """
        Carrega os favicons do LigaMagic e Scryfall de arquivos locais.
        Os favicons devem estar na mesma pasta do script com os nomes:
        - @ligamagic.ico (favicon do LigaMagic)
        - @scryfall.ico (favicon do Scryfall)

        Returns:
            dict: Dicionário com PhotoImage dos favicons {'ligamagic': PhotoImage, 'scryfall': PhotoImage}
                  Retorna dicionário vazio se não conseguir carregar os favicons.
        """
        favicons = {}

        # Obtém o diretório onde o script está localizado
        script_dir = os.path.dirname(os.path.abspath(__file__))

        # Dicionário mapeando o nome da fonte para o arquivo local
        # Nota: Os arquivos devem ter @ no início do nome
        favicon_files = {
            'ligamagic': '@ligamagic.ico',  # Favicon do LigaMagic (fonte brasileira)
            'scryfall': '@scryfall.ico'      # Favicon do Scryfall (fonte internacional)
        }

        # Processa cada favicon
        for source, filename in favicon_files.items():
            # Monta o caminho completo do arquivo de favicon
            favicon_path = os.path.join(script_dir, filename)

            # Verifica se o arquivo existe antes de tentar carregar
            if not os.path.exists(favicon_path):
                logging.warning(f"Arquivo de favicon não encontrado: {favicon_path}")
                continue

            # Tenta carregar e processar o favicon
            try:
                # Abre a imagem usando PIL (Python Imaging Library)
                img = Image.open(favicon_path)

                # Redimensiona para 16x16 pixels (tamanho padrão de favicon para melhor visualização)
                # LANCZOS é um filtro de alta qualidade para redimensionamento
                img = img.resize((16, 16), Image.Resampling.LANCZOS)

                # Converte para RGBA (Red, Green, Blue, Alpha) para suportar transparência
                # Isso garante que o fundo transparente do favicon seja preservado
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')

                # Cria um PhotoImage do Tkinter a partir da imagem PIL
                # IMPORTANTE: Precisamos manter a referência ao PhotoImage no dicionário
                # caso contrário, o garbage collector do Python irá destruí-lo
                photo = ImageTk.PhotoImage(img)

                # Armazena o PhotoImage no dicionário com a chave da fonte
                favicons[source] = photo
                logging.info(f"Favicon {source} carregado com sucesso de {filename}")

            except Exception as e:
                # Se houver qualquer erro ao carregar ou processar o favicon,
                # registra no log mas não interrompe a execução do programa
                logging.error(f"Erro ao carregar favicon {source} de {favicon_path}: {e}")

        return favicons

    def _stop_comparison(self):
        """
        Sinaliza para parar a busca de preços em andamento.
        Define um evento que a thread de busca verifica periodicamente.
        """
        if not self.stop_fetching_event.is_set():
            self.stop_fetching_event.set()
            self._update_status("Parando consulta... Aguarde finalizar a requisição atual.")
            self.ui.stop_button.config(state=tk.DISABLED)

    def _clear_price_cache(self):
        """
        Limpa o cache de preços (LigaMagic e Scryfall) com confirmação dupla.

        Este método implementa um sistema de segurança com duas confirmações:
        1. Primeira confirmação: Pergunta se o usuário realmente quer limpar
        2. Segunda confirmação: Aviso final antes da ação irreversível

        O cache inclui:
        - Cache do LigaMagic (preços em BRL)
        - Cache do Scryfall (preços em USD)
        - Taxa de câmbio armazenada
        """
        # ===================================================================
        # PRIMEIRA CONFIRMAÇÃO
        # ===================================================================
        # Pergunta inicial ao usuário
        primeira_resposta = messagebox.askyesno(
            "Limpar Cache de Preços",
            "Deseja realmente limpar o cache de preços?\n\n"
            "Isso irá remover:\n"
            "• Cache do LigaMagic (preços brasileiros)\n"
            "• Cache do Scryfall (preços internacionais)\n"
            "• Taxa de câmbio armazenada\n\n"
            "Os preços terão que ser consultados novamente nas próximas buscas.",
            icon='warning'
        )

        # Se o usuário cancelou na primeira confirmação, aborta
        if not primeira_resposta:
            self._update_status("Limpeza de cache cancelada.")
            logging.info("Usuário cancelou a limpeza de cache na primeira confirmação.")
            return

        # ===================================================================
        # SEGUNDA CONFIRMAÇÃO (Confirmação Final)
        # ===================================================================
        # Aviso mais enfático para garantir que o usuário tem certeza
        segunda_resposta = messagebox.askyesno(
            "⚠️ CONFIRMAÇÃO FINAL",
            "ATENÇÃO: Esta ação é irreversível!\n\n"
            "Você tem CERTEZA ABSOLUTA que deseja limpar o cache?\n\n"
            "Todo o histórico de preços será perdido e\n"
            "as próximas consultas serão mais lentas.",
            icon='warning',
            default='no'  # Por segurança, o padrão é "Não"
        )

        # Se o usuário cancelou na segunda confirmação, aborta
        if not segunda_resposta:
            self._update_status("Limpeza de cache cancelada pelo usuário.")
            logging.info("Usuário cancelou a limpeza de cache na segunda confirmação.")
            return

        # ===================================================================
        # LIMPEZA DO CACHE (Confirmado duas vezes)
        # ===================================================================
        try:
            logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
            arquivos_removidos = []
            arquivos_nao_encontrados = []

            # Lista de arquivos de cache para remover
            cache_files = [
                os.path.join(logs_dir, "ligamagic_cache.json"),  # Cache LigaMagic
                os.path.join(logs_dir, "price_cache.json")        # Cache Scryfall
            ]

            # Remove cada arquivo de cache
            for cache_file in cache_files:
                if os.path.exists(cache_file):
                    os.remove(cache_file)
                    arquivos_removidos.append(os.path.basename(cache_file))
                    logging.info(f"Cache removido: {cache_file}")
                else:
                    arquivos_nao_encontrados.append(os.path.basename(cache_file))
                    logging.info(f"Cache não encontrado (já estava vazio): {cache_file}")

            # Limpa também o cache em memória
            # Reinicia o cache do LigaMagic
            from ligamagic import ligamagic_manager
            ligamagic_manager.cache = {}

            # Reinicia o cache do Scryfall
            mtg_data_manager.price_cache = {}
            mtg_data_manager._exchange_rate_cache = None
            mtg_data_manager._exchange_rate_timestamp = 0

            # Monta mensagem de sucesso
            mensagem = "✅ Cache limpo com sucesso!\n\n"
            if arquivos_removidos:
                mensagem += f"Arquivos removidos:\n• " + "\n• ".join(arquivos_removidos)
            if arquivos_nao_encontrados:
                mensagem += f"\n\nArquivos já vazios:\n• " + "\n• ".join(arquivos_nao_encontrados)

            messagebox.showinfo("Cache Limpo", mensagem)
            self._update_status("Cache de preços limpo com sucesso.")
            logging.info("Cache de preços limpo com sucesso pelo usuário.")

        except Exception as e:
            # Se houver erro durante a limpeza, registra e informa o usuário
            erro_msg = f"Erro ao limpar cache: {e}"
            logging.error(erro_msg)
            messagebox.showerror("Erro ao Limpar Cache", erro_msg)
            self._update_status("Erro ao limpar cache.")

    def _update_status(self, message):
        self.ui.status_label.config(text=message)
        self.root.update_idletasks()

    def _handle_error(self, user_message, error, exit_on_ok=False):
        """ Centraliza o tratamento de erros, logando e exibindo uma mensagem para o usuário. """
        logging.error(f"{user_message} - Erro: {error}")
        messagebox.showerror("Erro", f"{user_message}\n\nDetalhes: {error}")
        if exit_on_ok:
            self.root.destroy()

    def _load_cards_from_file(self):
        """
        Carrega uma lista de cartas de um arquivo de texto, com verificação de segurança.

        Após carregar o arquivo, valida todos os nomes das cartas contra AllPrintings.json
        para garantir que os nomes estejam corretos e completos antes de exibir na interface.
        """
        file_path = filedialog.askopenfilename(
            title="Selecione o arquivo da lista de cartas",
            filetypes=[("Arquivos de Texto", "*.txt"), ("Todos os arquivos", "*.*")]
        )
        if not file_path:
            return  # O usuário cancelou a seleção

        # Medida de segurança: verificar se o arquivo é um .txt
        if not file_path.lower().endswith(".txt"):
            self._handle_error("Apenas arquivos .txt são permitidos.", "Seleção de arquivo inválida.")
            return

        try:
            # Carrega o conteúdo do arquivo
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            # ===================================================================
            # VALIDAÇÃO DOS NOMES DAS CARTAS CONTRA AllPrintings.json
            # ===================================================================
            logging.info(f"Validando nomes das cartas do arquivo: {file_path}")

            # Divide o conteúdo em linhas
            lines = content.strip().split('\n')
            validated_lines = []
            changes_count = 0

            for line in lines:
                line = line.strip()

                # Ignora linhas vazias
                if not line:
                    validated_lines.append("")
                    continue

                # Extrai a quantidade e o nome da carta
                # Formato esperado: "1 Nome da Carta" ou "Nome da Carta"
                parts = line.split(None, 1)  # Split no primeiro espaço

                if len(parts) == 2 and parts[0].isdigit():
                    # Tem quantidade: "1 Sol Ring"
                    quantity = parts[0]
                    card_name = parts[1]
                elif len(parts) == 1:
                    # Só o nome: "Sol Ring"
                    quantity = None
                    card_name = parts[0]
                else:
                    # Linha em formato desconhecido, mantém original
                    validated_lines.append(line)
                    continue

                # Valida o nome da carta contra AllPrintings.json
                validated_name = mtg_data_manager.validate_card_name(card_name)

                # Se o nome mudou, registra a correção
                if validated_name != card_name:
                    logging.info(f"✓ Nome corrigido: '{card_name}' → '{validated_name}'")
                    changes_count += 1

                # Reconstrói a linha com o nome validado
                if quantity is not None:
                    validated_lines.append(f"{quantity} {validated_name}")
                else:
                    validated_lines.append(validated_name)

            # Junta as linhas validadas
            validated_content = '\n'.join(validated_lines)

            # Atualiza a interface com o conteúdo validado
            self.ui.collection_text.delete("1.0", tk.END)
            self.ui.collection_text.insert("1.0", validated_content)

            # Mensagem de status
            if changes_count > 0:
                self._update_status(f"Lista carregada e validada: {changes_count} nomes corrigidos")
                logging.info(f"✅ Validação concluída: {changes_count} cartas tiveram nomes corrigidos")
            else:
                self._update_status(f"Lista de cartas carregada de: {file_path}")
                logging.info("✅ Validação concluída: todos os nomes já estavam corretos")

        except IOError as e:
            self._handle_error("Erro de E/S ao carregar o arquivo.", e)
        except Exception as e:
            self._handle_error("Ocorreu um erro inesperado ao carregar o arquivo.", e)

    def _identify_commanders(self):
        self._update_status("Identificando comandantes...")
        card_list_raw = self.ui.collection_text.get("1.0", tk.END).strip()
        if not card_list_raw:
            self._update_status("A lista de cartas (coleção) está vazia.")
            return

        card_names = {line.strip() for line in card_list_raw.split("\n") if line.strip()}
        self.ui.commander_listbox.delete(0, tk.END)
        
        eligible_commanders = self._get_eligible_commanders(card_names)

        if eligible_commanders:
            for commander in sorted(eligible_commanders):
                self.ui.commander_listbox.insert(tk.END, commander)
            self._update_status(f"Encontrado(s) {len(eligible_commanders)} comandante(s) elegível(is).")
        else:
            self.ui.commander_listbox.insert(tk.END, "Nenhum comandante elegível encontrado.")
            self._update_status("Nenhum comandante elegível encontrado na lista.")
            
    def _get_eligible_commanders(self, card_names):
        """ Itera sobre a lista de nomes e retorna os comandantes elegíveis. """
        eligible_commanders = set()
        for name in card_names:
            card_details = mtg_data_manager.get_card_details(name)
            if card_details and mtg_data_manager.is_eligible_commander(card_details):
                eligible_commanders.add(card_details["name"])
        return eligible_commanders

    def _on_commander_select(self, event):
        selection = self.ui.commander_listbox.curselection()
        if not selection:
            return

        selected_commander_name = self.ui.commander_listbox.get(selection[0])
        if selected_commander_name == self.selected_commander:
            return

        self.selected_commander = selected_commander_name
        self._update_status(f"Comandante selecionado: {self.selected_commander}")
        self.ui.edhrec_text.delete("1.0", tk.END)
        self.ui.edhrec_text.insert(tk.END, f"Buscando recomendações para {self.selected_commander}...")
        
        recommendations = mtg_data_manager.get_edhrec_recommendations(self.selected_commander)
        
        self.ui.edhrec_text.delete("1.0", tk.END)
        if recommendations is not None:
            self.edhrec_recommendations = recommendations
            if recommendations:
                self.ui.edhrec_text.insert(tk.END, f"Principais Recomendações para {self.selected_commander}:\n\n" + "\n".join(recommendations))
                self._update_status(f"Encontrada(s) {len(recommendations)} recomendações.")
            else:
                self.ui.edhrec_text.insert(tk.END, f"Nenhuma recomendação específica encontrada para {self.selected_commander}.")
                self._update_status("Nenhuma recomendação encontrada.")
        else:
            self._handle_error(f"Não foi possível buscar recomendações para {self.selected_commander}.", "Verifique a conexão ou o nome do comandante.")


    def _compare_with_collection(self):
        self._update_status("Preparando comparação...")
        self.ui.comparison_results_text.delete("1.0", tk.END)
        self.ui.progress_bar["value"] = 0
        self.total_missing_cost = 0.0

        if not self.edhrec_recommendations:
            self.ui.comparison_results_text.insert(tk.END, "Erro: Busque as recomendações do EDHREC primeiro.\n")
            return

        collection_raw = self.ui.collection_text.get("1.0", tk.END).strip()
        if not collection_raw:
            self.ui.comparison_results_text.insert(tk.END, "Erro: A sua coleção está vazia.\n")
            return

        my_collection = {line.strip() for line in collection_raw.split("\n") if line.strip()}
        edhrec_set = set(self.edhrec_recommendations)

        cards_you_have = edhrec_set.intersection(my_collection)
        cards_you_need = edhrec_set.difference(my_collection)

        self.ui.comparison_results_text.insert(tk.END, "--- Cartas que Você Possui ---\n" + ("\n".join(sorted(cards_you_have)) if cards_you_have else "Nenhuma.") + "\n")
        self.ui.comparison_results_text.insert(tk.END, "\n--- Cartas que Você Precisa ---\n")

        if not cards_you_need:
            self.ui.comparison_results_text.insert(tk.END, "Nenhuma.\n")
            self._update_status("Comparação completa: Você possui todas as cartas recomendadas.")
            return

        self.ui.comparison_results_text.insert(tk.END, "Buscando preços em fontes brasileiras (LigaMagic) e internacionais (Scryfall)...\n\n")

        self.ui.progress_bar["maximum"] = len(cards_you_need)
        self.stop_fetching_event.clear()
        self.ui.stop_button.config(state=tk.NORMAL)

        price_fetching_thread = threading.Thread(target=self._price_fetching_worker, args=(sorted(cards_you_need),))
        price_fetching_thread.start()
        self.root.after(100, self._process_queue)

    def _price_fetching_worker(self, cards_to_fetch):
        total_cost = 0.0
        for i, card_name in enumerate(cards_to_fetch):
            if self.stop_fetching_event.is_set():
                self.queue.put(("stopped", None, None))
                break

            self.queue.put(("progress", i + 1, card_name))

            # Usa o novo método integrado que tenta LigaMagic primeiro
            price_result = mtg_data_manager.get_card_price_brl(card_name, prefer_local=True)

            if price_result:
                brl_price = price_result['price']
                source = price_result['source']
                total_cost += brl_price
                # Envia dados estruturados para exibição com favicon
                self.queue.put(("card_price", card_name, brl_price, source))
            else:
                # Sem preço disponível
                self.queue.put(("card_price", card_name, None, None))

            self.queue.put(("total_cost", total_cost, None))

        if not self.stop_fetching_event.is_set():
            self.queue.put(("done", None, None))

    def _process_queue(self):
        """
        Processa mensagens da fila de threads.

        Este método é chamado periodicamente pela thread principal do Tkinter
        para processar mensagens enviadas pela thread de busca de preços.
        Isso é necessário porque apenas a thread principal pode atualizar a GUI.

        Tipos de mensagens processadas:
        - "progress": Atualiza a barra de progresso
        - "card_price": Exibe o preço de uma carta com favicon
        - "total_cost": Atualiza o custo total
        - "done": Finaliza o processo de busca
        - "stopped": Indica interrupção pelo usuário
        """
        try:
            # Tenta processar todas as mensagens disponíveis na fila
            while True:
                # get_nowait() retorna imediatamente ou lança queue.Empty
                # Não bloqueia a thread principal
                msg = self.queue.get_nowait()
                msg_type = msg[0]  # Primeiro elemento é o tipo da mensagem

                # --------------------------------------------------------
                # ATUALIZAÇÃO DE PROGRESSO
                # --------------------------------------------------------
                if msg_type == "progress":
                    # Extrai o índice atual e o nome da carta
                    value1, value2 = msg[1], msg[2]
                    # Atualiza a barra de progresso visual
                    self.ui.progress_bar["value"] = value1
                    # Atualiza o texto de status mostrando qual carta está sendo processada
                    self._update_status(f"Buscando preço para '{value2}' ({value1}/{self.ui.progress_bar['maximum']})...")

                # --------------------------------------------------------
                # EXIBIÇÃO DE PREÇO COM FAVICON
                # --------------------------------------------------------
                elif msg_type == "card_price":
                    # Extrai informações da carta
                    card_name, price, source = msg[1], msg[2], msg[3]

                    # Insere o nome da carta no widget de texto
                    self.ui.comparison_results_text.insert(tk.END, f"{card_name} (")

                    if price is not None and source:
                        # Exibe o preço formatado em BRL
                        self.ui.comparison_results_text.insert(tk.END, f"R$ {price:.2f} ")

                        # Tenta inserir o favicon da fonte de dados
                        if source in self.favicons:
                            # image_create() insere uma imagem no widget Text
                            # Usa o PhotoImage armazenado no dicionário self.favicons
                            self.ui.comparison_results_text.image_create(tk.END, image=self.favicons[source])
                        else:
                            # Fallback: Se o favicon não estiver disponível, usa texto
                            # Isso garante que sempre haverá alguma indicação da fonte
                            source_tag = "[LigaMagic]" if source == "ligamagic" else "[Scryfall]"
                            self.ui.comparison_results_text.insert(tk.END, source_tag)
                    else:
                        # Caso não tenha sido possível obter o preço
                        self.ui.comparison_results_text.insert(tk.END, "Preço não disponível")

                    # Fecha o parêntese e adiciona nova linha
                    self.ui.comparison_results_text.insert(tk.END, ")\n")

                # --------------------------------------------------------
                # ATUALIZAÇÃO DO CUSTO TOTAL
                # --------------------------------------------------------
                elif msg_type == "total_cost":
                    value1 = msg[1]
                    self.total_missing_cost = value1
                    # Atualiza o label que mostra o custo total acumulado
                    self.ui.total_cost_label.config(text=f"Custo Total Estimado: R$ {self.total_missing_cost:.2f}")

                # --------------------------------------------------------
                # FINALIZAÇÃO NORMAL DO PROCESSO
                # --------------------------------------------------------
                elif msg_type == "done":
                    # Preenche a barra de progresso completamente
                    self.ui.progress_bar["value"] = self.ui.progress_bar["maximum"]
                    # Atualiza o status final
                    self._update_status(f"Comparação completa. Custo total: R$ {self.total_missing_cost:.2f}.")
                    # Desabilita o botão "Parar" (já terminou)
                    self.ui.stop_button.config(state=tk.DISABLED)
                    return  # Encerra o processamento da fila

                # --------------------------------------------------------
                # INTERRUPÇÃO PELO USUÁRIO
                # --------------------------------------------------------
                elif msg_type == "stopped":
                    self._update_status(f"Comparação interrompida pelo usuário. Custo parcial: R$ {self.total_missing_cost:.2f}.")
                    self.ui.stop_button.config(state=tk.DISABLED)
                    return  # Encerra o processamento da fila

        except queue.Empty:
            # Se a fila está vazia, agenda uma nova verificação após 100ms
            # Isso mantém a GUI responsiva sem consumir muita CPU
            self.root.after(100, self._process_queue)

if __name__ == "__main__":
    root = tk.Tk()
    app = CommanderDeckCheckApp(root)
    root.mainloop()
