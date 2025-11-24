import tkinter as tk
from tkinter import scrolledtext, messagebox
import socket

# Configuração Padrão
SERVER_IP = '127.0.0.1'
SERVER_PORT = 51482

def enviar_codigo():
    # Pega o código da área de texto
    codigo = txt_codigo.get("1.0", tk.END)
    
    if not codigo.strip():
        messagebox.showwarning("Aviso", "Digite algum código Kotlin!")
        return

    # Limpa as áreas de resultado
    txt_saida.config(state=tk.NORMAL)
    txt_saida.delete("1.0", tk.END)
    txt_erro.config(state=tk.NORMAL)
    txt_erro.delete("1.0", tk.END)
    
    try:
        # Cria o socket e conecta (equivalente ao connect() em C)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((SERVER_IP, int(entry_port.get())))
        
        # Envia o código (equivalente ao write/send)
        s.sendall(codigo.encode('utf-8'))
        
        # Recebe a resposta (equivalente ao read/recv)
        resposta = s.recv(4096).decode('utf-8')
        
        # Se tiver "ERRO", joga na tela de erro
        if "ERRO" in resposta or "exception" in resposta.lower():
            txt_erro.insert(tk.INSERT, resposta)
        else:
            txt_saida.insert(tk.INSERT, resposta)
            
        s.close()

    except Exception as e:
        messagebox.showerror("Erro de Conexão", f"Não foi possível conectar ao servidor: {e}")

# --- Configuração da Interface Gráfica (GUI) ---
janela = tk.Tk()
janela.title("Cliente de Compilação Remota - Kotlin")
janela.geometry("800x700")


# Barra de configuração (IP/Porta)
frame_config = tk.Frame(janela)
frame_config.pack(pady=5)
tk.Label(frame_config, text="Porta Servidor:").pack(side=tk.LEFT)
entry_port = tk.Entry(frame_config, width=10)
entry_port.insert(0, str(SERVER_PORT))
entry_port.pack(side=tk.LEFT, padx=5)

# Área 1: Edição de Programa
tk.Label(janela, text="Digite seu código KOTLIN aqui:", font=("Arial", 10, "bold")).pack(anchor="w", padx=10)
txt_codigo = scrolledtext.ScrolledText(janela, height=15)
txt_codigo.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)

# Código padrão de exemplo
exemplo = """fun main() {
    println("Ola Professor! Este codigo rodou no servidor.")
    println("Calculando 10 + 10 = " + (10+10))
}"""
txt_codigo.insert(tk.INSERT, exemplo)

# Botão de Execução
btn_run = tk.Button(janela, text="COMPILAR E EXECUTAR NO SERVIDOR", bg="#4CAF50", fg="white", font=("Arial", 12), command=enviar_codigo)
btn_run.pack(pady=10)

# Área 2: Saída do Programa
tk.Label(janela, text="Saída do Programa (Stdout):", font=("Arial", 10, "bold")).pack(anchor="w", padx=10)
txt_saida = scrolledtext.ScrolledText(janela, height=8, bg="#f0f0f0")
txt_saida.pack(padx=10, pady=5, fill=tk.X)

# Área 3: Retorno de Erros
tk.Label(janela, text="Erros de Compilação/Execução:", font=("Arial", 10, "bold"), fg="red").pack(anchor="w", padx=10)
txt_erro = scrolledtext.ScrolledText(janela, height=6, bg="#ffe6e6")
txt_erro.pack(padx=10, pady=5, fill=tk.X)

janela.mainloop()
