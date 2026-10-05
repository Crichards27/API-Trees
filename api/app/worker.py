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
            attack.finished_at = datetime.now(
                timezone.utc
            )
            db.commit()
            return

        if tree.status == TreeStatus.DEAD:
            attack.status = AttackStatus.FINISHED
            attack.finished_at = datetime.now(
                timezone.utc
            )
            db.commit()
            return

        living_branches = [
            branch
            for branch in tree.branches
            if branch.status != BranchStatus.DEAD
        ]

        if not living_branches:
            tree.status = TreeStatus.DEAD

            attack.status = AttackStatus.FINISHED
            attack.finished_at = datetime.now(
                timezone.utc
            )

            db.commit()

            print(
                f"Tree {tree.id} died from fire."
            )

            return

        branch = random.choice(
            living_branches
        )

        branch.status = BranchStatus.DEAD
        branch.fruit = 0

        db.commit()

        print(
            f"Tree {tree.id}: "
            f"fire killed branch {branch.id}."
        )

        remaining_branches = [
            branch
            for branch in tree.branches
            if branch.status != BranchStatus.DEAD
        ]

        if not remaining_branches:
            tree.status = TreeStatus.DEAD

            attack.status = AttackStatus.FINISHED
            attack.finished_at = datetime.now(
                timezone.utc
            )

            db.commit()

            print(
                f"Tree {tree.id} died from fire."
            )

            return

        schedule_event(
            "spread_fire",
            10,
            attack_id=attack.id,
            tree_id=tree.id,
        )

    finally:
        db.close()


if __name__ == "__main__":
    run_worker()
