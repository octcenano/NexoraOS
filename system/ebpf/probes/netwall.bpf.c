// nexora-netwall eBPF: veto de conectividad por cgroup con mapa de denegacion.
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include "../include/nexora_events.h"

struct {
    __uint(type, BPF_MAP_TYPE_HASH);
    __uint(max_entries, 4096);
    __type(key, __u16);
    __type(value, __u8);
} deny_map SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_RINGBUF);
    __uint(max_entries, 1 << 16);
} deny_events SEC(".maps");

SEC("cgroup/connect4")
int cg_connect4(struct bpf_sock_addr *ctx)
{
    __u16 port = (__u16)ctx->user_port;
    __u8 *denied = bpf_map_lookup_elem(&deny_map, &port);
    if (denied && *denied) {
        struct nexora_event *e = bpf_ringbuf_reserve(&deny_events, sizeof(*e), 0);
        if (e) {
            e->op = NEXORA_NET_DENY;
            e->arg = port;
            e->pid = (bpf_get_current_pid_tgid() >> 32);
            e->path[0] = '\0';
            bpf_ringbuf_submit(e, 0);
        }
        return 0;  /* denegar conexion */
    }
    return 1;     /* permitir */
}

char LICENSE[] SEC("license") = "GPL";
