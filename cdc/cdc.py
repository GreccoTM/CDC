# -*- coding: utf-8 -*-

# Importações de bibliotecas padrão do Python
import tkinter as tk
from tkinter import ttk, filedialog
import time
import threading
import queue

# Importações de módulos locais da aplicação
import mtg_data
import commander_rules

class CommanderDeckCheckApp:
    """
    Classe principal da aplicação Commander Deck Check (CDC).

    Esta classe é responsável por inicializar e gerenciar a interface gráfica do usuário (GUI),
    bem como por orquestrar as interações entre os diferentes componentes da aplicação,
    como a entrada de lista de decks, identificação de comandantes, validação de regras
    e comparação com a coleção do usuário.
    """
    def __init__(self, root):
        """
        Construtor da classe CommanderDeckCheckApp.

        Args:
            root (tk.Tk): O widget raiz da aplicação Tkinter, a janela principal.
        """
        self.root = root
        self.root.title("Commander Deck Check (CDC)")
        self.root.geometry("1600x960")

        # Configura um tema visual moderno para a aplicação usando ttk.
        self.style = ttk.Style(self.root)
        self.style.theme_use('clam')

        # Variáveis para armazenar o estado da aplicação.
        self.selected_commander = None  # Armazena o nome do comandante atualmente selecionado.
        self.edhrec_recommendations = []  # Armazena a lista de recomendações do EDHREC.

        # Cria todos os widgets (elementos visuais) da interface.
        self._create_widgets()
        # Define o texto inicial da barra de status.
        self.status_bar.config(text="Pronto")

    def _create_widgets(self):
        """
        Cria e organiza todos os widgets na janela principal.

        Este método constrói a interface do usuário usando um layout de PanedWindow aninhado,
        o que permite que o usuário redimensione as seções da interface tanto na horizontal
        quanto na vertical para melhor visualização.
        """
        # Frame principal que conterá todos os outros widgets.
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- PanedWindow Vertical Principal ---
        # Divide a janela em uma seção superior e uma inferior, redimensionáveis.
        main_v_pane = ttk.PanedWindow(main_frame, orient=tk.VERTICAL)
        main_v_pane.pack(fill=tk.BOTH, expand=True)

        # --- Painel Horizontal Superior ---
        # Este painel é adicionado à seção superior do painel vertical.
        top_h_pane = ttk.PanedWindow(main_v_pane, orient=tk.HORIZONTAL)
        main_v_pane.add(top_h_pane, weight=7) # 'weight=7' para dar 70% da altura

        # --- Coluna Esquerda (no Painel Superior) ---
        left_pane = ttk.Frame(top_h_pane, padding=5)
        top_h_pane.add(left_pane, weight=1)
        # Configura as linhas da grade para expandir verticalmente.
        left_pane.grid_rowconfigure(0, weight=1)
        left_pane.grid_columnconfigure(0, weight=1)

        # Seção de Seleção do Comandante
        commander_frame = ttk.LabelFrame(left_pane, text="Comandantes Disponíveis", padding="10")
        commander_frame.grid(row=0, column=0, sticky="nsew", pady=5)
        commander_frame.grid_rowconfigure(0, weight=1)
        commander_frame.grid_columnconfigure(0, weight=1)

        self.commander_listbox = tk.Listbox(commander_frame, borderwidth=0, highlightthickness=0)
        commander_scrollbar = ttk.Scrollbar(commander_frame, orient="vertical", command=self.commander_listbox.yview)
        self.commander_listbox.config(yscrollcommand=commander_scrollbar.set)
        self.commander_listbox.grid(row=0, column=0, sticky="nsew")
        commander_scrollbar.grid(row=0, column=1, sticky="ns")
        self.commander_listbox.bind("<<ListboxSelect>>", self._on_commander_select)

        # --- Coluna Direita (no Painel Superior) ---
        right_pane = ttk.Frame(top_h_pane, padding=5)
        top_h_pane.add(right_pane, weight=1)
        # Configura as linhas da grade para expandir verticalmente.
        right_pane.grid_rowconfigure(0, weight=1) # Dando peso para a PanedWindow
        right_pane.grid_columnconfigure(0, weight=1)

        # PanedWindow Vertical para Recomendações EDHREC e Lista de Cartas
        right_v_pane = ttk.PanedWindow(right_pane, orient=tk.VERTICAL)
        right_v_pane.grid(row=0, column=0, sticky="nsew")

        # Seção de Recomendações EDHREC
        edhrec_frame = ttk.LabelFrame(right_v_pane, text="Recomendações EDHREC", padding="10")
        right_v_pane.add(edhrec_frame, weight=1) # Ocupa 50% da altura do right_v_pane
        edhrec_frame.grid_rowconfigure(0, weight=1)
        edhrec_frame.grid_columnconfigure(0, weight=1)

        self.edhrec_text = tk.Text(edhrec_frame, wrap=tk.WORD, borderwidth=0, highlightthickness=0)
        edhrec_scrollbar = ttk.Scrollbar(edhrec_frame, orient="vertical", command=self.edhrec_text.yview)
        self.edhrec_text.config(yscrollcommand=edhrec_scrollbar.set)
        self.edhrec_text.grid(row=0, column=0, sticky="nsew")
        edhrec_scrollbar.grid(row=0, column=1, sticky="ns")

        # Seção de Lista de Cartas (Deck/Coleção)
        collection_frame = ttk.LabelFrame(right_v_pane, text="Lista de Cartas (Deck/Coleção)", padding="10")
        right_v_pane.add(collection_frame, weight=1) # Ocupa 50% da altura do right_v_pane
        collection_frame.grid_rowconfigure(0, weight=1)
        collection_frame.grid_columnconfigure(0, weight=1)

        self.collection_text = tk.Text(collection_frame, wrap=tk.WORD, borderwidth=0, highlightthickness=0)
        collection_scrollbar = ttk.Scrollbar(collection_frame, orient="vertical", command=self.collection_text.yview)
        self.collection_text.config(yscrollcommand=collection_scrollbar.set)
        self.collection_text.grid(row=0, column=0, sticky="nsew")
        collection_scrollbar.grid(row=0, column=1, sticky="ns")

        collection_buttons_frame = ttk.Frame(collection_frame)
        collection_buttons_frame.grid(row=1, column=0, sticky="ew", pady=5)
        ttk.Button(collection_buttons_frame, text="Carregar do Arquivo", command=self._load_cards_from_file).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(collection_buttons_frame, text="Identificar Comandantes", command=self._identify_commanders).pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        ttk.Button(collection_buttons_frame, text="Comparar", command=self._compare_with_collection).pack(side=tk.RIGHT, padx=5, fill=tk.X, expand=True)


        # --- Painel Inferior para Resultados da Comparação ---
        # Adicionado diretamente à seção inferior do painel vertical.
        comparison_results_frame = ttk.LabelFrame(main_v_pane, text="Resultados da Comparação", padding="10")
        main_v_pane.add(comparison_results_frame, weight=3) # 'weight=3' para dar 30% da altura
        comparison_results_frame.grid_rowconfigure(0, weight=1)
        comparison_results_frame.grid_columnconfigure(0, weight=1)

        self.comparison_results_text = tk.Text(comparison_results_frame, wrap=tk.WORD, borderwidth=0, highlightthickness=0)
        comparison_scrollbar = ttk.Scrollbar(comparison_results_frame, orient="vertical", command=self.comparison_results_text.yview)
        self.comparison_results_text.config(yscrollcommand=comparison_scrollbar.set)
        self.comparison_results_text.grid(row=0, column=0, sticky="nsew")
        comparison_scrollbar.grid(row=0, column=1, sticky="ns")

        # --- Seção de Progresso e Total ---
        # Frame para conter a barra de progresso e o total de gastos
        progress_total_frame = ttk.Frame(comparison_results_frame, padding="5")
        progress_total_frame.grid(row=1, column=0, columnspan=2, sticky="ew")
        progress_total_frame.grid_columnconfigure(0, weight=1)

        self.style.configure("Custom.Horizontal.TProgressbar", troughcolor='lightgray', background='steelblue')
        self.progress_bar = ttk.Progressbar(progress_total_frame, orient="horizontal", mode="determinate", style="Custom.Horizontal.TProgressbar")
        self.progress_bar.grid(row=0, column=0, sticky="ew", pady=2)

        self.total_cost_label = ttk.Label(progress_total_frame, text="Custo Total Estimado: R$ 0.00", anchor=tk.E)
        self.total_cost_label.grid(row=0, column=1, sticky="e", padx=5)


        # --- Barra de Status ---
        self.status_bar = ttk.Label(self.root, text="Pronto", relief=tk.SUNKEN, anchor=tk.W, padding=5)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Fila para comunicação entre threads
        self.queue = queue.Queue()

    def _update_status(self, message):
        """Atualiza o texto na barra de status para fornecer feedback ao usuário."""
        self.status_bar.config(text=message)
        self.root.update_idletasks() # Força a atualização da GUI imediatamente.

    def _load_cards_from_file(self):
        """
        Abre uma caixa de diálogo para o usuário selecionar um arquivo de texto
        contendo uma lista de cartas (para deck ou coleção) e o carrega na área de texto da coleção.
        """
        file_path = filedialog.askopenfilename(
            title="Selecione o arquivo da lista de cartas",
            filetypes=[("Arquivos de Texto", "*.txt"), ("Todos os arquivos", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.collection_text.delete("1.0", tk.END)
                    self.collection_text.insert("1.0", content)
                self._update_status(f"Lista de cartas carregada de: {file_path}")
            except Exception as e:
                self._update_status(f"Erro ao carregar arquivo de cartas: {e}")



    def _identify_commanders(self):
        """
        Identifica os comandantes elegíveis a partir da lista de cartas fornecida pelo usuário (agora da Minha Coleção).
        """
        self._update_status("Identificando comandantes...")
        card_list_raw = self.collection_text.get("1.0", tk.END).strip()
        if not card_list_raw:
            self._update_status("A lista de cartas (coleção) está vazia.")
            return

        card_names = [line.strip() for line in card_list_raw.split('\n') if line.strip()]
        self.commander_listbox.delete(0, tk.END)
        eligible_commanders = []

        for name in card_names:
            # Lógica simples para extrair o nome da carta, ignorando quantidade e edição.
            parsed_name = ' '.join(name.split(' ')[1:]) if name.split(' ')[0].isdigit() else name
            parsed_name = parsed_name.split('(')[0].strip()
            
            card_details = mtg_data.get_card_details(parsed_name)
            if card_details and mtg_data.is_eligible_commander(card_details):
                eligible_commanders.append(card_details["name"])

        if eligible_commanders:
            # Remove duplicatas e ordena a lista de comandantes.
            for commander in sorted(list(set(eligible_commanders))):
                self.commander_listbox.insert(tk.END, commander)
            self._update_status(f"Encontrado(s) {len(eligible_commanders)} comandante(s) elegível(is).")
        else:
            self.commander_listbox.insert(tk.END, "Nenhum comandante elegível encontrado.")
            self._update_status("Nenhum comandante elegível encontrado na lista.")

    def _on_commander_select(self, event):
        """
        Chamado quando o usuário seleciona um comandante na lista.
        Busca e exibe as recomendações do EDHREC para o comandante selecionado.
        """
        selection = self.commander_listbox.curselection()
        if not selection:
            return
        
        index = selection[0]
        selected_commander_name = self.commander_listbox.get(index)
        # Evita buscas repetidas se o mesmo comandante for clicado novamente.
        if selected_commander_name == self.selected_commander:
            return

        self.selected_commander = selected_commander_name
        self._update_status(f"Comandante selecionado: {self.selected_commander}")
        
        self.edhrec_text.delete("1.0", tk.END)
        self.edhrec_recommendations = []

        self.edhrec_text.insert(tk.END, f"Buscando recomendações do EDHREC para {self.selected_commander}...\n")
        self.root.update_idletasks()

        recommendations = mtg_data.get_edhrec_recommendations(self.selected_commander)

        self.edhrec_text.delete("1.0", tk.END) # Limpa a mensagem de "Buscando...".
        if recommendations:
            self.edhrec_recommendations = recommendations
            self.edhrec_text.insert(tk.END, f"Principais Recomendações para {self.selected_commander}:\n\n")
            self.edhrec_text.insert(tk.END, "\n".join(f"- {card}" for card in recommendations))
            self._update_status(f"Encontrada(s) {len(recommendations)} recomendações para {self.selected_commander}.")
        elif recommendations is None:
            self.edhrec_text.insert(tk.END, f"Não foi possível buscar recomendações para {self.selected_commander}.")
            self._update_status(f"Falha ao buscar recomendações para {self.selected_commander}.")
        else: # Lista vazia
            self.edhrec_text.insert(tk.END, f"Nenhuma recomendação específica encontrada para {self.selected_commander}.")
            self._update_status(f"Nenhuma recomendação encontrada para {self.selected_commander}.")

    def _compare_with_collection(self):
        """
        Inicia o processo de comparação entre as recomendações do EDHREC e a coleção do usuário.
        Identifica as cartas faltantes e, em uma thread separada, busca seus preços médios
        no Scryfall (USD) e converte para BRL, atualizando a interface com o progresso
        e o custo total estimado.
        """
        self._update_status("Preparando comparação e busca de preços...")
        self.comparison_results_text.delete("1.0", tk.END)
        self.progress_bar["value"] = 0
        self.total_cost_label.config(text="Custo Total Estimado: R$ 0.00")
        self.total_missing_cost = 0.0 # Reinicia o custo total

        if not self.edhrec_recommendations:
            self.comparison_results_text.insert(tk.END, "Erro: Busque as recomendações do EDHREC primeiro.\n")
            self._update_status("Falha na comparação: Nenhuma recomendação disponível.")
            return

        collection_raw = self.collection_text.get("1.0", tk.END).strip()
        if not collection_raw:
            self.comparison_results_text.insert(tk.END, "Erro: A sua coleção está vazia. Por favor, carregue sua coleção.\n")
            self._update_status("Falha na comparação: Sua coleção está vazia.")
            return

        # Usa um 'set' para uma busca mais eficiente.
        my_collection = {line.strip() for line in collection_raw.split('\n') if line.strip()}
        
        cards_you_have = [rec for rec in self.edhrec_recommendations if rec in my_collection]
        cards_you_need = [rec for rec in self.edhrec_recommendations if rec not in my_collection]

        self.comparison_results_text.insert(tk.END, "--- Cartas que Você Possui ---\n")
        if cards_you_have:
            self.comparison_results_text.insert(tk.END, "\n".join(sorted(cards_you_have)))
        else:
            self.comparison_results_text.insert(tk.END, "Nenhuma.\n")
        
        self.comparison_results_text.insert(tk.END, "\n\n--- Cartas que Você Precisa ---\n")
        
        if not cards_you_need:
            self.comparison_results_text.insert(tk.END, "Nenhuma.\n")
            self._update_status(f"Comparação completa: Você tem {len(cards_you_have)}, não precisa de nenhuma carta.")
            return

        # Busca a taxa de câmbio USD para BRL uma vez para todas as cartas
        self._update_status("Buscando taxa de câmbio USD/BRL...")
        usd_to_brl_rate = mtg_data.get_usd_to_brl_exchange_rate()
        if usd_to_brl_rate is None: # Retorna None em caso de erro
            usd_to_brl_rate = 5.0 # Usa um valor padrão fixo se a API falhar
            self.comparison_results_text.insert(tk.END, "Aviso: Não foi possível obter a taxa de câmbio atual. Usando R$5.00/US$1.00 para conversão.\n")
        
        self.progress_bar["maximum"] = len(cards_you_need)
        self.progress_bar["value"] = 0

        # Inicia a thread de busca de preços
        # Passa a lista de cartas, a taxa de câmbio, e a fila para comunicação.
        self.price_fetching_thread = threading.Thread(
            target=self._price_fetching_worker,
            args=(sorted(cards_you_need), usd_to_brl_rate)
        )
        self.price_fetching_thread.start()
        # Agenda a verificação periódica da fila para atualizar a UI.
        self.root.after(100, self._process_queue)

    def _price_fetching_worker(self, cards_to_fetch, usd_to_brl_rate):
        """
        Função executada em uma thread separada para buscar os preços das cartas.
        Envia mensagens de progresso para a fila.
        """
        current_total_cost = 0.0
        for i, card_name in enumerate(cards_to_fetch):
            # Envia mensagem de progresso para a fila (3 elementos: tipo, valor atual, nome da carta)
            self.queue.put(("progress", i + 1, card_name))
            
            usd_price = mtg_data.get_card_price_from_scryfall(card_name)
            
            display_price = "Preço não disponível"
            if usd_price is not None:
                brl_price = usd_price * usd_to_brl_rate
                current_total_cost += brl_price
                display_price = f"R$ {brl_price:.2f}"
            
            # Envia o resultado individual para a fila (3 elementos: tipo, nome da carta, preço exibível)
            self.queue.put(("card_price", card_name, display_price))
            time.sleep(0.1) # Pequeno atraso para respeitar limites de taxa do Scryfall

        # Envia o custo total final para a fila (3 elementos: tipo, custo total, None)
        self.queue.put(("total_cost", current_total_cost, None))
        # Sinaliza que a tarefa da thread foi concluída (3 elementos: tipo, None, None)
        self.queue.put(("done", None, None))

    def _process_queue(self):
        """
        Processa as mensagens da fila e atualiza a interface do usuário.
        Chamado periodicamente pela função `self.root.after`.
        """
        try:
            while True:
                msg_type, value1, value2 = self.queue.get_nowait()
                if msg_type == "progress":
                    # value1 = progresso atual, value2 = nome da carta
                    self.progress_bar["value"] = value1
                    self._update_status(f"Buscando preço no Scryfall para '{value2}' ({value1}/{self.progress_bar['maximum']})...")
                elif msg_type == "card_price":
                    # value1 = nome da carta, value2 = preço exibível
                    self.comparison_results_text.insert(tk.END, f"- {value1} ({value2})\n")
                elif msg_type == "total_cost":
                    # value1 = custo total
                    self.total_missing_cost = value1
                    self.total_cost_label.config(text=f"Custo Total Estimado: R$ {self.total_missing_cost:.2f}")
                elif msg_type == "done":
                    self.progress_bar["value"] = self.progress_bar["maximum"] # Garante que a barra chegue ao fim.
                    self._update_status(f"Comparação completa: Custo total estimado: R$ {self.total_missing_cost:.2f}.")
                    return # Sai do loop e não agenda a próxima chamada (thread concluída)
        except queue.Empty:
            pass # Nenhuma mensagem na fila, continua esperando

        # Agenda a próxima chamada para verificar a fila.
        self.root.after(100, self._process_queue)




# Ponto de entrada da aplicação.
if __name__ == "__main__":
    # Cria a janela principal da aplicação.
    root = tk.Tk()
    # Instancia a classe principal da aplicação.
    app = CommanderDeckCheckApp(root)
    # Inicia o loop principal da GUI, que aguarda por eventos do usuário.
    root.mainloop()