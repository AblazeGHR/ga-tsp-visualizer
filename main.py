# -*- coding: utf-8 -*-
"""GA-TSP 命令行入口。

依次对 n=10 / n=20 的随机 TSP 实例运行 纯GA 与 GA+2-opt，
输出最优路径成本，并把三张图保存到 results/ 目录。

用法:
    E:/software/miniforge/python.exe main.py            # 默认 n=10, 20
    E:/software/miniforge/python.exe main.py --seed 1   # 换随机种子
"""

import argparse
import os
import time

import matplotlib
matplotlib.use("Agg")                     # 无界面后端，直接保存图片
import matplotlib.pyplot as plt

import tsp_ga

# 中文字体（Windows 自带微软雅黑/黑体），避免图内中文显示为方块
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(HERE, "results")


# ---------- 基准求解 ----------

def try_or_tools(cities):
    """尝试用 OR-Tools 求精确/近最优基准；未安装返回 None。"""
    try:
        from ortools.constraint_solver import pywrapcp, routing_enums_pb2
    except ImportError:
        return None
    n = len(cities)
    manager = pywrapcp.RoutingIndexManager(n, 1, 0)
    routing = pywrapcp.RoutingModel(manager)

    scale = 100000  # OR-Tools 要求整数权重，放大距离以减小取整误差

    def dist_cb(i, j):
        a, b = manager.IndexToNode(i), manager.IndexToNode(j)
        x, y = cities[a], cities[b]
        return int(round(tsp_ga.math.hypot(x[0] - y[0], x[1] - y[1]) * scale))

    transit = routing.RegisterTransitCallback(dist_cb)
    routing.SetArcCostEvaluatorOfAllVehicles(transit)
    search = pywrapcp.DefaultRoutingSearchParameters()
    search.time_limit.seconds = 10
    assignment = routing.SolveWithParameters(search)
    if assignment is None:
        return None
    return int(assignment.ObjectiveValue()) / scale


def baseline_for(cities, dist, n):
    """n<=10 用穷举法求精确最优；n>10 用 OR-Tools（未装则返回 None）。"""
    if n <= 10:
        cost, _ = tsp_ga.exhaustive_solve(cities, dist)
        return cost, "穷举精确解"
    cost = try_or_tools(cities)
    return (cost, "OR-Tools") if cost is not None else (None, None)


# ---------- 绘图 ----------

def plot_convergence(hist_ga, hist_ga2, n, path):
    """收敛曲线：纯GA 与 GA+2-opt 的最优成本随代数下降情况。"""
    fig, ax = plt.subplots(figsize=(6, 4.2))
    ax.plot(hist_ga, label="GA")
    ax.plot(hist_ga2, label="GA+2-opt")
    ax.set_title(f"n={n} 收敛曲线")
    ax.set_xlabel("代数")
    ax.set_ylabel("最优路径长度")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_best_route(cities, route, title, path):
    """画一条回路：按顺序连线并首尾闭合。"""
    pts = [cities[i] for i in route] + [cities[route[0]]]
    fig, ax = plt.subplots(figsize=(5.2, 5.2))
    ax.plot([p[0] for p in pts], [p[1] for p in pts], "o-", lw=1.6, ms=5)
    ax.set_title(title)
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_two_opt_compare(cities, route_before, route_after, cost_before,
                         cost_after, n, path):
    """2-opt 改进前后路径对比图（并排两张子图）。"""
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 5))
    for ax, route, cost, tag in (
        (axes[0], route_before, cost_before, "改进前"),
        (axes[1], route_after, cost_after, "改进后"),
    ):
        pts = [cities[i] for i in route] + [cities[route[0]]]
        ax.plot([p[0] for p in pts], [p[1] for p in pts], "o-", lw=1.6, ms=5)
        ax.set_title(f"{tag}  cost = {cost:.4f}")
        ax.set_xlabel("x")
        ax.set_ylabel("y")
        ax.grid(alpha=0.3)
    fig.suptitle(f"n={n}  2-opt 局部搜索改进前后")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ---------- 主流程 ----------

def converged_gen(history, best_cost):
    """最早达到全局最优的那一代（用于报告收敛速度）。"""
    for g, c in enumerate(history):
        if c == best_cost:
            return g
    return len(history) - 1


def fmt_result(r, key):
    """格式化一行 GA 结果：cost / 收敛代数 / 耗时 / gap。"""
    cost, conv, t = r[f"cost_{key}"], r[f"conv_{key}"], r[f"t_{key}"]
    gap = r[f"gap_{key}"]
    s = f"cost = {cost:.4f}   收敛于第{conv}代   耗时{t:.1f}s"
    if gap is not None:
        s += f"   gap = {gap:.2f}%"
    return s


def fmt_cost(r, key):
    """格式化一行后处理 2-opt 结果。"""
    cost = r[f"cost_{key}"]
    gap = r[f"gap_{key}"]
    s = f"{cost:.4f}"
    if gap is not None:
        s += f"   gap = {gap:.2f}%"
    return s


def run_instance(n, seed, pop_size, generations, results_dir):
    """跑单个规模 n 的完整实验，返回结果字典。"""
    cities = tsp_ga.make_random_instance(n, seed)

    t0 = time.time()
    cost_ga, route_ga, hist_ga, _, dist = tsp_ga.solve_tsp(
        n, seed=seed, pop_size=pop_size, generations=generations, use_2opt=False)
    t_ga = time.time() - t0

    t0 = time.time()
    cost_ga2, route_ga2, hist_ga2, _, _ = tsp_ga.solve_tsp(
        n, seed=seed, pop_size=pop_size, generations=generations, use_2opt=True)
    t_ga2 = time.time() - t0

    # 对纯GA结果做一次 2-opt 后处理，用作“改进前后对比图”
    route_post = tsp_ga.two_opt(route_ga, dist)
    cost_post = tsp_ga.route_cost(route_post, dist)

    baseline, baseline_src = baseline_for(cities, dist, n)

    gap = lambda c: (c - baseline) / baseline * 100 if baseline else None

    return {
        "n": n, "cities": cities, "dist": dist,
        "cost_ga": cost_ga, "route_ga": route_ga, "hist_ga": hist_ga, "t_ga": t_ga,
        "cost_ga2": cost_ga2, "route_ga2": route_ga2, "hist_ga2": hist_ga2, "t_ga2": t_ga2,
        "cost_post": cost_post, "route_post": route_post,
        "baseline": baseline, "baseline_src": baseline_src,
        "gap_ga": gap(cost_ga), "gap_ga2": gap(cost_ga2), "gap_post": gap(cost_post),
        "conv_ga": converged_gen(hist_ga, cost_ga),
        "conv_ga2": converged_gen(hist_ga2, cost_ga2),
    }


def main():
    parser = argparse.ArgumentParser(description="遗传算法解 TSP 演示")
    parser.add_argument("--seed", type=int, default=42, help="随机种子")
    parser.add_argument("--n1", type=int, default=10, help="小规模城市数")
    parser.add_argument("--n2", type=int, default=20, help="大规模城市数")
    parser.add_argument("--pop-size", type=int, default=100, help="种群大小")
    parser.add_argument("--generations", type=int, default=300, help="进化代数")
    args = parser.parse_args()

    os.makedirs(RESULTS_DIR, exist_ok=True)
    print(f"随机种子 seed = {args.seed}  pop_size = {args.pop_size}  generations = {args.generations}")
    print("=" * 78)

    rows = []
    for n in (args.n1, args.n2):
        r = run_instance(n, args.seed, args.pop_size, args.generations, RESULTS_DIR)
        rows.append(r)
        src = r["baseline_src"] or "无基准"
        bv = f"{r['baseline']:.4f}" if r["baseline"] else "—"
        print(f"n={n:>2}  基准({src}) = {bv}")
        print("   纯GA        " + fmt_result(r, "ga"))
        print("   GA+2-opt    " + fmt_result(r, "ga2"))
        print("   纯GA+后处理2opt cost = " + fmt_cost(r, "post"))
        print("-" * 78)

    # ① 收敛曲线（n1 与 n2 各一张）
    p1 = os.path.join(RESULTS_DIR, f"convergence_n{rows[0]['n']}.png")
    p2 = os.path.join(RESULTS_DIR, f"convergence_n{rows[1]['n']}.png")
    plot_convergence(rows[0]["hist_ga"], rows[0]["hist_ga2"], rows[0]["n"], p1)
    plot_convergence(rows[1]["hist_ga"], rows[1]["hist_ga2"], rows[1]["n"], p2)

    # ② 最优路径图（两个规模的 GA+2-opt 最终回路）
    p3a = os.path.join(RESULTS_DIR, f"best_route_n{rows[0]['n']}.png")
    plot_best_route(rows[0]["cities"], rows[0]["route_ga2"],
                    f"n={rows[0]['n']} GA+2-opt 最优回路", p3a)
    p3 = os.path.join(RESULTS_DIR, f"best_route_n{rows[1]['n']}.png")
    plot_best_route(rows[1]["cities"], rows[1]["route_ga2"],
                    f"n={rows[1]['n']} GA+2-opt 最优回路", p3)

    # ③ 2-opt 改进前后对比图（n2 规模）
    p4 = os.path.join(RESULTS_DIR, f"two_opt_compare_n{rows[1]['n']}.png")
    plot_two_opt_compare(rows[1]["cities"], rows[1]["route_ga"],
                         rows[1]["route_post"], rows[1]["cost_ga"],
                         rows[1]["cost_post"], rows[1]["n"], p4)

    print("已生成图片:")
    for p in (p1, p2, p3a, p3, p4):
        print(f"  {p}")


if __name__ == "__main__":
    main()
