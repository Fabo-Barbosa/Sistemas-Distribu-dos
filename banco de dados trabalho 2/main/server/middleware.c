#include <mysql/mysql.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <arpa/inet.h>
#include <sys/socket.h>
#include <pthread.h>
#include <time.h>

// --- DEFINIÇÕES DO SISTEMA ---
#define MAX_NOS 5
#define BUFFER_SIZE 4096

// Credenciais do Banco (Restauradas!)
#define DB_USER "devmaster"
#define DB_PASS "@DevMaster123"
#define DB_NAME "projeto_distribuido"

// Tipos de Mensagem do Protocolo
#define MSG_HEARTBEAT   1
#define MSG_QUERY       2
#define MSG_ELECTION    3  // "Quem manda aqui?"
#define MSG_COORDINATOR 4  // "Eu mando aqui!"

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

// Variáveis Globais de Controle de Liderança
int ID_LIDER_ATUAL = 0;
time_t ultima_msg_lider = 0; // Timestamp da última vez que o líder falou
int estou_em_eleicao = 0;    // Evita começar várias eleições ao mesmo tempo

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

// Função para enviar um pacote para TODOS os outros nós listados no config.txt
void propagar_para_vizinhos(Pacote p) {
    int sock;
    struct sockaddr_in serv_addr;

    printf(">>> Iniciando Replicacao (Broadcast) <<<\n");

    for (int i = 0; i < total_nos; i++) {
        // Pula se for eu mesmo
        if (lista_nos[i].id == MEU_ID) continue;

        // Cria socket temporário
        if ((sock = socket(AF_INET, SOCK_STREAM, 0)) < 0) continue;

        serv_addr.sin_family = AF_INET;
        serv_addr.sin_port = htons(lista_nos[i].porta);
        
        // IP do vizinho
        if (inet_pton(AF_INET, lista_nos[i].ip, &serv_addr.sin_addr) <= 0) {
             close(sock); continue;
        }

        // Tenta conectar (timeout rápido seria ideal, mas vamos padrão)
        if (connect(sock, (struct sockaddr *)&serv_addr, sizeof(serv_addr)) == 0) {
            // Envia o pacote estruturado
            send(sock, &p, sizeof(Pacote), 0);
            printf("-> Replicado com sucesso para No %d (Porta %d)\n", lista_nos[i].id, lista_nos[i].porta);
        } else {
            printf("-> Falha ao replicar para No %d (Offline?)\n", lista_nos[i].id);
        }
        close(sock);
    }
}

void iniciar_eleicao() {
    if (estou_em_eleicao) return;
    estou_em_eleicao = 1;
    printf("!!! ALERTA: Lider (No %d) parou de responder. Iniciando Eleicao... !!!\n", ID_LIDER_ATUAL);

    int tenho_chances = 1;

    // Algoritmo Bully: Tenta falar com todo mundo que tem ID MAIOR que o meu
    for (int i = 0; i < total_nos; i++) {
        if (lista_nos[i].id <= MEU_ID) continue; // Ignora menores ou eu mesmo

        int sock;
        struct sockaddr_in serv_addr;
        
        if ((sock = socket(AF_INET, SOCK_STREAM, 0)) < 0) continue;
        serv_addr.sin_family = AF_INET;
        serv_addr.sin_port = htons(lista_nos[i].porta);
        inet_pton(AF_INET, lista_nos[i].ip, &serv_addr.sin_addr);

        // Se conseguir conectar em alguém maior, ele é o chefe, eu recuo.
        if (connect(sock, (struct sockaddr *)&serv_addr, sizeof(serv_addr)) == 0) {
            printf("-> Encontrei um no maior (No %d) online. Ele deve assumir.\n", lista_nos[i].id);
            tenho_chances = 0;
            
            // Opcional: Mandar MSG_ELECTION para forçar ele a se declarar, 
            // mas apenas conectar já prova que ele está vivo.
            close(sock);
            break; 
        }
        close(sock);
    }

    if (tenho_chances) {
        // Se ninguém maior respondeu, EU SOU O NOVO LÍDER!
        printf(">>> NINGUEM MAIOR RESPONDEU. EU SOU O NOVO LIDER! <<<\n");
        ID_LIDER_ATUAL = MEU_ID;
        ultima_msg_lider = time(NULL); // Reseto meu timer

        // Avisa todo mundo (Broadcast MSG_COORDINATOR)
        Pacote p;
        p.tipo = MSG_COORDINATOR;
        p.id_origem = MEU_ID;
        strcpy(p.conteudo, "NOVO LIDER");
        p.checksum = calcular_checksum(p.conteudo);
        propagar_para_vizinhos(p);
    }
    estou_em_eleicao = 0;
}

// --- THREAD DE HEARTBEAT ---
// Executa em paralelo: A cada 5 segundos, avisa que este nó está vivo.
void *rotina_heartbeat(void *vargp) {
    Pacote p_heartbeat;
    p_heartbeat.tipo = MSG_HEARTBEAT;
    p_heartbeat.id_origem = MEU_ID;
    strcpy(p_heartbeat.conteudo, "HEARTBEAT");
    p_heartbeat.checksum = calcular_checksum(p_heartbeat.conteudo);

    // Inicializa timer
    ultima_msg_lider = time(NULL); 
    
    // Assume provisoriamente que o maior ID da lista é o líder no início
    int maior_id = 0;
    for(int i=0; i<total_nos; i++) if(lista_nos[i].id > maior_id) maior_id = lista_nos[i].id;
    ID_LIDER_ATUAL = maior_id;

    printf(">>> Thread Monitoramento iniciada. Lider atual: %d <<<\n", ID_LIDER_ATUAL);

    while(1) {
        sleep(3); // Verifica a cada 3 segundos

        // 1. Envia meu sinal de vida (Se eu for líder, isso é crucial. Se não for, é bom pra rede)
        for (int i = 0; i < total_nos; i++) {
            if (lista_nos[i].id == MEU_ID) continue;
            int sock = socket(AF_INET, SOCK_STREAM, 0);
            struct sockaddr_in serv_addr;
            serv_addr.sin_family = AF_INET;
            serv_addr.sin_port = htons(lista_nos[i].porta);
            inet_pton(AF_INET, lista_nos[i].ip, &serv_addr.sin_addr);

            // Timeout curto no connect para não travar a thread
            struct timeval timeout;      
            timeout.tv_sec = 1;
            timeout.tv_usec = 0;
            setsockopt(sock, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));

            if (connect(sock, (struct sockaddr *)&serv_addr, sizeof(serv_addr)) == 0) {
                send(sock, &p_heartbeat, sizeof(Pacote), 0);
            }
            close(sock);
        }

        // 2. Verifica se o Líder morreu (Só se eu não for o líder)
        if (ID_LIDER_ATUAL != MEU_ID) {
            double segundos_sem_lider = difftime(time(NULL), ultima_msg_lider);
            
            // Se passar de 10 segundos sem sinal do líder
            if (segundos_sem_lider > 10.0) {
                iniciar_eleicao();
            }
        }
    }
    return NULL;
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

    // --- NOVO: INICIA O CORAÇÃO ---
    pthread_t thread_id;
    pthread_create(&thread_id, NULL, rotina_heartbeat, NULL);

    // LOOP PRINCIPAL
    while(1) {
        printf("\n--- Aguardando instrucao ---\n");
        if ((new_socket = accept(server_fd, (struct sockaddr *)&address, (socklen_t*)&addrlen)) < 0) {
            perror("accept");
            continue;
        }

        memset(&pacote_recebido, 0, sizeof(Pacote));
        int valread = read(new_socket, &pacote_recebido, sizeof(Pacote));
        
        if (valread > 0) {
            // 1. Validação de Segurança (Checksum)
            if (calcular_checksum(pacote_recebido.conteudo) != pacote_recebido.checksum) {
                char *erro = "ERRO: Pacote corrompido (Checksum invalido)";
                send(new_socket, erro, strlen(erro), 0);
                close(new_socket);
                continue;
            }

           // TRATAMENTO DE MENSAGENS ESPECIAIS

            // Caso 1: Recebi um Heartbeat
            if (pacote_recebido.tipo == MSG_HEARTBEAT) {
                // Se veio do Líder, atualizo o relógio
                if (pacote_recebido.id_origem == ID_LIDER_ATUAL) {
                    ultima_msg_lider = time(NULL);
                    // Opcional: printf("Heartbeat do Lider %d recebido.\n", ID_LIDER_ATUAL);
                }
                close(new_socket);
                continue;
            }

            // Caso 2: Recebi aviso de Novo Coordenador
            if (pacote_recebido.tipo == MSG_COORDINATOR) {
                printf(">>> ATENCAO: No %d se declarou o NOVO LIDER! <<<\n", pacote_recebido.id_origem);
                ID_LIDER_ATUAL = pacote_recebido.id_origem;
                ultima_msg_lider = time(NULL); // Renova a confiança
                close(new_socket);
                continue;
            }

            // Caso 3: SQL Normal (MSG_QUERY)
            printf("Comando recebido: %s\n", pacote_recebido.conteudo);

            // 2. Conectar no Banco Local
            // Mapeamento simples: ID 1 usa 3306, ID 2 usa 3307. Se tiver ID 3, usa 3306 de novo (teste)
            int porta_db_local = (MEU_ID == 2) ? 3307 : 3306;
            MYSQL *conn = conectar_banco(porta_db_local);
            
            char resposta[4096] = ""; // Buffer para resposta ao cliente

            if (conn) {
                // 3. Executa a Query Localmente
                if (mysql_query(conn, pacote_recebido.conteudo)) {
                    sprintf(resposta, "Erro SQL no No %d: %s", MEU_ID, mysql_error(conn));
                } else {
                    // SUCESSO!
                    // Verifica se é SELECT (leitura) ou INSERT/UPDATE (escrita)
                    if (strncasecmp(pacote_recebido.conteudo, "SELECT", 6) == 0) {
                        // Lógica de Leitura (Mostra resultados)
                        MYSQL_RES *res = mysql_store_result(conn);
                        if (res) {
                            MYSQL_ROW row;
                            int num_fields = mysql_num_fields(res);
                            sprintf(resposta, "RESULTADOS DO NO %d:\n", MEU_ID);
                            while ((row = mysql_fetch_row(res))) {
                                for(int i=0; i<num_fields; i++) {
                                    strcat(resposta, row[i] ? row[i] : "NULL");
                                    strcat(resposta, " | ");
                                }
                                strcat(resposta, "\n");
                            }
                            mysql_free_result(res);
                        }
                    } else {
                        // Lógica de Escrita (INSERT/UPDATE/DELETE)
                        sprintf(resposta, "Sucesso: Comando executado no No %d.", MEU_ID);
                        
                        // 4. LÓGICA DE REPLICAÇÃO (O PULO DO GATO)
                        // Só repassa para frente se quem mandou foi o CLIENTE (ID 0)
                        // Se quem mandou foi outro nó (ID > 0), eu paro aqui para evitar loop infinito.
                        if (pacote_recebido.id_origem == 0) {
                            printf(">>> Origem Cliente detectada. Iniciando Broadcast...\n");
                            
                            // Marca que agora EU (este nó) sou a origem da replicação
                            pacote_recebido.id_origem = MEU_ID; 
                            
                            propagar_para_vizinhos(pacote_recebido);
                            
                            strcat(resposta, "\n(Replicacao enviada para a rede)");
                        } else {
                            printf(">>> Mensagem de replicacao recebida do No %d. Nao vou repassar.\n", pacote_recebido.id_origem);
                        }
                    }
                }
                mysql_close(conn);
            } else {
                sprintf(resposta, "ERRO CRITICO: No %d nao conseguiu conectar no banco local (%d)!", MEU_ID, porta_db_local);
            }

            // Devolve a resposta para quem chamou (seja Cliente ou outro Nó)
            send(new_socket, resposta, strlen(resposta), 0);
        }
        close(new_socket);
    }
    return 0;
}