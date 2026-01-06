import socket
import struct
import tkinter as tk
from tkinter import messagebox

# Configuração do Protocolo (Igual ao C)
# Formato: i (int tipo), i (int id_origem), 1024s (char conteudo), L (unsigned long checksum)
FORMATO_PACOTE = 'ii1024sL'

# Tipos de Mensagem
MSG_HEARTBEAT = 1
MSG_QUERY = 2

def calcular_checksum(conteudo_bytes):
    soma = 0
    for byte in conteudo_bytes:
        soma += byte
    return soma

def enviar_query():
    query = entry_query.get()
    if not query:
        messagebox.showwarning("Aviso", "Por favor, digite uma query SQL.")
        return

    try:
        # Pega o IP e Porta digitados na interface (ou usa padrão)
        ip_destino = entry_ip.get()
        porta_destino = int(entry_porta.get())

        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.settimeout(5) # Evita travar se o servidor não responder
        client.connect((ip_destino, porta_destino))

        # --- PREPARANDO O PACOTE (A Mágica acontece aqui) ---
        tipo = MSG_QUERY
        id_origem = 0  # 0 indica que sou um CLIENTE (não um nó middleware)
        
        # Garante que a query tenha exatamente 1024 bytes
        query_bytes = query.encode('utf-8')
        checksum = calcular_checksum(query_bytes)
        
        # Empacota em binário (struct do C)
        pacote_binario = struct.pack(FORMATO_PACOTE, tipo, id_origem, query_bytes, checksum)

        # Envia
        client.send(pacote_binario)

        # Recebe resposta (Texto simples do servidor)
        resposta = client.recv(4096).decode('utf-8', errors='ignore')
        
        # Exibe
        text_resultado.delete(1.0, tk.END)
        text_resultado.insert(tk.END, resposta)
        
        client.close()
    except Exception as e:
        messagebox.showerror("Erro", f"Erro na conexão: {e}")

# --- Interface Gráfica ---
root = tk.Tk()
root.title("Cliente Distribuído v2")
root.geometry("600x500")

# Configuração de IP/Porta
frame_config = tk.Frame(root)
frame_config.pack(pady=5)
tk.Label(frame_config, text="IP Nó:").pack(side=tk.LEFT)
entry_ip = tk.Entry(frame_config, width=15)
entry_ip.insert(0, "127.0.0.1")
entry_ip.pack(side=tk.LEFT, padx=5)
tk.Label(frame_config, text="Porta:").pack(side=tk.LEFT)
entry_porta = tk.Entry(frame_config, width=6)
entry_porta.insert(0, "5001") # Aponta para o Nó 1
entry_porta.pack(side=tk.LEFT)

tk.Label(root, text="Digite sua Query SQL:").pack(pady=5)
entry_query = tk.Entry(root, width=70)
entry_query.pack(pady=5)

btn_executar = tk.Button(root, text="ENVIAR COMANDO", command=enviar_query, bg="#007bff", fg="white", font=("Arial", 10, "bold"))
btn_executar.pack(pady=10)

tk.Label(root, text="Log do Sistema:").pack(pady=5)
text_resultado = tk.Text(root, height=15, width=70, bg="#f0f0f0")
text_resultado.pack(pady=5)

root.mainloop()