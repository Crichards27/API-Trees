import enum
import uuid

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)

from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ============================================================
# ENUMS
# ============================================================


class GameStatus(str, enum.Enum):
    LOBBY = "lobby"
    ACTIVE = "active"
    FINISHED = "finished"


class TreeStatus(str, enum.Enum):
    HEALTHY = "healthy"
    BURNING = "burning"
    DEAD = "dead"


class BranchStatus(str, enum.Enum):
    HEALTHY = "healthy"
    POISONED = "poisoned"
    DEAD = "dead"


class AttackType(str, enum.Enum):
    POISON = "poison"
    MOLOTOV = "molotov"


class AttackStatus(str, enum.Enum):
    ACTIVE = "active"
    FINISHED = "finished"
    STOPPED = "stopped"


# ============================================================
# GAME
# ============================================================


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(primary_key=True)

    status: Mapped[GameStatus] = mapped_column(
        Enum(GameStatus),
        default=GameStatus.LOBBY,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    teams = relationship(
        "Team",
        back_populates="game",
        cascade="all, delete-orphan",
    )


# ============================================================
# TEAM
# ============================================================


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)

    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    claimed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    token: Mapped[str | None] = mapped_column(
        String(128),
        unique=True,
        nullable=True,
    )

    game = relationship(
        "Game",
        back_populates="teams",
    )

    inventory = relationship(
        "Inventory",
        back_populates="team",
        uselist=False,
        cascade="all, delete-orphan",
    )

    plots = relationship(
        "Plot",
        back_populates="team",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "game_id",
            "name",
            name="uq_game_team_name",
        ),
    )


# ============================================================
# INVENTORY
# ============================================================


class Inventory(Base):
    __tablename__ = "inventories"

    id: Mapped[int] = mapped_column(primary_key=True)

    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    money: Mapped[int] = mapped_column(
        default=300,
        nullable=False,
    )

    fruit: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    seeds: Mapped[int] = mapped_column(
        default=3,
        nullable=False,
    )

    poison: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    molotov: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    team = relationship(
        "Team",
        back_populates="inventory",
    )


# ============================================================
# PLOTS
# ============================================================


class Plot(Base):
    __tablename__ = "plots"

    id: Mapped[int] = mapped_column(primary_key=True)

    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
    )

    row: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    column: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    team: Mapped["Team"] = relationship(
        "Team",
        back_populates="plots",
    )

    tree: Mapped["Tree | None"] = relationship(
        "Tree",
        back_populates="plot",
        uselist=False,
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "row",
            "column",
            name="uq_team_plot_position",
        ),
    )


# ============================================================
# PLOT CONNECTIONS
# ============================================================


class PlotConnection(Base):
    __tablename__ = "plot_connections"

    id: Mapped[int] = mapped_column(primary_key=True)

    plot_a_id: Mapped[int] = mapped_column(
        ForeignKey("plots.id", ondelete="CASCADE"),
        nullable=False,
    )

    plot_b_id: Mapped[int] = mapped_column(
        ForeignKey("plots.id", ondelete="CASCADE"),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "plot_a_id",
            "plot_b_id",
            name="uq_plot_connection",
        ),
    )


# ============================================================
# TREES
# ============================================================


class Tree(Base):
    __tablename__ = "trees"

    id: Mapped[int] = mapped_column(primary_key=True)

    plot_id: Mapped[int] = mapped_column(
        ForeignKey("plots.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    status: Mapped[TreeStatus] = mapped_column(
        Enum(TreeStatus),
        default=TreeStatus.HEALTHY,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    plot: Mapped["Plot"] = relationship(
        "Plot",
        back_populates="tree",
    )

    branches = relationship(
        "Branch",
        back_populates="tree",
        cascade="all, delete-orphan",
    )


# ============================================================
# BRANCHES
# ============================================================


class Branch(Base):
    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(primary_key=True)

    tree_id: Mapped[int] = mapped_column(
        ForeignKey("trees.id", ondelete="CASCADE"),
        nullable=False,
    )

    status: Mapped[BranchStatus] = mapped_column(
        Enum(BranchStatus),
        default=BranchStatus.HEALTHY,
        nullable=False,
    )

    fruit: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    tree = relationship(
        "Tree",
        back_populates="branches",
    )


# ============================================================
# ATTACKS
# ============================================================


class Attack(Base):
    __tablename__ = "attacks"

    id: Mapped[int] = mapped_column(primary_key=True)

    attacker_team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id"),
        nullable=False,
    )

    target_plot_id: Mapped[int] = mapped_column(
        ForeignKey("plots.id"),
        nullable=False,
    )

    attack_type: Mapped[AttackType] = mapped_column(
        Enum(AttackType),
        nullable=False,
    )

    status: Mapped[AttackStatus] = mapped_column(
        Enum(AttackStatus),
        default=AttackStatus.ACTIVE,
        nullable=False,
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )


# ============================================================
# FINAL RESULTS
# ============================================================


class GameResult(Base):
    __tablename__ = "game_results"

    id: Mapped[int] = mapped_column(primary_key=True)

    game_id: Mapped[int] = mapped_column(
        ForeignKey("games.id", ondelete="CASCADE"),
        nullable=False,
    )

    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id"),
        nullable=False,
    )

    money: Mapped[int] = mapped_column(nullable=False)

    fruit: Mapped[int] = mapped_column(nullable=False)

    trees: Mapped[int] = mapped_column(nullable=False)

    score: Mapped[int] = mapped_column(nullable=False)

    place: Mapped[int] = mapped_column(nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "game_id",
            "team_id",
            name="uq_game_result_team",
        ),
    )