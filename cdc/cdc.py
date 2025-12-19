import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
import logging

from mtg_data import mtg_data_manager
import commander_rules

# Configuração do logging
log_file_path = "cdc.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file_path, mode='a', encoding='utf-8'),
        # logging.StreamHandler()  # Logs visíveis apenas na GUI
    ],
    force=True
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
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ajuda", menu=help_menu)
        help_menu.add_command(label="Sobre", command=self._show_about)

    def _show_about(self):
        about_text = (
            "Commander Deck Check (CDC)\n"
            "Versão 1.0\n\n"
            "Desenvolvido por: GreccoTM\n\n"
            "Este projeto utiliza dados de:\n"
            "- MTGJSON\n"
            "- EDHREC\n"
            "- Scryfall API"
        )
        messagebox.showinfo("Sobre", about_text)

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
        """ Vincula os eventos da UI aos métodos da aplicação. """
        self.ui.commander_listbox.bind("<<ListboxSelect>>", self._on_commander_select)
        ttk.Button(self.ui.collection_buttons_frame, text="Carregar do Arquivo", command=self._load_cards_from_file).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(self.ui.collection_buttons_frame, text="Identificar Comandantes", command=self._identify_commanders).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(self.ui.collection_buttons_frame, text="Comparar", command=self._compare_with_collection).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(self.ui.collection_buttons_frame, text="Ver Logs", command=self.ui._show_logs).pack(side=tk.RIGHT, padx=5)
        
        self.ui.stop_button.config(command=self._stop_comparison)

    def _stop_comparison(self):
        """ Sinaliza para parar a busca de preços. """
        if not self.stop_fetching_event.is_set():
            self.stop_fetching_event.set()
            self._update_status("Parando consulta... Aguarde finalizar a requisição atual.")
            self.ui.stop_button.config(state=tk.DISABLED)

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
        """ Carrega uma lista de cartas de um arquivo de texto, com verificação de segurança. """
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
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
                self.ui.collection_text.delete("1.0", tk.END)
                self.ui.collection_text.insert("1.0", content)
            self._update_status(f"Lista de cartas carregada de: {file_path}")
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

        usd_to_brl_rate = mtg_data_manager.get_usd_to_brl_exchange_rate() or 5.0
        if usd_to_brl_rate == 5.0:
            self.ui.comparison_results_text.insert(tk.END, "Aviso: Usando taxa de câmbio padrão (R$5.00/US$1.00).\n")

        self.ui.progress_bar["maximum"] = len(cards_you_need)
        self.stop_fetching_event.clear()
        self.ui.stop_button.config(state=tk.NORMAL)
        
        price_fetching_thread = threading.Thread(target=self._price_fetching_worker, args=(sorted(cards_you_need), usd_to_brl_rate))
        price_fetching_thread.start()
        self.root.after(100, self._process_queue)

    def _price_fetching_worker(self, cards_to_fetch, usd_to_brl_rate):
        total_cost = 0.0
        for i, card_name in enumerate(cards_to_fetch):
            if self.stop_fetching_event.is_set():
                self.queue.put(("stopped", None, None))
                break
                
            self.queue.put(("progress", i + 1, card_name))
            usd_price = mtg_data_manager.get_card_price_from_scryfall(card_name)
            
            display_price = "Preço não disponível"
            if usd_price:
                brl_price = usd_price * usd_to_brl_rate
                total_cost += brl_price
                display_price = f"R$ {brl_price:.2f}"
            
            self.queue.put(("card_price", card_name, display_price))
            self.queue.put(("total_cost", total_cost, None))
            
        if not self.stop_fetching_event.is_set():
            self.queue.put(("done", None, None))

    def _process_queue(self):
        try:
            while True:
                msg_type, value1, value2 = self.queue.get_nowait()
                if msg_type == "progress":
                    self.ui.progress_bar["value"] = value1
                    self._update_status(f"Buscando preço para '{value2}' ({value1}/{self.ui.progress_bar['maximum']})...")
                elif msg_type == "card_price":
                    self.ui.comparison_results_text.insert(tk.END, f"{value1} ({value2})\n")
                elif msg_type == "total_cost":
                    self.total_missing_cost = value1
                    self.ui.total_cost_label.config(text=f"Custo Total Estimado: R$ {self.total_missing_cost:.2f}")
                elif msg_type == "done":
                    self.ui.progress_bar["value"] = self.ui.progress_bar["maximum"]
                    self._update_status(f"Comparação completa. Custo total: R$ {self.total_missing_cost:.2f}.")
                    self.ui.stop_button.config(state=tk.DISABLED)
                    return
                elif msg_type == "stopped":
                    self._update_status(f"Comparação interrompida pelo usuário. Custo parcial: R$ {self.total_missing_cost:.2f}.")
                    self.ui.stop_button.config(state=tk.DISABLED)
                    return
        except queue.Empty:
            self.root.after(100, self._process_queue)

if __name__ == "__main__":
    root = tk.Tk()
    app = CommanderDeckCheckApp(root)
    root.mainloop()
