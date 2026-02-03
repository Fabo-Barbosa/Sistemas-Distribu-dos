import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import socket
import struct
import threading

# --- CONFIGURAÇÃO DO PROTOCOLO (Igual ao Middleware) ---
FORMATO_PACOTE = "ii1024sQ"
MSG_QUERY = 2

class ClienteGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Cliente Distribuído - Painel de Controle")
        self.root.geometry("600x500")
        self.root.configure(bg="#f0f0f0")

        # Estilo
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TButton", font=('Helvetica', 10, 'bold'))
        style.configure("TLabel", background="#f0f0f0", font=('Helvetica', 11))
        style.configure("TRadiobutton", background="#f0f0f0", font=('Helvetica', 10))

        # --- ÁREA DE CONEXÃO ---
        frame_conn = ttk.LabelFrame(root, text=" Conectar em qual Nó? ", padding=10)
        frame_conn.pack(fill="x", padx=10, pady=10)

        self.porta_var = tk.IntVar(value=5001)
        
        ttk.Radiobutton(frame_conn, text="Nó 1 (Porta 5001)", variable=self.porta_var, value=5001).pack(side="left", padx=20)
        ttk.Radiobutton(frame_conn, text="Nó 2 (Porta 5002)", variable=self.porta_var, value=5002).pack(side="left", padx=20)
        ttk.Radiobutton(frame_conn, text="Nó 3 (Porta 5003)", variable=self.porta_var, value=5003).pack(side="left", padx=20)

        # --- ÁREA DE COMANDO SQL ---
        frame_sql = ttk.LabelFrame(root, text=" Comando SQL ", padding=10)
        frame_sql.pack(fill="x", padx=10, pady=5)

        self.txt_sql = tk.Entry(frame_sql, font=('Consolas', 11))
        self.txt_sql.pack(fill="x", pady=5)
        self.txt_sql.insert(0, "INSERT INTO clientes (nome) VALUES ('Teste GUI');")

        btn_enviar = ttk.Button(frame_sql, text="ENVIAR COMANDO ➤", command=self.enviar_thread)
        btn_enviar.pack(pady=5, fill="x")

        # --- ÁREA DE LOG ---
        frame_log = ttk.LabelFrame(root, text=" Log do Sistema ", padding=10)
        frame_log.pack(fill="both", expand=True, padx=10, pady=10)

        self.txt_log = scrolledtext.ScrolledText(frame_log, height=10, font=('Consolas', 9))
        self.txt_log.pack(fill="both", expand=True)
        self.log("Sistema iniciado. Selecione um nó e envie um comando.")

    def log(self, mensagem):
        self.txt_log.insert(tk.END, f">> {mensagem}\n")
        self.txt_log.see(tk.END)

    def calcular_checksum(self, conteudo_bytes):
        return sum(conteudo_bytes)

    def enviar_thread(self):
        # Roda o envio em background para não travar a tela
        threading.Thread(target=self.enviar_comando, daemon=True).start()

    def enviar_comando(self):
        sql = self.txt_sql.get().strip()
        porta = self.porta_var.get()
        ip = "localhost"

        if not sql:
            messagebox.showwarning("Aviso", "Digite um comando SQL!")
            return

        try:
            self.log(f"Enviando para Nó {porta - 5000} ({ip}:{porta})...")

            # 1. Preparar Pacote
            tipo = MSG_QUERY
            id_origem = 0 
            conteudo_bytes = sql.encode('utf-8')[:1024].ljust(1024, b'\0')
            checksum = self.calcular_checksum(conteudo_bytes)

            pacote = struct.pack(FORMATO_PACOTE, tipo, id_origem, conteudo_bytes, checksum)

            # 2. Conectar e Enviar
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3) # Timeout de 3 segundos
            s.connect((ip, porta))
            s.sendall(pacote)
            
            # Tenta receber confirmação (opcional, dependendo do middleware)
            try:
                resp = s.recv(1024)
                if resp:
                    texto_resp = resp.decode('utf-8', errors='ignore')
                    self.log(f"Resposta do Servidor: {texto_resp}")
            except socket.timeout:
                self.log("Comando enviado (Sem resposta imediata).")
            
            s.close()
            self.log("--- Sucesso! ---\n")

        except ConnectionRefusedError:
            self.log(f"ERRO: Não foi possível conectar em {ip}:{porta}.")
            self.log("O Docker está rodando? O container caiu?")
            messagebox.showerror("Erro de Conexão", f"Falha ao conectar no Nó {porta-5000}.\nVerifique se o Docker está rodando.")
        except Exception as e:
            self.log(f"ERRO: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = ClienteGUI(root)
    root.mainloop()