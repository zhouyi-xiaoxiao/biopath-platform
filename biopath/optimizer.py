"""Optimization routines for selecting trap locations."""

from __future__ import annotations

from typing import Callable, Iterable, List, Tuple

from .mapio import GridMap
from .objective import mean_distance_to_traps


Trap = Tuple[int, int]


def greedy_optimize(
    grid_map: GridMap,
    candidates: Iterable[Trap],
    k: int,
    local_improve: bool = False,
    objective_fn: Callable[[GridMap, Iterable[Trap]], float] = mean_distance_to_traps,
) -> Tuple[List[Trap], float]:
    """Greedy selection of traps that minimizes the mean distance objective."""
    if k <= 0:
        return [], objective_fn(grid_map, [])

    candidates_list = list(dict.fromkeys(candidates))
    if k > len(candidates_list):
        raise ValueError("k cannot exceed number of candidates")

    selected: List[Trap] = []
    selected_set = set()

    for _ in range(k):
        best_candidate = None
        best_objective = float("inf")
        for cand in candidates_list:
            if cand in selected_set:
                continue
            objective = objective_fn(grid_map, selected + [cand])
            if objective < best_objective:
                best_objective = objective
                best_candidate = cand
        if best_candidate is None:
            break
        selected.append(best_candidate)
        selected_set.add(best_candidate)

    current_objective = objective_fn(grid_map, selected)

    if local_improve and selected:
        improved = True
        while improved:
            improved = False
            best_swap = None
            best_objective = current_objective
            unselected = [c for c in candidates_list if c not in selected_set]
            for out_trap in list(selected):
                for in_trap in unselected:
                    trial = [t for t in selected if t != out_trap] + [in_trap]
                    objective = objective_fn(grid_map, trial)
                    if objective < best_objective:
                        best_objective = objective
                        best_swap = (out_trap, in_trap)
            if best_swap:
                out_trap, in_trap = best_swap
                selected.remove(out_trap)
                selected.append(in_trap)
                selected_set.remove(out_trap)
                selected_set.add(in_trap)
                current_objective = best_objective
                improved = True

    return selected, current_objective
