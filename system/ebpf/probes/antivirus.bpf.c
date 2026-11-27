// nexora-antivirus eBPF: observacion de aperturas en directorios de descargas.
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>
#include "../include/nexora_events.h"

struct {
    __uint(type, BPF_MAP_TYPE_RINGBUF);
    __uint(max_entries, 1 << 20);
} av_events SEC(".maps");

SEC("lsm/file_open")
int BPF_PROG(av_file_open, struct file *file, __u32 ret)
{
    struct nexora_event *e;
    const unsigned char *name;
    char buf[128];

    name = bpf_d_path ? NULL : NULL;  /* placeholder: ruta via helper en kernel >= 5.10 */
    e = bpf_ringbuf_reserve(&av_events, sizeof(*e), 0);
    if (!e)
        return 0;
    e->ts_ns = bpf_ktime_get_ns();
    e->pid = (bpf_get_current_pid_tgid() >> 32);
    e->uid = (bpf_get_current_uid_gid() & 0xffffffff);
    e->op = NEXORA_DOWNLOAD;
    e->arg = ret;
    bpf_get_current_comm(e->comm, sizeof(e->comm));
    e->path[0] = '\0';
    bpf_ringbuf_submit(e, 0);
    return 0;
}

char LICENSE[] SEC("license") = "GPL";
