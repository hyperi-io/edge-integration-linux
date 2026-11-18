/* Median ns per syscall-heavy operation over 7 runs, to compare audit rulesets. */
#define _GNU_SOURCE
#include <arpa/inet.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#define RUNS 7

static double now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec * 1e9 + (double)ts.tv_nsec;
}

static int cmp(const void *a, const void *b) {
    double x = *(const double *)a, y = *(const double *)b;
    return (x > y) - (x < y);
}

static void w_getppid(long n) {
    for (long i = 0; i < n; i++) syscall(SYS_getppid);
}

static void w_open(long n) {
    for (long i = 0; i < n; i++) {
        int fd = open("/etc/hostname", O_RDONLY);
        if (fd >= 0) close(fd);
    }
}

static void w_stat(long n) {
    struct stat st;
    for (long i = 0; i < n; i++) stat("/usr/bin/true", &st);
}

static void w_write(long n) {
    char path[] = "/tmp/auditbench.XXXXXX";
    int fd = mkstemp(path);
    char buf[64] = {0};
    for (long i = 0; i < n; i++) {
        if (pwrite(fd, buf, sizeof buf, 0) < 0) break;
    }
    close(fd);
    unlink(path);
}

static void w_exec(long n) {
    for (long i = 0; i < n; i++) {
        pid_t p = fork();
        if (p == 0) {
            execl("/usr/bin/true", "true", (char *)NULL);
            _exit(127);
        }
        waitpid(p, NULL, 0);
    }
}

static void w_connect(long n) {
    int ls = socket(AF_INET, SOCK_STREAM, 0);
    struct sockaddr_in a = {.sin_family = AF_INET, .sin_addr.s_addr = htonl(INADDR_LOOPBACK)};
    socklen_t al = sizeof a;
    bind(ls, (struct sockaddr *)&a, sizeof a);
    listen(ls, 4096);
    getsockname(ls, (struct sockaddr *)&a, &al);
    for (long i = 0; i < n; i++) {
        int s = socket(AF_INET, SOCK_STREAM, 0);
        connect(s, (struct sockaddr *)&a, sizeof a);
        int c = accept(ls, NULL, NULL);
        close(s);
        if (c >= 0) close(c);
    }
    close(ls);
}

struct workload {
    const char *name;
    void (*fn)(long);
    long n;
};

int main(void) {
    struct workload w[] = {
        {"getppid", w_getppid, 2000000},
        {"pwrite", w_write, 1000000},
        {"open_close", w_open, 300000},
        {"stat", w_stat, 300000},
        {"connect", w_connect, 20000},
        {"fork_exec", w_exec, 2000},
    };
    for (size_t k = 0; k < sizeof w / sizeof w[0]; k++) {
        double r[RUNS];
        w[k].fn(w[k].n / 10);
        for (int i = 0; i < RUNS; i++) {
            double t0 = now_ns();
            w[k].fn(w[k].n);
            r[i] = (now_ns() - t0) / (double)w[k].n;
        }
        qsort(r, RUNS, sizeof r[0], cmp);
        printf("%s %.1f\n", w[k].name, r[RUNS / 2]);
    }
    return 0;
}
