import json
import random
import time

from datetime import datetime, timezone
from redis import Redis
from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.events import EVENT_QUEUE, schedule_event
from app.models import (
    Attack,
    AttackStatus,
    Branch,
    BranchStatus,
    Game,
    GameStatus,
    Tree,
    TreeStatus,
)


redis_client = Redis.from_url(
    settings.redis_url,
    decode_responses=True,
)


def get_active_game(db):
    return db.scalar(
        select(Game)
        .where(Game.status == GameStatus.ACTIVE)
        .order_by(Game.id.desc())
    )


def handle_grow_branch(data: dict):
    tree_id = data["tree_id"]

    db = SessionLocal()

    try:
        game = get_active_game(db)

        if game is None:
            return

        tree = db.get(Tree, tree_id)

        if tree is None:
            return
        
        if tree.status != TreeStatus.HEALTHY:
            return

        # Maximum 10 branches.
        if len(tree.branches) >= 10:
            return

        branch = Branch(
            tree_id=tree.id,
            fruit=0,
        )

        db.add(branch)
        db.commit()
        db.refresh(branch)

        print(
            f"Tree {tree.id}: "
            f"branch {branch.id} grew."
        )

        # Start fruit growth for this branch.
        schedule_event(
            "grow_fruit",
            random.randint(2, 10),
            branch_id=branch.id,
        )

        # Schedule the next branch.
        if len(tree.branches) < 10:
            schedule_event(
                "grow_branch",
                30,
                tree_id=tree.id,
            )

    finally:
        db.close()


def handle_grow_fruit(data: dict):
    branch_id = data["branch_id"]

    db = SessionLocal()

    try:
        game = get_active_game(db)

        if game is None:
            return

        branch = db.get(
            Branch,
            branch_id,
        )

        if branch is None:
            return
        if branch.status == BranchStatus.POISONED:
            return
        if branch.tree.status != TreeStatus.HEALTHY:
            return
        # Poison handling will eventually go here.

        if branch.fruit >= 10:
            return

        branch.fruit += 1

        db.commit()

        print(
            f"Branch {branch.id}: "
            f"fruit grew ({branch.fruit}/10)."
        )

        if branch.fruit < 10:
            schedule_event(
                "grow_fruit",
                random.randint(2, 10),
                branch_id=branch.id,
            )

    finally:
        db.close()


def process_event(event: dict):
    event_type = event.get("type")
    data = event.get("data", {})

    if event_type == "grow_branch":
        handle_grow_branch(data)

    elif event_type == "grow_fruit":
        handle_grow_fruit(data)
    
    elif event_type == "spread_poison":
        handle_spread_poison(data)
    
    elif event_type == "spread_fire":
        handle_spread_fire(data)

    else:
        print(
            f"Unknown event type: {event_type}"
        )


def run_worker():

    print("API Trees worker started.")

    while True:

        now = time.time()

        events = redis_client.zrangebyscore(
            EVENT_QUEUE,
            min=0,
            max=now,
            start=0,
            num=10,
        )

        if not events:
            time.sleep(0.25)
            continue

        for raw_event in events:

            # Remove first so we don't execute it repeatedly.
            removed = redis_client.zrem(
                EVENT_QUEUE,
                raw_event,
            )

            if not removed:
                continue

            try:
                event = json.loads(raw_event)

                process_event(event)

            except Exception as exc:
                print(
                    f"Worker event failed: {exc}"
                )


def handle_spread_poison(data: dict):
    attack_id = data["attack_id"]
    tree_id = data["tree_id"]

    db = SessionLocal()

    try:
        game = get_active_game(db)

        if game is None:
            return

        attack = db.get(
            Attack,
            attack_id,
        )

        if (
            attack is None
            or attack.status != AttackStatus.ACTIVE
        ):
            return

        tree = db.get(
            Tree,
            tree_id,
        )

        if tree is None:
            attack.status = AttackStatus.STOPPED
            db.commit()
            return

        branches = list(
            tree.branches
        )

        poisoned = [
            branch
            for branch in branches
            if branch.status == BranchStatus.POISONED
        ]

        healthy = [
            branch
            for branch in branches
            if branch.status == BranchStatus.HEALTHY
        ]

        # All poisoned branches were cut off.
        # The poison has been stopped.
        if not poisoned:
            attack.status = AttackStatus.STOPPED
            attack.finished_at = datetime.now(
                timezone.utc
            )

            db.commit()

            print(
                f"Poison attack {attack.id} stopped."
            )

            return

        # No healthy branches remain.
        # Every remaining branch is poisoned,
        # therefore the tree dies.
        if not healthy:
            tree.status = TreeStatus.DEAD

            attack.status = AttackStatus.FINISHED
            attack.finished_at = datetime.now(
                timezone.utc
            )

            db.commit()

            print(
                f"Tree {tree.id} died from poison."
            )

            return

        branch = random.choice(
            healthy
        )

        branch.status = BranchStatus.POISONED
        branch.fruit = 0

        db.commit()

        print(
            f"Tree {tree.id}: "
            f"poison spread to branch {branch.id}."
        )

        # Check again in another 10 seconds.
        schedule_event(
            "spread_poison",
            10,
            attack_id=attack.id,
            tree_id=tree.id,
        )

    finally:
        db.close()


def handle_spread_fire(data: dict):
    attack_id = data["attack_id"]

    frontier = set(
        data.get("frontier_plot_ids", [])
    )

    visited = set(
        data.get("visited_plot_ids", [])
    )

    db = SessionLocal()

    try:
        game = get_active_game(db)

        if game is None:
            return

        attack = db.get(
            Attack,
            attack_id,
        )

        if (
            attack is None
            or attack.status != AttackStatus.ACTIVE
        ):
            return

        next_frontier = set()

        # --------------------------------------------------
        # 1. Trees that have been burning for the previous
        #    30 seconds now die.
        # --------------------------------------------------

        for plot_id in frontier:

            plot = db.get(
                Plot,
                plot_id,
            )

            if plot is None:
                continue

            tree = plot.tree

            if (
                tree is not None
                and tree.status == TreeStatus.BURNING
            ):
                tree.status = TreeStatus.DEAD

                for branch in tree.branches:
                    branch.status = BranchStatus.DEAD
                    branch.fruit = 0

                print(
                    f"Molotov attack {attack.id}: "
                    f"tree {tree.id} on plot "
                    f"{plot.id} burned down."
                )

            # ----------------------------------------------
            # 2. Find plots connected to this burning plot.
            # ----------------------------------------------

            connected_ids = get_connected_plot_ids(
                db,
                plot_id,
            )

            for connected_id in connected_ids:

                if connected_id not in visited:
                    next_frontier.add(
                        connected_id
                    )

        # --------------------------------------------------
        # 3. Newly reached trees catch fire.
        #
        # Empty plots are still part of the frontier so
        # fire can travel through them.
        # --------------------------------------------------

        for plot_id in next_frontier:

            plot = db.get(
                Plot,
                plot_id,
            )

            if plot is None:
                continue

            tree = plot.tree

            if (
                tree is not None
                and tree.status != TreeStatus.DEAD
            ):
                tree.status = TreeStatus.BURNING

                print(
                    f"Molotov attack {attack.id}: "
                    f"tree {tree.id} on plot "
                    f"{plot.id} caught fire."
                )

        visited.update(next_frontier)

        db.commit()

        # --------------------------------------------------
        # 4. No more plots means the fire is finished.
        # --------------------------------------------------

        if not next_frontier:

            attack.status = AttackStatus.FINISHED
            attack.finished_at = datetime.now(
                timezone.utc
            )

            db.commit()

            print(
                f"Molotov attack {attack.id} "
                f"finished spreading."
            )

            return

        # --------------------------------------------------
        # 5. Wait another 30 seconds.
        #
        # Current burning trees will die.
        # Their neighbors will catch fire.
        # --------------------------------------------------

        schedule_event(
            "spread_fire",
            30,
            attack_id=attack.id,
            frontier_plot_ids=list(
                next_frontier
            ),
            visited_plot_ids=list(
                visited
            ),
        )

    finally:
        db.close()


if __name__ == "__main__":
    run_worker()
