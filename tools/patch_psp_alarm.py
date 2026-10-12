#!/usr/bin/env python3
"""Basic PSP sceKernelSetAlarm scheduling in the recompiled host runtime.

Guest handlers run on temporary guest threads, not on the host thread.
The handler's unsigned return value is its next interval in microseconds;
zero cancels the alarm. No retail game source or data is included.
"""
from pathlib import Path
import argparse


def once(source, old, new):
    if new in source:
        return source
    if source.count(old) != 1:
        raise RuntimeError("Unexpected PSPRecomp source layout; alarm patch not applied")
    return source.replace(old, new, 1)


def plan(h, k):
    original = (h, k)
    h = once(h, "    void sceKernelGetSystemTimeLow(Ctx &ctx);\n",
        "    void sceKernelSetAlarm(Ctx &ctx);\n"
        "    void sceKernelGetSystemTimeLow(Ctx &ctx);\n")
    h = once(h,
        "    std::map<std::int32_t, GuestCall> guest_calls_;   // callback thread uid -> waiting caller\n",
        "    std::map<std::int32_t, GuestCall> guest_calls_;   // callback thread uid -> waiting caller\n"
        "    struct Alarm { std::uint64_t due{}; std::uint32_t handler{}, common{}, gp{}; bool running{}; };\n"
        "    std::map<std::int32_t, Alarm> alarms_;\n")
    k = once(k,
        '    hle(tm, 0xE81CAF8Fu, "sceKernelCreateCallback", &Kernel::sceKernelCreateCallback);\n',
        '    hle(tm, 0xE81CAF8Fu, "sceKernelCreateCallback", &Kernel::sceKernelCreateCallback);\n'
        '    hle(tm, 0x6652B8CAu, "sceKernelSetAlarm", &Kernel::sceKernelSetAlarm);\n')
    k = once(k,
        "void Kernel::sceKernelGetSystemTimeLow(Ctx &ctx) {",
        """void Kernel::sceKernelSetAlarm(Ctx &ctx) {
    if (ctx.gpr[5] == 0u) {
        finish(ctx, 0x800200D2u); // invalid argument: missing handler
        return;
    }
    const auto uid = new_uid();
    Alarm alarm;
    alarm.due = now_us() + std::max(ctx.gpr[4], 1u);
    alarm.handler = ctx.gpr[5];
    alarm.common = ctx.gpr[6];
    alarm.gp = ctx.gpr[28];
    alarms_[uid] = alarm;
    finish(ctx, static_cast<std::uint32_t>(uid));
}

void Kernel::sceKernelGetSystemTimeLow(Ctx &ctx) {""")
    k = once(k,
        "void Kernel::poll_waits() {\n    const std::uint64_t now = now_us();\n",
        """void Kernel::poll_waits() {
    const std::uint64_t now = now_us();
    // Fire due PSP alarms on separate guest threads. Return 0 terminates an
    // alarm, a positive return schedules it for the requested microseconds.
    for (auto &[alarm_uid, alarm] : alarms_) {
        if (alarm.running || now < alarm.due) continue;
        Thread t;
        t.uid = new_uid();
        t.name = "pspweb_alarm";
        t.entry = alarm.handler;
        t.priority = 16;
        t.stack_size = 0x8000u;
        t.stack_block = allocate("stack:alarm", 1u, t.stack_size, 0u);
        if (t.stack_block < 0) continue;
        t.stack_top = blocks_.at(t.stack_block).address + t.stack_size;
        t.gp = alarm.gp;
        const std::int32_t tid = t.uid;
        auto &stored = threads_[tid] = std::move(t);
        start_thread(stored, 0u, {});
        stored.ctx.gpr[4] = alarm.common;
        alarm.running = true;
        guest_calls_[tid] = GuestCall{0, [this, alarm_uid](std::uint32_t delay) {
            const auto found = alarms_.find(alarm_uid);
            if (found != alarms_.end()) {
                if (delay == 0u) alarms_.erase(found);
                else {
                    found->second.due = now_us() + delay;
                    found->second.running = false;
                }
            }
            return 0u;
        }};
    }
""")
    k = once(k,
        "    return earliest;\n}\n\nvoid Kernel::start_thread(",
        """    for (const auto &[uid, alarm] : alarms_) {
        (void)uid;
        if (!alarm.running && (earliest == 0u || alarm.due < earliest))
            earliest = alarm.due;
    }
    return earliest;
}

void Kernel::start_thread(""")
    return h, k, (h, k) != original


def main():
    p = argparse.ArgumentParser()
    p.add_argument("checkout", type=Path)
    args = p.parse_args()
    folder = args.checkout / "PSPRecomp/profiles/web/host"
    header = folder / "kernel.hpp"
    kernel = folder / "kernel.cpp"
    old = (header.read_text(), kernel.read_text())
    updated = plan(*old)
    if updated[2]:
        header.write_text(updated[0])
        kernel.write_text(updated[1])
    print("PSP alarm guest-thread scheduling:", "applied" if updated[2] else "already applied")


if __name__ == "__main__":
    main()
