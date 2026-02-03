import socket
import threading
import time
import struct
import os
import mysql.connector

# --- CONFIGURAÇÕES ---
# Pega do Docker ou usa localhost
DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
DB_USER = "root"
DB_PASS = "root"
DB_NAME = "banco_distribuido"

FORMATO_PACOTE = "ii1024sQ"
TAMANHO_PACOTE = struct.calcsize(FORMATO_PACOTE)

MSG_HEARTBEAT = 1
MSG_QUERY = 2
MSG_ELEICAO = 3
MSG_COORDENADOR = 4

class Node:
    def __init__(self):
        self.meu_id = 0
        self.vizinhos = []
        self.lider_id = 0
        self.em_eleicao = False
        self.ultimo_heartbeat = time.time()
        
        self.carregar_config()

        print(f"--- INICIANDO NÓ {self.meu_id} (Banco: {DB_HOST}) ---")
        
        # Tenta conectar até o banco subir
        while not self.conectar_db():
            time.sleep(2)
        print("Banco Conectado!")

        # Inicia Monitoramento (Eleição)
        threading.Thread(target=self.rotina_monitoramento, daemon=True).start()

    def carregar_config(self):
        try:
            # Tenta pegar ID do Docker (Simulação)
            env_id = os.getenv('NODE_ID')
            
            with open("config.txt", "r") as f:
                linhas = [l.strip() for l in f.readlines() if l.strip()]
                
                # Se tem ID no ambiente (Docker), usa ele. Senão, pega do arquivo.
                if env_id:
                    self.meu_id = int(env_id)
                else:
                    self.meu_id = int(linhas[0])

                for l in linhas[1:]:
                    partes = l.split()
                    if len(partes) < 3: continue
                    nid, host, porta = int(partes[0]), partes[1], int(partes[2])
                    self.vizinhos.append({'id': nid, 'ip': host, 'porta': porta})
                    
        except Exception as e:
            print(f"ERRO config.txt: {e}")
            exit(1)

    def conectar_db(self):
        try:
            self.conn = mysql.connector.connect(
                host=DB_HOST, user=DB_USER, password=DB_PASS, database=DB_NAME
            )
            return True
        except:
            return False

    def enviar(self, ip, porta, tipo, conteudo=""):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1) 
            s.connect((ip, porta))
            
            dado_bytes = conteudo.encode('utf-8')[:1024].ljust(1024, b'\0')
            chk = sum(dado_bytes)
            pkt = struct.pack(FORMATO_PACOTE, tipo, self.meu_id, dado_bytes, chk)
            
            s.sendall(pkt)
            s.close()
            return True
        except:
            return False

    def processar_pacote(self, dados):
        try:
            tipo, origem, conteudo_raw, chk = struct.unpack(FORMATO_PACOTE, dados)
            conteudo = conteudo_raw.decode('utf-8').strip('\x00')
            
            if tipo == MSG_HEARTBEAT:
                if origem == self.lider_id:
                    self.ultimo_heartbeat = time.time()

            elif tipo == MSG_QUERY:
                print(f"--> SQL de {origem}: {conteudo}")
                cursor = self.conn.cursor()
                cursor.execute(conteudo)
                self.conn.commit()
                cursor.close()
                
            elif tipo == MSG_ELEICAO:
                print(f"--> Eleição de {origem}. Sou maior, vou assumir.")
                if self.meu_id > origem:
                    self.iniciar_eleicao()

            elif tipo == MSG_COORDENADOR:
                print(f"!!! NOVO LIDER: {origem} !!!")
                self.lider_id = origem
                self.ultimo_heartbeat = time.time()
                self.em_eleicao = False

        except Exception as e:
            print(f"Erro pacote: {e}")

    def iniciar_eleicao(self):
        if self.em_eleicao: return
        self.em_eleicao = True
        print("!!! INICIANDO ELEIÇÃO !!!")
        
        maior_respondeu = False
        for viz in self.vizinhos:
            if viz['id'] > self.meu_id:
                if self.enviar(viz['ip'], viz['porta'], MSG_ELEICAO):
                    maior_respondeu = True
        
        if not maior_respondeu:
            print(f">>> EU ({self.meu_id}) SOU O LIDER <<<")
            self.lider_id = self.meu_id
            self.em_eleicao = False
            for viz in self.vizinhos:
                if viz['id'] != self.meu_id:
                    self.enviar(viz['ip'], viz['porta'], MSG_COORDENADOR)
        else:
            self.em_eleicao = False 

    def rotina_monitoramento(self):
        time.sleep(10) # Espera inicial para todos subirem
        if self.lider_id == 0: self.iniciar_eleicao()

        while True:
            time.sleep(3)
            if self.lider_id == self.meu_id:
                for viz in self.vizinhos:
                    if viz['id'] != self.meu_id:
                        self.enviar(viz['ip'], viz['porta'], MSG_HEARTBEAT)
            else:
                if time.time() - self.ultimo_heartbeat > 8:
                    print(f"!!! Timeout Lider {self.lider_id} !!!")
                    self.iniciar_eleicao()

    def server_loop(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(('0.0.0.0', 5000))
        server.listen(5)
        print("--- Ouvindo na porta 5000 ---")
        
        while True:
            try:
                conn, addr = server.accept()
                dados = b''
                while len(dados) < TAMANHO_PACOTE:
                    chunk = conn.recv(TAMANHO_PACOTE - len(dados))
                    if not chunk: break
                    dados += chunk
                
                if len(dados) == TAMANHO_PACOTE:
                    self.processar_pacote(dados)
                conn.close()
            except: pass

if __name__ == "__main__":
    Node().server_loop()