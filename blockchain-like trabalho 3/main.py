import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import argparse
import logging

# Importando suas funções procedurais
from util.node_functions import criar_estado_no, iniciar_no, conectar_a_peer, propagar_mensagem
from util.blockchain import calcular_saldo, adicionar_transacao
from util.miner_pow import minerar_bloco, interromper_mineracao
from util.protocolo import msg_nova_transacao, msg_novo_bloco

class BlockchainApp:
    def __init__(self, root, host, port, bootstraps):
        self.root = root
        self.root.title(f"Blockchain Node - {host}:{port}")
        self.root.geometry("700x600")
        #print(port)

        # 1. Inicializa o Estado do Nó (Procedural)
        self.no_estado = criar_estado_no(host, port)
        
        # Configura logging para arquivo para não poluir o terminal
        logging.basicConfig(filename=f"node_{port}.log", level=logging.INFO)

        self._setup_ui()
        
        # 2. Inicia o Servidor P2P em background
        iniciar_no(self.no_estado)

        # 3. Conecta aos Bootstraps
        for b in bootstraps:
            threading.Thread(target=conectar_a_peer, args=(self.no_estado, b), daemon=True).start()

        self.log("Sistema iniciado. Aguardando conexões...")

    def _setup_ui(self):
        """Define o layout da interface Tkinter."""
        # Frame Superior: Status
        status_frame = ttk.LabelFrame(self.root, text=" Status do Nó ")
        status_frame.pack(fill="x", padx=10, pady=5)

        self.lbl_address = ttk.Label(status_frame, text=f"Endereço: {self.no_estado['address']}")
        self.lbl_address.pack(side="left", padx=5)

        self.lbl_balance = ttk.Label(status_frame, text="Saldo: 0.0 BTC", foreground="green", font=("Arial", 10, "bold"))
        self.lbl_balance.pack(side="right", padx=5)

        # Frame Central: Ações
        actions_frame = ttk.Frame(self.root)
        actions_frame.pack(fill="x", padx=10, pady=5)

        ttk.Button(actions_frame, text="Nova Transação", command=self.window_transacao).pack(side="left", expand=True, fill="x")
        ttk.Button(actions_frame, text="Minerar Bloco", command=self.acao_minerar).pack(side="left", expand=True, fill="x")
        ttk.Button(actions_frame, text="Ver Blockchain", command=self.acao_ver_chain).pack(side="left", expand=True, fill="x")
        ttk.Button(actions_frame, text="Sincronizar", command=self.acao_sync).pack(side="left", expand=True, fill="x")

        # Frame Inferior: Log de Eventos
        log_frame = ttk.LabelFrame(self.root, text=" Log da Rede ")
        log_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.txt_log = scrolledtext.ScrolledText(log_frame, state='disabled', height=15)
        self.txt_log.pack(fill="both", expand=True)

    def log(self, mensagem):
        """Adiciona mensagens à área de texto da UI."""
        self.txt_log.config(state='normal')
        self.txt_log.insert(tk.END, f"> {mensagem}\n")
        self.txt_log.see(tk.END)
        self.txt_log.config(state='disabled')

    def atualizar_saldo_ui(self):
        saldo = calcular_saldo(self.no_estado["blockchain"], self.no_estado["address"])
        self.lbl_balance.config(text=f"Saldo: {saldo} BTC")

    # --- Ações da Interface ---

    def window_transacao(self):
        """Abre um popup para criar transação."""
        win = tk.Toplevel(self.root)
        win.title("Enviar Moedas")
        win.geometry("300x200")

        ttk.Label(win, text="Destino (host:port):").pack(pady=5)
        ent_destino = ttk.Entry(win)
        ent_destino.pack(fill="x", padx=20)

        ttk.Label(win, text="Valor:").pack(pady=5)
        ent_valor = ttk.Entry(win)
        ent_valor.pack(fill="x", padx=20)

        def enviar():
            try:
                dest = ent_destino.get()
                val = float(ent_valor.get())
                
                # Lógica procedural: cria e propaga
                from util.transaction import criar_transacao
                tx = criar_transacao(self.no_estado["address"], dest, val)
                
                if adicionar_transacao(self.no_estado["blockchain"], tx):
                    msg = msg_nova_transacao(tx)
                    propagar_mensagem(self.no_estado, msg)
                    self.log(f"Transação enviada: {tx['id'][:8]}")
                    win.destroy()
                else:
                    messagebox.showerror("Erro", "Saldo insuficiente ou transação inválida.")
            except ValueError:
                messagebox.showerror("Erro", "Valor inválido.")

        ttk.Button(win, text="Confirmar Envio", command=enviar).pack(pady=20)

    def acao_minerar(self):
        """Roda a mineração em uma thread para não travar a GUI."""
        def tarefa():
            self.log("Iniciando mineração...")
            bloco = minerar_bloco(self.no_estado, self.no_estado["address"])
            if bloco:
                self.log(f"Bloco #{bloco['index']} minerado com sucesso!")
                # Propaga o novo bloco
                msg = msg_novo_bloco(bloco)
                propagar_mensagem(self.no_estado, msg)
                self.root.after(0, self.atualizar_saldo_ui)
            else:
                self.log("Mineração interrompida ou falhou.")

        threading.Thread(target=tarefa, daemon=True).start()

    def acao_ver_chain(self):
        self.log(f"Blockchain atual possui {len(self.no_estado['blockchain']['chain'])} blocos.")
        for b in self.no_estado['blockchain']['chain']:
            self.log(f"Bloco {b['index']} | Hash: {b['hash'][:10]}... | Txs: {len(b['transactions'])}")

    def acao_sync(self):
        self.log("Sincronizando com peers...")
        from util.protocolo import msg_solicitar_chain
        msg = msg_solicitar_chain()
        # Adiciona o sender para o peer saber para quem responder
        msg["sender"] = self.no_estado["address"] 
        propagar_mensagem(self.no_estado, msg)
        self.atualizar_saldo_ui()

# --- Inicialização ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--bootstrap", nargs="*", default=[])
    args = parser.parse_args()

    root = tk.Tk()
    app = BlockchainApp(root, "localhost", args.port, args.bootstrap)
    root.mainloop()