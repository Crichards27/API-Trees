from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Plot, PlotConnection


PLOTS_PER_ROW = 4


def get_connected_plot_ids(
    db: Session,
    plot_id: int,
) -> list[int]:

    connections = db.scalars(
        select(PlotConnection).where(
            or_(
                PlotConnection.plot_a_id == plot_id,
                PlotConnection.plot_b_id == plot_id,
            )
        )
    ).all()

    connected_ids = []

    for connection in connections:
        if connection.plot_a_id == plot_id:
            connected_ids.append(connection.plot_b_id)
        else:
            connected_ids.append(connection.plot_a_id)

    return sorted(connected_ids)


def get_next_plot_position(
    db: Session,
    team_id: int,
) -> tuple[int, int]:
    """
    Return the next available position in the team's plot grid.

    Four plots are allowed per row.

    Positions:
        1 -> row 0, column 0
        2 -> row 0, column 1
        3 -> row 0, column 2
        4 -> row 0, column 3
        5 -> row 1, column 0
        etc.
    """

    plots = db.scalars(
        select(Plot)
        .where(Plot.team_id == team_id)
        .order_by(
            Plot.row,
            Plot.column,
        )
    ).all()

    occupied = {
        (plot.row, plot.column)
        for plot in plots
    }

    position = 0

    while True:
        row = position // PLOTS_PER_ROW
        column = position % PLOTS_PER_ROW

        if (row, column) not in occupied:
            return row, column

        position += 1


def connect_plot_to_neighbors(
    db: Session,
    plot: Plot,
) -> list[int]:
    """
    Connect a plot to its immediate grid neighbors.

    Valid neighbors:
        left
        right
        above
        below

    Diagonal plots are NOT connected.
    """

    neighbor_positions = [
        (plot.row, plot.column - 1),
        (plot.row, plot.column + 1),
        (plot.row - 1, plot.column),
        (plot.row + 1, plot.column),
    ]

    created_connections = []

    for row, column in neighbor_positions:

        # Ignore positions outside the grid.
        if row < 0 or column < 0:
            continue

        neighbor = db.scalar(
            select(Plot).where(
                Plot.team_id == plot.team_id,
                Plot.row == row,
                Plot.column == column,
            )
        )

        if neighbor is None:
            continue

        plot_a_id = min(plot.id, neighbor.id)
        plot_b_id = max(plot.id, neighbor.id)

        existing = db.scalar(
            select(PlotConnection).where(
                PlotConnection.plot_a_id == plot_a_id,
                PlotConnection.plot_b_id == plot_b_id,
            )
        )

        if existing is not None:
            continue

        connection = PlotConnection(
            plot_a_id=plot_a_id,
            plot_b_id=plot_b_id,
        )

        db.add(connection)

        created_connections.append(
            neighbor.id
        )

    return sorted(created_connections)