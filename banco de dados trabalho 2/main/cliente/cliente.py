import socket
import tkinter as tk
from tkinter import messagebox

def enviar_query():
    query = entry_query.get()
    if not query:
        messagebox.showwarning("Aviso", "Por favor, digite uma query SQL.")
        return

    try:
        # 1. Conecta ao Middleware (Porta 5000)
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(('127.0.0.1', 5000))

        # 2. Envia a Query
        client.send(query.encode('utf-8'))

        # 3. Recebe a Resposta
        resposta = client.recv(4096).decode('utf-8')
        
        # 4. Exibe o resultado na interface
        text_resultado.delete(1.0, tk.END)
        text_resultado.insert(tk.END, resposta)
        
        client.close()
    except Exception as e:
        messagebox.showerror("Erro", f"Não foi possível conectar ao Middleware: {e}")

# --- Configuração da Interface Gráfica ---
root = tk.Tk()
root.title("Cliente de Banco de Dados Distribuído")
root.geometry("600x400")

label_instrucao = tk.Label(root, text="Digite sua Query SQL (ex: SELECT * FROM cliente):")
label_instrucao.pack(pady=10)

entry_query = tk.Entry(root, width=70)
entry_query.pack(pady=5)

btn_executar = tk.Button(root, text="Executar no Cluster", command=enviar_query, bg="#4CAF50", fg="white")
btn_executar.pack(pady=10)

label_resultado = tk.Label(root, text="Resultado do Middleware:")
label_resultado.pack(pady=5)

text_resultado = tk.Text(root, height=10, width=70)
text_resultado.pack(pady=5)

root.mainloop()