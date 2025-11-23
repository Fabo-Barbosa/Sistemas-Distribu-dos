#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/types.h> 
#include <sys/socket.h>
#include <netinet/in.h>
#include <sys/wait.h>

// Função para tratar erros padrão [cite: 69]
void error(const char *msg) {
    perror(msg);
    exit(1);
}

// Função para lidar com processos zumbis (limpeza de processos filhos)
void sigchld_handler(int s) {
    while(waitpid(-1, NULL, WNOHANG) > 0);
}

// Lógica de atendimento ao cliente (Processo Filho)
void doprocessing(int sock) {
    int n;
    char buffer[4096]; // Buffer aumentado para caber códigos maiores
    char filename[50], cmd_compile[256], cmd_run[256];
    char output_buffer[4096];
    FILE *fp;

    bzero(buffer, 4096);
    
    // 1. Ler o código enviado pelo cliente [cite: 103]
    n = read(sock, buffer, 4095);
    if (n < 0) {
        perror("ERROR reading from socket");
        exit(1);
    }

    printf("Código recebido (%d bytes). Processando...\n", n);

    // 2. Criar nomes de arquivos únicos baseados no PID (para concorrência segura)
    int pid = getpid();
    sprintf(filename, "temp_%d.kt", pid);
    
    // 3. Salvar o código em arquivo .kt
    fp = fopen(filename, "w");
    if (fp == NULL) {
        write(sock, "Erro interno ao criar arquivo no servidor.", 42);
        exit(1);
    }
    fprintf(fp, "%s", buffer);
    fclose(fp);

    // 4. Compilar (Kotlin)
    // Redireciona erros (stderr) para arquivo de erro
    sprintf(cmd_compile, "kotlinc %s -include-runtime -d temp_%d.jar 2> erro_%d.txt", filename, pid, pid);
    int status = system(cmd_compile);

    // Preparar resposta
    bzero(output_buffer, 4096);

    if (status != 0) {
        char err_file[50];
        sprintf(err_file, "erro_%d.txt", pid);
        fp = fopen(err_file, "r");
        
        strcat(output_buffer, "--- ERRO DE COMPILAÇÃO ---\n");
        if (fp) {
            fread(output_buffer + strlen(output_buffer), 1, 4000, fp);
            fclose(fp);
        }
    } else {
        sprintf(cmd_run, "java -jar temp_%d.jar > saida_%d.txt", pid, pid);
        system(cmd_run);

        char out_file[50];
        sprintf(out_file, "saida_%d.txt", pid);
        fp = fopen(out_file, "r");

        if (fp) {
            fread(output_buffer, 1, 4095, fp);
            fclose(fp);
        } else {
            strcpy(output_buffer, "Programa executado, mas sem saída (stdout vazio).");
        }
    }
    n = write(sock, output_buffer, strlen(output_buffer));
    if (n < 0) perror("ERROR writing to socket");
    char cleanup[256];
    sprintf(cleanup, "rm temp_%d.kt temp_%d.jar erro_%d.txt saida_%d.txt 2>/dev/null", pid, pid, pid, pid);
    system(cleanup);
}

int main(int argc, char *argv[]) {
    int sockfd, newsockfd, portno;
    socklen_t clilen;
    struct sockaddr_in serv_addr, cli_addr;

    if (argc < 2) {
        fprintf(stderr, "ERRO, nenhuma porta fornecida\n");
        exit(1);
    }

    // Criação do Socket [cite: 84]
    sockfd = socket(AF_INET, SOCK_STREAM, 0);
    if (sockfd < 0) error("ERROR opening socket");

    // Configuração do Endereço [cite: 88-91]
    bzero((char *) &serv_addr, sizeof(serv_addr));
    portno = atoi(argv[1]);
    serv_addr.sin_family = AF_INET;
    serv_addr.sin_addr.s_addr = INADDR_ANY;
    serv_addr.sin_port = htons(portno);

    // Bind [cite: 92]
    if (bind(sockfd, (struct sockaddr *) &serv_addr, sizeof(serv_addr)) < 0)
        error("ERROR on binding");

    // Listen (Fila de espera de 5) [cite: 95]
    listen(sockfd, 5);
    
    // Trata processos filhos mortos para evitar zumbis
    signal(SIGCHLD, sigchld_handler);

    printf("Servidor de Compilação KOTLIN rodando na porta %d...\n", portno);

    // LOOP INFINITO PARA ACEITAR MÚLTIPLAS REQUISIÇÕES 
    while (1) {
        clilen = sizeof(cli_addr);
        // Accept (Bloqueante) [cite: 97]
        newsockfd = accept(sockfd, (struct sockaddr *) &cli_addr, &clilen);
        if (newsockfd < 0) error("ERROR on accept");

        // Fork cria um processo filho para lidar com o cliente
        int pid = fork();
        
        if (pid < 0) {
            error("ERROR on fork");
        }
        
        if (pid == 0) {
            // Este é o processo FILHO
            close(sockfd); // Filho não precisa do socket de escuta
            doprocessing(newsockfd);
            close(newsockfd); // Fecha a conexão após terminar
            exit(0); // Encerra o filho
        }
        else {
            // Este é o processo PAI
            close(newsockfd); // Pai não precisa do socket do cliente, volta a escutar
        }
    }
    return 0; 
}
