#include <mysql/mysql.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <sys/socket.h>

// --- DEFINIÇÕES DO SISTEMA ---
#define MAX_NOS 5
#define BUFFER_SIZE 4096

// Credenciais do Banco (Restauradas!)
#define DB_USER "devmaster"
#define DB_PASS "@DevMaster123"
#define DB_NAME "projeto_distribuido"

// Tipos de Mensagem do Protocolo
#define MSG_HEARTBEAT 1
#define MSG_QUERY     2

// --- ESTRUTURAS DE DADOS ---

// Configuração de um Nó (Lido do arquivo)
typedef struct {
    int id;
    char ip[20];
    int porta;
} NoConfig;

// O Pacote que viaja pela rede (Protocolo)
typedef struct {
    int tipo;               // MSG_HEARTBEAT ou MSG_QUERY
    int id_origem;          // Quem mandou (1, 2, 3...)
    char conteudo[1024];    // O SQL ou mensagem
    unsigned long checksum; // Validação
} Pacote;

// --- VARIÁVEIS GLOBAIS ---
int MEU_ID = 0;
NoConfig lista_nos[MAX_NOS];
int total_nos = 0;

// --- FUNÇÕES AUXILIARES ---

// Calcula integridade simples (soma dos bytes)
unsigned long calcular_checksum(char *dados) {
    unsigned long soma = 0;
    while (*dados) {
        soma += *dados++;
    }
    return soma;
}

// Carrega IPs e Portas do arquivo config.txt
void carregar_configuracao() {
    FILE *f = fopen("config.txt", "r");
    if (!f) {
        perror("ERRO FATAL: config.txt nao encontrado");
        exit(1);
    }

    // 1. Lê quem SOU EU (primeira linha)
    if (fscanf(f, "%d", &MEU_ID) != 1) {
        printf("Erro ao ler ID do no.\n");
        exit(1);
    }
    printf(">>> INICIANDO NO ID: %d <<<\n", MEU_ID);

    // 2. Lê a lista de vizinhos
    int i = 0;
    while (fscanf(f, "%s %d", lista_nos[i].ip, &lista_nos[i].porta) != EOF && i < MAX_NOS) {
        lista_nos[i].id = i + 1; // IDs assumidos sequenciais (1, 2, 3...)
        i++;
    }
    total_nos = i;
    fclose(f);
    
    printf("Configuracao carregada. Total de nos na rede: %d\n", total_nos);
}

// --- FUNÇÕES DE BANCO DE DADOS ---

MYSQL* conectar_banco(int porta) {
    MYSQL *conn = mysql_init(NULL);
    enum mysql_protocol_type protocolo = MYSQL_PROTOCOL_TCP;
    mysql_options(conn, MYSQL_OPT_PROTOCOL, &protocolo);
    
    // Conecta usando as credenciais definidas no topo
    if (mysql_real_connect(conn, "127.0.0.1", DB_USER, DB_PASS, DB_NAME, porta, NULL, 0) == NULL) {
        fprintf(stderr, "Erro de conexao MySQL: %s\n", mysql_error(conn));
        return NULL;
    }
    return conn;
}

// --- MAIN ---

int main() {
    // 1. Carrega configurações antes de tudo
    carregar_configuracao();

    int server_fd, new_socket;
    struct sockaddr_in address;
    int opt = 1;
    int addrlen = sizeof(address);
    
    // Buffer agora é do tipo Pacote, não char[]
    Pacote pacote_recebido; 

    // Criação do Socket
    if ((server_fd = socket(AF_INET, SOCK_STREAM, 0)) == 0) {
        perror("Falha no socket");
        exit(EXIT_FAILURE);
    }

    // Configuração de Socket
    if (setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt))) {
        perror("setsockopt");
        exit(EXIT_FAILURE);
    }

    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    
    // Configura a porta baseada no ID lido do arquivo (MEU_ID - 1 pois array começa em 0)
    int minha_porta = lista_nos[MEU_ID - 1].porta; 
    address.sin_port = htons(minha_porta);

    if (bind(server_fd, (struct sockaddr *)&address, sizeof(address)) < 0) {
        perror("Falha no bind");
        exit(EXIT_FAILURE);
    }

    if (listen(server_fd, 3) < 0) {
        perror("listen");
        exit(EXIT_FAILURE);
    }

    printf("--- Middleware (ID %d) Ouvindo na Porta %d ---\n", MEU_ID, minha_porta);

    // LOOP PRINCIPAL
    while(1) {
        printf("\nAguardando conexao...\n");
        if ((new_socket = accept(server_fd, (struct sockaddr *)&address, (socklen_t*)&addrlen)) < 0) {
            perror("accept");
            continue;
        }

        // Limpa e recebe a estrutura inteira
        memset(&pacote_recebido, 0, sizeof(Pacote));
        
        // Lê exatamente o tamanho de um Pacote
        int valread = read(new_socket, &pacote_recebido, sizeof(Pacote));
        
        if (valread > 0) {
            printf("Recebido pacote do No %d. Tipo: %d\n", pacote_recebido.id_origem, pacote_recebido.tipo);

            // Valida Checksum (Integridade)
            unsigned long check = calcular_checksum(pacote_recebido.conteudo);
            if (check != pacote_recebido.checksum) {
                printf("ERRO: Checksum invalido! Pacote corrompido.\n");
                close(new_socket);
                continue;
            }

            printf("Conteudo validado: %s\n", pacote_recebido.conteudo);
            
            // TODO: Aqui vamos adicionar a lógica de conectar no banco e replicar
            // Por enquanto, apenas confirmamos o recebimento.
            char *msg = "Recebido com sucesso";
            send(new_socket, msg, strlen(msg), 0);
        }
        close(new_socket);
    }
    return 0;
}