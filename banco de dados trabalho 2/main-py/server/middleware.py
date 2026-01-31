import socket
import threading
import time
import struct
import mysql.connector
from mysql.connector import Error

# --- CONFIGURAÇÕES E CONSTANTES ---
MAX_NOS = 5
BUFFER_SIZE = 4096
FORMATO_PACOTE = "ii1024sQ"  # i=int, i=int, 1024s=char[1024], Q=unsigned long (8 bytes)
TAMANHO_PACOTE = struct.calcsize(FORMATO_PACOTE)

# Mensagens
MSG_HEARTBEAT = 1
MSG_QUERY = 2
MSG_ELECTION = 3
MSG_COORDINATOR = 4

# DB
DB_USER = "devmaster"
DB_PASS = "@DevMaster123"
DB_NAME = "projeto_distribuido"

class Middleware:
    def __init__(self):
        self.meu_id = 0
        self.lista_nos = [] # Lista de dicionários {'id', 'ip', 'porta'}
        self.id_lider_atual = 0
        self.ultima_msg_lider = time.time()
        self.estou_em_eleicao = False
        self.carregar_configuracao()
        
    def carregar_configuracao(self):
        try:
            with open("config.txt", "r") as f:
                linhas = f.readlines()
                self.meu_id = int(linhas[0].strip())
                print(f">>> INICIANDO NO ID: {self.meu_id} <<<")
                
                for i, linha in enumerate(linhas[1:]):
                    parts = linha.split()
                    if parts:
                        self.lista_nos.append({
                            'id': i + 1,
                            'ip': parts[0],
                            'porta': int(parts[1])
                        })
            print(f"Configuracao carregada. Total de nos: {len(self.lista_nos)}")
        except Exception as e:
            print(f"ERRO FATAL ao ler config.txt: {e}")
            exit(1)

    def calcular_checksum(self, conteudo):
        # Simula a soma de bytes do C
        return sum(conteudo.encode('ascii', 'ignore'))

    def conectar_banco(self):
        # Lógica de porta baseada no ID igual ao original
        porta_db = 3307 if self.meu_id == 2 else 3306
        try:
            conn = mysql.connector.connect(
                host="127.0.0.1",
                user=DB_USER,
                password=DB_PASS,
                database=DB_NAME,
                port=porta_db
            )
            return conn
        except Error as e:
            print(f"Erro MySQL: {e}")
            return None

    def empacotar(self, tipo, id_origem, conteudo):
        conteudo_bytes = conteudo.encode('utf-8')[:1024].ljust(1024, b'\0')
        checksum = self.calcular_checksum(conteudo)
        return struct.pack(FORMATO_PACOTE, tipo, id_origem, conteudo_bytes, checksum)

    def desempacotar(self, dados):
        tipo, id_origem, conteudo_raw, checksum = struct.unpack(FORMATO_PACOTE, dados)
        conteudo = conteudo_raw.decode('utf-8').strip('\x00')
        return tipo, id_origem, conteudo, checksum

    def propagar_para_vizinhos(self, tipo, id_origem, conteudo):
        pacote = self.empacotar(tipo, id_origem, conteudo)
        for no in self.lista_nos:
            if no['id'] == self.meu_id: continue
            
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1.0)
                    s.connect((no['ip'], no['porta']))
                    s.sendall(pacote)
                    print(f"-> Replicado para No {no['id']}")
            except:
                print(f"-> Falha ao replicar para No {no['id']}")

    def iniciar_eleicao(self):
        if self.estou_em_eleicao: return
        self.estou_em_eleicao = True
        print(f"!!! Lider {self.id_lider_atual} caiu. Iniciando Eleicao Bully... !!!")
        
        tenho_chances = True
        for no in self.lista_nos:
            if no['id'] <= self.meu_id: continue
            
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1.0)
                    if s.connect_ex((no['ip'], no['porta'])) == 0:
                        print(f"-> No maior ({no['id']}) online. Ele assume.")
                        tenho_chances = False
                        break
            except: continue

        if tenho_chances:
            print(">>> EU SOU O NOVO LIDER! <<<")
            self.id_lider_atual = self.meu_id
            self.propagar_para_vizinhos(MSG_COORDINATOR, self.meu_id, "NOVO LIDER")
        
        self.estou_em_eleicao = False

    def rotina_heartbeat(self):
        print(">>> Thread Monitoramento iniciada.")
        while True:
            time.sleep(3)
            # Enviar batida
            self.propagar_para_vizinhos(MSG_HEARTBEAT, self.meu_id, "HEARTBEAT")
            
            # Verificar líder
            if self.id_lider_atual != self.meu_id:
                if time.time() - self.ultima_msg_lider > 10:
                    self.iniciar_eleicao()

    def iniciar(self):
        # Inicia thread de monitoramento
        threading.Thread(target=self.rotina_heartbeat, daemon=True).start()
        
        # Setup do Servidor
        minha_porta = self.lista_nos[self.meu_id - 1]['porta']
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(('0.0.0.0', minha_porta))
            server.listen(5)
            print(f"--- Middleware Python (ID {self.meu_id}) na Porta {minha_porta} ---")
            
            while True:
                conn_sock, addr = server.accept()
                with conn_sock:
                    dados = conn_sock.recv(TAMANHO_PACOTE)
                    if not dados or len(dados) < TAMANHO_PACOTE: continue
                    
                    tipo, id_origem, conteudo, checksum = self.desempacotar(dados)
                    
                    if self.calcular_checksum(conteudo) != checksum:
                        conn_sock.sendall(b"ERRO: Checksum invalido")
                        continue

                    if tipo == MSG_HEARTBEAT:
                        if id_origem == self.id_lider_atual:
                            self.ultima_msg_lider = time.time()
                    
                    elif tipo == MSG_COORDINATOR:
                        print(f">>> Novo Lider: {id_origem}")
                        self.id_lider_atual = id_origem
                        self.ultima_msg_lider = time.time()
                    
                    elif tipo == MSG_QUERY:
                        print(f"Query: {conteudo}")
                        resposta = self.executar_query(conteudo, id_origem)
                        conn_sock.sendall(resposta.encode('utf-8'))

    def executar_query(self, sql, id_origem):
        db = self.conectar_banco()
        if not db: return "Erro conexao DB"
        
        cursor = db.cursor()
        try:
            cursor.execute(sql)
            if sql.upper().startswith("SELECT"):
                rows = cursor.fetchall()
                res = f"RESULTADOS NO {self.meu_id}:\n"
                for row in rows:
                    res += " | ".join(map(str, row)) + "\n"
                return res
            else:
                db.commit()
                res = f"Sucesso no No {self.meu_id}."
                if id_origem == 0: # Veio do cliente, propaga
                    threading.Thread(target=self.propagar_para_vizinhos, 
                                   args=(MSG_QUERY, self.meu_id, sql)).start()
                    res += "\n(Replicacao enviada)"
                return res
        except Error as e:
            return f"Erro SQL: {e}"
        finally:
            db.close()

if __name__ == "__main__":
    m = Middleware()
    m.iniciar()