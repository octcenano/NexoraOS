// nexora-sentinel eBPF: deteccion conductual (exec, connect, setuid, chmod).
#include "vmlinux.h"
#include <bpf/bpf_helpers.h>
#include <bpf/bpf_tracing.h>
#include "../include/nexora_events.h"

struct {
    __uint(type, BPF_MAP_TYPE_RINGBUF);
    __uint(max_entries, 1 << 24);
} events SEC(".maps");

static int push_event(__u32 op, __u32 arg, const char *path)
{
    struct nexora_event *e = bpf_ringbuf_reserve(&events, sizeof(*e), 0);
    if (!e)
        return 0;
    e->ts_ns = bpf_ktime_get_ns();
    e->pid = (bpf_get_current_pid_tgid() >> 32);
    e->uid = (bpf_get_current_uid_gid() & 0xffffffff);
    e->op = op;
    e->arg = arg;
    bpf_get_current_comm(e->comm, sizeof(e->comm));
    if (path)
        bpf_probe_read_kernel_str(e->path, sizeof(e->path), path);
    else
        e->path[0] = '\0';
    bpf_ringbuf_submit(e, 0);
    return 0;
}

SEC("tracepoint/sched/sched_process_exec")
int tp_exec(void *ctx) { return push_event(NEXORA_EXEC, 0, NULL); }

SEC("tracepoint/syscalls/sys_enter_connect")
int tp_connect(struct trace_event_raw_sys_enter *ctx)
{
    return push_event(NEXORA_CONNECT, 0, NULL);
}

SEC("tracepoint/syscalls/sys_enter_setreuid")
int tp_setreuid(struct trace_event_raw_sys_enter *ctx)
{
    __u32 new_uid = (__u32)ctx->args[1];
    if (new_uid == 0)
        return push_event(NEXORA_SETUID, new_uid, NULL);
    return 0;
}

SEC("tracepoint/syscalls/sys_enter_fchmodat")
int tp_fchmodat(struct trace_event_raw_sys_enter *ctx)
{
    __u32 mode = (__u32)ctx->args[2];
    if ((mode & 06000) == 06000 || (mode & 0002) || (mode & 0020))
        return push_event(NEXORA_CHMOD, mode, NULL);
    return 0;
}

SEC("lsm/file_open")
int BPF_PROG(lsm_file_open, struct file *file, __u32 ret)
{
    return 0;  /* observacion pasiva; el veto se decide en espacio de usuario */
}

char LICENSE[] SEC("license") = "GPL";
