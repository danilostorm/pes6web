#!/usr/bin/env python3
"""Experimental GE FINISH callback bridge; only open-source PSP host changes.

The GE worker records command metadata. Guest callback functions are run on
the CPU scheduler, not the GPU worker. Requires PES6_ENABLE_GE_FINISH_CALLBACKS=1.
"""
import argparse
from pathlib import Path


def once(src, old, new, label):
    if src.count(old) != 1:
        raise RuntimeError(f"{label}: pinned source changed or partially patched")
    return src.replace(old, new, 1)


def scoped(src, start, end, old, new, label):
    if src.count(start) != 1 or src.count(end) != 1:
        raise RuntimeError(f"{label}: ambiguous function boundaries")
    a = src.index(start)
    b = src.index(end, a + len(start))
    body = src[a:b]
    if body.count(old) != 1:
        raise RuntimeError(f"{label}: unexpected function body")
    return src[:a] + body.replace(old, new, 1) + src[b:]


def plan(files):
    if "PES6_GE_FINISH_QUEUE" in files["ge_worker.hpp"]:
        required = {
            "ge_worker.cpp": "GeWorker::take_finish_events()",
            "ge.cpp": "last_finish_ = GeFinish",
            "ge.hpp": "struct GeFinish",
            "kernel.cpp": "Kernel::poll_ge_finish_callbacks()",
            "kernel.hpp": "ge_finish_callbacks_",
        }
        if any(token not in files[path] for path, token in required.items()):
            raise RuntimeError("Incomplete GE FINISH queue patch")
        return files, False
    f = dict(files)
    f["ge.hpp"] = once(f["ge.hpp"], "    struct Stats {\n",
        """    struct GeFinish {
        bool valid{};
        std::uint32_t token{}, next_pc{};
    };
    [[nodiscard]] GeFinish last_finish() const noexcept { return last_finish_; }

    struct Stats {
""", "GE finish metadata")
    f["ge.hpp"] = once(f["ge.hpp"], "    void execute(std::uint32_t op);\n",
        "    GeFinish last_finish_{};\n    void execute(std::uint32_t op);\n", "GE finish state")
    f["ge.cpp"] = once(f["ge.cpp"], "    ++stats_.lists;\n",
        "    ++stats_.lists;\n    last_finish_ = {};\n", "GE list reset")
    f["ge.cpp"] = once(f["ge.cpp"],
        "    const std::uint32_t data = op & 0x00FFFFFFu;\n",
        "    const std::uint32_t data = op & 0x00FFFFFFu;\n"
        "    if (cmd == kFinish) last_finish_ = GeFinish{true, data, pc_};\n",
        "GE finish opcode")
    f["ge_worker.hpp"] = once(f["ge_worker.hpp"], "#include <thread>\n",
        "#include <thread>\n#include <vector>\n", "worker include")
    f["ge_worker.hpp"] = once(f["ge_worker.hpp"],
        "    [[nodiscard]] bool done(std::uint32_t id) const noexcept;\n",
        """    // PES6_GE_FINISH_QUEUE: thread-safe completed graphics-list metadata.
    struct FinishEvent { std::uint32_t id{}, token{}, next_pc{}; };
    [[nodiscard]] std::vector<FinishEvent> take_finish_events();
    [[nodiscard]] bool done(std::uint32_t id) const noexcept;
""", "worker event API")
    f["ge_worker.hpp"] = once(f["ge_worker.hpp"],
        "    std::deque<std::function<void()>> queue_;\n",
        """    std::deque<std::function<void()>> queue_;
    std::mutex finish_mutex_;
    std::deque<FinishEvent> finish_events_;
    void capture_finish(std::uint32_t id);
""", "worker event queue")
    f["ge_worker.cpp"] = once(f["ge_worker.cpp"], "            completed_.store(id);\n",
        "            capture_finish(id);\n            completed_.store(id);\n", "completed list")
    f["ge_worker.cpp"] = once(f["ge_worker.cpp"], "            completed_.store(stalled_id_);\n",
        "            capture_finish(stalled_id_);\n            completed_.store(stalled_id_);\n", "stalled list")
    f["ge_worker.cpp"] = once(f["ge_worker.cpp"],
        "bool GeWorker::done(std::uint32_t id) const noexcept {\n",
        """void GeWorker::capture_finish(std::uint32_t id) {
    const auto done = ge_.last_finish();
    if (!done.valid) return;
    std::lock_guard<std::mutex> guard(finish_mutex_);
    if (finish_events_.size() < 4096u)
        finish_events_.push_back(FinishEvent{id, done.token, done.next_pc});
}

std::vector<GeWorker::FinishEvent> GeWorker::take_finish_events() {
    std::lock_guard<std::mutex> guard(finish_mutex_);
    std::vector<FinishEvent> result(finish_events_.begin(), finish_events_.end());
    finish_events_.clear();
    return result;
}

bool GeWorker::done(std::uint32_t id) const noexcept {
""", "event collection")
    f["kernel.hpp"] = once(f["kernel.hpp"],
        "    std::unique_ptr<GeWorker> ge_worker_;\n",
        """    std::unique_ptr<GeWorker> ge_worker_;
    struct GeCallbackSlot {
        bool used{};
        std::uint32_t signal_fn{}, signal_arg{}, finish_fn{}, finish_arg{}, gp{};
    };
    std::array<GeCallbackSlot, 16u> ge_finish_callbacks_{};
    std::map<std::uint32_t, std::uint32_t> ge_list_callback_ids_;
    void poll_ge_finish_callbacks();
""", "kernel callback state")
    f["kernel.hpp"] = once(f["kernel.hpp"],
        "    void sceGeSetCallback(Ctx &ctx);\n",
        "    void sceGeSetCallback(Ctx &ctx);\n    void sceGeUnsetCallback(Ctx &ctx);\n",
        "kernel callback declaration")
    f["kernel.cpp"] = once(f["kernel.cpp"],
        '    hle("sceGe_user", 0x05DB22CEu, "sceGeUnsetCallback", &Kernel::return_zero);\n',
        '    hle("sceGe_user", 0x05DB22CEu, "sceGeUnsetCallback", &Kernel::sceGeUnsetCallback);\n',
        "callback unregister HLE")
    f["kernel.cpp"] = once(f["kernel.cpp"],
        "    if (halted_) return false;\n    poll_io();\n",
        "    if (halted_) return false;\n    poll_io();\n    poll_ge_finish_callbacks();\n",
        "CPU dispatch per host frame")
    f["kernel.cpp"] = once(f["kernel.cpp"],
        """void Kernel::sceGeListEnQueue(Ctx &ctx) {
    finish(ctx, ge_worker_->enqueue(ctx.gpr[4], ctx.gpr[5]));
}
""",
        """void Kernel::sceGeListEnQueue(Ctx &ctx) {
    const auto id = ge_worker_->enqueue(ctx.gpr[4], ctx.gpr[5]);
    const auto callback = ctx.gpr[6];
    if (std::getenv("PES6_ENABLE_GE_FINISH_CALLBACKS") != nullptr &&
        callback < ge_finish_callbacks_.size() &&
        ge_finish_callbacks_[callback].used &&
        ge_finish_callbacks_[callback].finish_fn != 0u)
        ge_list_callback_ids_[id] = callback;
    // Drop very old metadata if the renderer is unable to keep up; do not
    // discard merely by completed ID because event arrival is cross-thread.
    if (ge_list_callback_ids_.size() > 8192u)
        ge_list_callback_ids_.erase(ge_list_callback_ids_.begin());
    finish(ctx, id);
}
""", "GE callback per display list")
    f["kernel.cpp"] = scoped(f["kernel.cpp"],
        "void Kernel::sceGeSetCallback(Ctx &ctx) {",
        "void Kernel::sceGeGetCmd(Ctx &ctx) {",
        "    finish(ctx, 0u);\n}\n",
        """    const auto *raw = rt_.memory().raw_pointer(ctx.gpr[4], 16u);
    if (raw == nullptr) {
        finish(ctx, 0x800200D3u); // invalid guest pointer
        return;
    }
    std::uint32_t words[4]{};
    std::memcpy(words, raw, sizeof(words));
    for (std::uint32_t id = 0u; id < ge_finish_callbacks_.size(); ++id) {
        auto &cb = ge_finish_callbacks_[id];
        if (cb.used) continue;
        cb = GeCallbackSlot{true, words[0], words[1], words[2], words[3], ctx.gpr[28]};
        finish(ctx, id);
        return;
    }
    finish(ctx, 0x80020190u); // no free callback IDs
}

void Kernel::sceGeUnsetCallback(Ctx &ctx) {
    const auto id = ctx.gpr[4];
    if (id >= ge_finish_callbacks_.size() || !ge_finish_callbacks_[id].used) {
        finish(ctx, 0x800200CBu);
        return;
    }
    ge_finish_callbacks_[id] = {};
    finish(ctx, 0u);
}

void Kernel::poll_ge_finish_callbacks() {
    // Transfer completed events to guest CPU threads, never the GPU thread.
    const auto events = ge_worker_->take_finish_events();
    if (std::getenv("PES6_ENABLE_GE_FINISH_CALLBACKS") == nullptr) {
        ge_list_callback_ids_.clear();
        return;
    }
    bool spawned = false;
    for (const auto &event : events) {
        const auto pending = ge_list_callback_ids_.find(event.id);
        if (pending == ge_list_callback_ids_.end()) continue;
        const auto callback_id = pending->second;
        ge_list_callback_ids_.erase(pending);
        if (callback_id >= ge_finish_callbacks_.size()) continue;
        const auto &cb = ge_finish_callbacks_[callback_id];
        if (!cb.used || cb.finish_fn == 0u) continue;
        Thread t;
        t.uid = new_uid();
        t.name = "pspweb_ge_finish";
        t.entry = cb.finish_fn;
        t.priority = 0x10;
        t.stack_size = 0x4000u;
        t.stack_block = allocate("stack:ge_finish", 1u, t.stack_size, 0u);
        if (t.stack_block < 0) continue;
        t.stack_top = blocks_.at(t.stack_block).address + t.stack_size;
        t.gp = cb.gp;
        const auto uid = t.uid;
        auto &stored = threads_[uid] = std::move(t);
        start_thread(stored, 0u, {});
        // PPSSPP uses the FINISH subinterrupt token and registered user arg.
        stored.ctx.gpr[4] = event.token & 0xFFFFu;
        stored.ctx.gpr[5] = cb.finish_arg;
        stored.ctx.gpr[6] = event.next_pc;
        // Reclaim short-lived callback stack/thread on normal guest return.
        guest_calls_[uid] = GuestCall{-1, {}};
        if (std::getenv("PES6_TRACE_GE_FINISH_DISPATCH") != nullptr) {
            static std::uint32_t printed = 0u;
            if (printed++ < 24u)
                std::cerr << "[ge-finish-dispatch] frame=" << display_.vcount
                          << " cbid=" << callback_id << " token=" << event.token
                          << " entry=" << hex(cb.finish_fn) << "\n";
        }
        make_ready(stored, true);
        spawned = true;
    }
    if (spawned && current() != nullptr) {
        auto *active = current();
        active->ctx = rt_.cpu();
        make_ready(*active);
        current_uid_ = -1;
        psprecomp::set_runtime_thread_identity(-1, "ge-finish-pending");
    }
}

""", "GPU FINISH callback delivery")

    return f, True


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("checkout", type=Path)
    args = p.parse_args()
    base = args.checkout / "PSPRecomp/profiles/web/host"
    names = ("ge.hpp", "ge.cpp", "ge_worker.hpp", "ge_worker.cpp", "kernel.hpp", "kernel.cpp")
    original = {name: (base / name).read_text() for name in names}
    updated, changed = plan(original)
    if changed:
        for name in names:
            if updated[name] != original[name]:
                (base / name).write_text(updated[name])
    print("Experimental GE FINISH callback bridge:", "applied" if changed else "already installed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
