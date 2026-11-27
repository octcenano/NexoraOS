#ifndef NEXORA_EVENTS_H
#define NEXORA_EVENTS_H

enum nexora_op {
    NEXORA_EXEC      = 1,
    NEXORA_CONNECT   = 2,
    NEXORA_SETUID    = 3,
    NEXORA_CHMOD     = 4,
    NEXORA_SENSITIVE = 5,
    NEXORA_DOWNLOAD  = 6,
    NEXORA_NET_DENY  = 7,
};

struct nexora_event {
    __u64 ts_ns;
    __u32 pid;
    __u32 uid;
    __u32 op;
    __u32 arg;          /* puerto, modo, valor extra */
    char   comm[16];
    char   path[256];
};

#endif
