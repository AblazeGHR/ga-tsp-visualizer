# -*- coding: utf-8 -*-
"""算子消融实验 + 局部搜索（2-opt/3-opt）对比入口。

不改动 main.py / tsp_ga.py 的原函数，只做参数化实验：
  1) 交叉算子 {OX, PMX, CX} × 变异算子 {swap, inversion, insertion} 的 9 种组合（纯 GA）；
  2) 局部搜索对比：纯 GA 终解的后处理 2-opt / 3-opt，以及进化期 GA+2-opt vs GA+3-opt；
  3) 输出 markdown 表格并生成对比图到 results/。

用法:
    E:/software/miniforge/python.exe main_ablation.py
"""

import argparse
import os
import random
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import tsp_ga
import main as base

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(HERE, "results")

XOVERS = {
    "OX": tsp_ga.order_crossover,
    "PMX": tsp_ga.pmx_crossover,
    "CX": tsp_ga.cx_crossover,
}
MUTS = {
    "swap": tsp_ga.swap_mutation,
    "inversion": tsp_ga.inversion_mutation,
    "insertion": tsp_ga.insertion_mutation,
}


def run_ga(n, seed, pop_size, generations, xover, mutate,
           use_local=None, local_passes=10, elite=2, cx_rate=0.8):
    """参数化 GA：指定交叉/变异函数与局部搜索方式（None / '2opt' / '3opt'）。"""
    random.seed(seed)
    cities = tsp_ga.make_random_instance(n, seed)
    dist = tsp_ga.distance_matrix(cities)

    pop = [random.sample(range(n), n) for _ in range(pop_size)]
    if use_local == "2opt":
        pop = [tsp_ga.two_opt(ind, dist, local_passes) for ind in pop]
    elif use_local == "3opt":
        pop = [tsp_ga.three_opt(ind, dist, local_passes) for ind in pop]

    best_cost, best_route, history = float("inf"), None, []
    for _ in range(generations):
        costs = [tsp_ga.route_cost(ind, dist) for ind in pop]
        ranked = sorted(range(pop_size), key=lambda i: costs[i])
        gen_best = costs[ranked[0]]
        history.append(gen_best)
        if gen_best < best_cost:
            best_cost, best_route = gen_best, list(pop[ranked[0]])

        new_pop = [list(pop[i]) for i in ranked[:elite]]
        while len(new_pop) < pop_size:
            p1 = tsp_ga.tournament_select(pop, costs, 3)
            p2 = tsp_ga.tournament_select(pop, costs, 3)
            child = xover(p1, p2) if random.random() < cx_rate else list(p1)
            child = mutate(child, 0.1)
            if use_local == "2opt":
                child = tsp_ga.two_opt(child, dist, local_passes)
            elif use_local == "3opt":
                child = tsp_ga.three_opt(child, dist, local_passes)
            new_pop.append(child)
        pop = new_pop
    return best_cost, best_route, history, cities, dist


def gap(cost, baseline):
    return (cost - baseline) / baseline * 100 if baseline else None


def plot_gap_bars(labels, values, title, path):
    fig, ax = plt.subplots(figsize=(max(6.5, 0.55 * len(labels)), 4.2))
    x = np.arange(len(labels))
    colors = ["#d62728" if "去重" in l else "#1f77b4" for l in labels]
    bars = ax.bar(x, values, color=colors, width=0.62)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=8)
    ax.set_ylabel("gap (%)")
    ax.set_title(title)
    ax.axhline(0, color="black", lw=0.8)
    for b in bars:
        ax.text(b.get_x() + b.get_width() / 2, b.get_height(),
                f"{b.get_height():.2f}%", ha="center", va="bottom", fontsize=8)
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="GA-TSP 算子消融与局部搜索对比")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--n1", type=int, default=10)
    parser.add_argument("--n2", type=int, default=20)
    parser.add_argument("--pop-size", type=int, default=100)
    parser.add_argument("--generations", type=int, default=300)
    args = parser.parse_args()

    os.makedirs(RESULTS_DIR, exist_ok=True)
    print(f"seed={args.seed}  pop={args.pop_size}  gen={args.generations}")
    print("=" * 90)

    # ---------- 1) 交叉 × 变异 消融（纯 GA） ----------
    for n in (args.n1, args.n2):
        cities = tsp_ga.make_random_instance(n, args.seed)
        dist = tsp_ga.distance_matrix(cities)
        bl, bl_src = base.baseline_for(cities, dist, n)
        print(f"\n## 算子消融 n={n}  基准={bl:.4f}（{bl_src}）")
        print("| 交叉 | 变异 | cost | gap | 耗时 |")
        print("| --- | --- | --- | --- | --- |")
        matrix = {}
        for xname, xfun in XOVERS.items():
            for mname, mfun in MUTS.items():
                t0 = time.time()
                c, *_ = run_ga(n, args.seed, args.pop_size, args.generations, xfun, mfun)
                dt = time.time() - t0
                g = gap(c, bl)
                matrix[(xname, mname)] = g
                print(f"| {xname} | {mname} | {c:.4f} | {g:.2f}% | {dt:.1f}s |")
        if n == args.n2:
            labels = [f"{x}+{m}" for x in XOVERS for m in MUTS]
            vals = [matrix[(x, m)] for x in XOVERS for m in MUTS]
            p = os.path.join(RESULTS_DIR, "ablation_gap.png")
            plot_gap_bars(labels, vals, f"n={n} 交叉×变异 gap（纯 GA）", p)
            print(f"已生成: {p}")

    # ---------- 2) 局部搜索：后处理 2-opt vs 3-opt ----------
    print("\n## 局部搜索对比（n=20，默认算子 OX+swap）")
    print("| 方案 | cost | gap | 耗时 |")
    print("| --- | --- | --- | --- |")
    n = args.n2
    c_ga, r_ga, _, cities, dist = run_ga(
        n, args.seed, args.pop_size, args.generations,
        tsp_ga.order_crossover, tsp_ga.swap_mutation)
    bl, _ = base.baseline_for(cities, dist, n)

    t0 = time.time()
    r2 = tsp_ga.two_opt(r_ga, dist)
    c2 = tsp_ga.route_cost(r2, dist)
    t2 = time.time() - t0
    t0 = time.time()
    r3 = tsp_ga.three_opt(r_ga, dist)
    c3 = tsp_ga.route_cost(r3, dist)
    t3 = time.time() - t0
    print(f"| 纯GA | {c_ga:.4f} | {gap(c_ga, bl):.2f}% | - |")
    print(f"| +后处理2-opt | {c2:.4f} | {gap(c2, bl):.2f}% | {t2:.2f}s |")
    print(f"| +后处理3-opt | {c3:.4f} | {gap(c3, bl):.2f}% | {t3:.2f}s |")

    # 3-opt 对 2-opt 局部最优的进一步改进
    r3b = tsp_ga.three_opt(r2, dist)
    c3b = tsp_ga.route_cost(r3b, dist)
    print(f"| 2-opt结果再3-opt | {c3b:.4f} | {gap(c3b, bl):.2f}% | - |")

    # ---------- 3) 进化期 GA+2-opt vs GA+3-opt（小参数控时） ----------
    print("\n## 进化期局部搜索（pop=50, gen=80，控时公平对比）")
    print("| 方案 | cost | gap | 耗时 |")
    print("| --- | --- | --- | --- |")
    results3 = {}
    for tag, ls in (("GA+2-opt", "2opt"), ("GA+3-opt", "3opt")):
        t0 = time.time()
        c, r, h, _, _ = run_ga(n, args.seed, 50, 80,
                               tsp_ga.order_crossover, tsp_ga.swap_mutation,
                               use_local=ls)
        dt = time.time() - t0
        results3[tag] = gap(c, bl)
        print(f"| {tag} | {c:.4f} | {gap(c, bl):.2f}% | {dt:.1f}s |")

    # 汇总图：各方案 gap
    labels = ["纯GA", "+后处理2-opt", "+后处理3-opt", "GA+2-opt", "GA+3-opt"]
    vals = [gap(c_ga, bl), gap(c2, bl), gap(c3, bl),
            results3["GA+2-opt"], results3["GA+3-opt"]]
    p = os.path.join(RESULTS_DIR, "localsearch_gap.png")
    plot_gap_bars(labels, vals, "n=20 局部搜索方案 gap 对比", p)
    print(f"\n已生成: {p}")


if __name__ == "__main__":
    main()
