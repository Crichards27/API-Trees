# 🌳 API Trees

API Trees is a multiplayer strategy game played entirely through REST API calls.

There is no traditional game client required. Players interact with the game by making HTTP requests to claim teams, manage land, grow trees, harvest fruit, buy resources, and attack other players.

The game is built with **FastAPI, PostgreSQL, Redis, Caddy, Podman, Alembic, and Ansible** and is designed to be deployable on macOS and Raspberry Pi.

---

## 🎮 How the Game Works

Players compete as one of eight teams:

- 🍎 Apple
- 🍊 Orange
- 🍒 Cherry
- 🟣 Plum
- 🍐 Pear
- 🌰 Chestnut
- 🌰 Walnut
- 🍑 Peach

Each team can only be claimed by one player per game.

Before the game begins, players check which teams are available and claim one of them. Claiming a team provides an authentication token used for that team's API requests.

The administrator starts and ends the game.

---

# 🏆 Winning

When the administrator ends the game, each participating team's final score is calculated.

| Resource | Value |
|---|---:|
| Money | 1 point |
| Fruit | 10 points |
| Tree | 100 points |

The team with the highest total score wins.

Multiple teams can win if they finish with the same highest score.

Only teams that were actually claimed participate in the final standings.

---

# 🌱 Starting Resources

Every claimed team begins with:

| Resource | Starting Amount |
|---|---:|
| Money | 300 |
| Seeds | 3 |
| Land Plots | 3 |
| Trees | 1 |

The starting tree occupies one of the team's starting plots.

---

# 🗺️ Land

Each team owns a collection of connected land plots.

Plots are arranged using `row` and `column` coordinates.

A row can contain up to four plots:

```text
[0,0] ─ [0,1] ─ [0,2] ─ [0,3]
                           │
[1,0] ─ [1,1] ─ [1,2] ─ [1,3]
```

Plots maintain connections to neighboring plots.

A team begins with three connected plots and can purchase additional plots from the market.

A plot costs:

```text
100 money
```

Purchased plots are automatically assigned a position in the team's land grid.

---

# 🌳 Trees

A plot can contain a maximum of one tree.

Planting a tree requires:

```text
3 seeds
```

Example:

```http
PUT /plots/{plot_id}/tree
Authorization: Bearer <team-token>
```

Trees can have up to:

```text
10 branches
```

A new branch grows every:

```text
30 seconds
```

Trees can also be deleted by their owner.

```http
DELETE /trees/{tree_id}
```

---

# 🌿 Branches

Branches belong to trees.

Each branch can contain up to:

```text
10 fruit
```

Fruit grows at a random interval between:

```text
2–10 seconds
```

Branches can be inspected individually:

```http
GET /branches/{branch_id}
```

Branches can also be deleted:

```http
DELETE /branches/{branch_id}
```

Deleted branches can regrow while the tree is alive.

---

# 🍒 Fruit

Fruit grows automatically on healthy branches.

Players can harvest fruit from their branches using PATCH requests.

Harvested fruit is stored in the team's inventory.

Fruit can then be converted into other resources.

### Fruit → Money

Each fruit is worth:

```text
10 money
```

### Fruit → Seeds

Each fruit can produce:

```text
5 seeds
```

Players choose how much harvested fruit they want to convert.

---

# 🛒 Market

Players can spend money through the market API.

| Item | Cost |
|---|---:|
| Land Plot | 100 |
| Poison | 50 |
| Molotov | 500 |

Market purchases use authenticated POST requests.

Examples include:

```http
POST /market/plots
POST /market/poison
POST /market/molotov
```

Purchased poison and Molotovs are stored in the team's inventory.

---

# ☠️ Poison

Poison can be used against a plot containing a tree.

```http
POST /attacks/poison
```

Example body:

```json
{
  "plot_id": 97
}
```

Poison:

1. Selects a random branch on the targeted tree.
2. Removes all fruit from that branch.
3. Prevents that branch from growing additional fruit.
4. Spreads to another branch every 10 seconds.

If every remaining branch becomes poisoned or dead, the tree dies.

Players can fight the poison by deleting poisoned branches.

If all poisoned branches are removed before the poison spreads further, the poison attack stops.

Players are allowed to attack their own land.

---

# 🔥 Molotov

Molotovs create a spreading fire across connected plots.

```http
POST /attacks/molotov
```

Example:

```json
{
  "plot_id": 79
}
```

When a Molotov hits a tree:

```text
t = 0 seconds

Target tree → BURNING
```

After 30 seconds:

```text
Original tree → DEAD

Trees on connected plots → BURNING
```

After another 30 seconds:

```text
Previous burning trees → DEAD

Trees on the next connected plots → BURNING
```

The fire therefore travels recursively through the connected plot network in 30-second waves.

The fire system tracks plots it has already visited so that loops in the land network do not cause fire to spread indefinitely.

Players may Molotov their own land.

---

# 📡 API

API Trees is built using FastAPI.

Once deployed, interactive API documentation is available through Swagger:

```text
https://<server>/docs
```

ReDoc documentation is available at:

```text
https://<server>/redoc
```

The raw OpenAPI schema is available at:

```text
https://<server>/openapi.json
```

---

# 🔐 Authentication

After claiming a team, the player receives a team authentication token.

Protected requests use:

```http
Authorization: Bearer <team-token>
```

For example:

```bash
curl -k \
  -H "Authorization: Bearer $CHERRY_TOKEN" \
  https://localhost/me/plots
```

Swagger can also use the bearer token through its **Authorize** interface.

Administrator endpoints use the configured admin token.

---

# 🎬 Game Lifecycle

A typical game follows this sequence:

```text
Players connect
      │
      ▼
GET available teams
      │
      ▼
POST team selection
      │
      ▼
Receive team token
      │
      ▼
Admin starts game
      │
      ▼
POST /admin/start
      │
      ▼
Players grow / harvest / trade / attack
      │
      ▼
Admin ends game
      │
      ▼
POST /admin/end
      │
      ▼
Final scores calculated
      │
      ▼
GET /results
```

A new game can then be created and teams can be claimed again.

---

# 🧱 Architecture

API Trees runs as several containers:

```text
                         HTTPS
                           │
                           ▼
                      ┌─────────┐
                      │  Caddy  │
                      └────┬────┘
                           │
                           ▼
                    ┌─────────────┐
                    │ FastAPI API │
                    └──────┬──────┘
                           │
                ┌──────────┴──────────┐
                │                     │
                ▼                     ▼
          ┌────────────┐        ┌───────────┐
          │ PostgreSQL │        │   Redis   │
          └────────────┘        └─────┬─────┘
                                      │
                                      ▼
                                ┌──────────┐
                                │  Worker  │
                                └──────────┘
```

### FastAPI

Handles:

- Authentication
- Team selection
- Game actions
- Market purchases
- Resource management
- Attack creation
- API documentation

### PostgreSQL

Stores persistent game state including:

- Games
- Teams
- Inventories
- Plots
- Plot connections
- Trees
- Branches
- Attacks
- Game results

### Redis

Provides fast event scheduling for asynchronous game mechanics.

Examples include:

- Branch growth
- Fruit growth
- Poison spreading
- Fire spreading

### Worker

Processes scheduled Redis events independently of the API server.

This allows game events to continue without requiring players to continuously send requests.

### Caddy

Provides the HTTPS reverse proxy in front of FastAPI.

Separate Caddy configurations can be used for macOS development and Raspberry Pi deployment.

---

# 🐳 Containers

The application runs using Podman Compose.

The primary services are:

```text
api
worker
db
redis
caddy
```

Check their status with:

```bash
podman compose ps
```

View API logs:

```bash
podman compose logs -f api
```

View worker events:

```bash
podman compose logs -f worker
```

---

# 🚀 Deployment

Deployment is automated using Ansible.

From the repository root:

```bash
ansible-playbook \
  -i ansible/hosts \
  ansible/deploy.yaml
```

The deployment process:

1. Detects the target platform.
2. Selects the appropriate Caddy configuration.
3. Verifies Podman.
4. Builds the containers.
5. Starts PostgreSQL and Redis.
6. Waits for PostgreSQL.
7. Applies database migrations.
8. Starts the API, worker, and Caddy.
9. Waits for HTTPS.
10. Tests the health endpoint.

A successful deployment exposes:

```text
API:    https://localhost
Health: https://localhost/health
Docs:   https://localhost/docs
```

The exact hostname may differ on a Raspberry Pi deployment.

---

# 🗃️ Database Migrations

API Trees uses Alembic to manage changes to existing databases.

Migration files are stored in:

```text
api/alembic/versions/
```

Migration files **should be committed to Git**.

Deployment automatically applies outstanding migrations:

```bash
alembic upgrade head
```

Migrations allow an existing installation to be upgraded without destroying its persistent game data.

A fresh installation can construct the database as part of the initial deployment process.

---

# 🧪 Development

Clone the repository:

```bash
git clone git@github.com:I-Make-Stuff/API-Trees.git

cd API-Trees
```

Deploy:

```bash
ansible-playbook \
  -i ansible/hosts \
  ansible/deploy.yaml
```

Check containers:

```bash
podman compose ps
```

Test the health endpoint:

```bash
curl -k https://localhost/health
```

Open Swagger:

```text
https://localhost/docs
```

---

# 🧪 Example Game

Check available teams:

```bash
curl -k https://localhost/teams
```

Claim a team using the team-selection endpoint documented in Swagger and save the returned token.

For example:

```bash
export CHERRY_TOKEN="<token>"
```

View your plots:

```bash
curl -sk \
  -H "Authorization: Bearer $CHERRY_TOKEN" \
  https://localhost/me/plots | python3 -m json.tool
```

View your inventory:

```bash
curl -sk \
  -H "Authorization: Bearer $CHERRY_TOKEN" \
  https://localhost/me/inventory | python3 -m json.tool
```

Plant a tree:

```bash
curl -sk \
  -X PUT \
  -H "Authorization: Bearer $CHERRY_TOKEN" \
  https://localhost/plots/79/tree | python3 -m json.tool
```

Inspect a tree:

```bash
curl -sk \
  -H "Authorization: Bearer $CHERRY_TOKEN" \
  https://localhost/trees/33 | python3 -m json.tool
```

Inspect a branch:

```bash
curl -sk \
  -H "Authorization: Bearer $CHERRY_TOKEN" \
  https://localhost/branches/55 | python3 -m json.tool
```

Use poison:

```bash
curl -sk \
  -X POST \
  -H "Authorization: Bearer $CHERRY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"plot_id":97}' \
  https://localhost/attacks/poison | python3 -m json.tool
```

Use a Molotov:

```bash
curl -sk \
  -X POST \
  -H "Authorization: Bearer $CHERRY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"plot_id":79}' \
  https://localhost/attacks/molotov | python3 -m json.tool
```

---

# 📊 Results

Once the administrator ends the game:

```http
POST /admin/end
```

Final standings are available from:

```http
GET /results
```

Example:

```json
{
  "game_id": 3,
  "winners": [
    "cherry"
  ],
  "tie": false,
  "standings": [
    {
      "place": 1,
      "team": "cherry",
      "money": 300,
      "fruit": 16,
      "trees": 0,
      "score": 460
    }
  ]
}
```

---

# 🛠️ Technology

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- Redis
- Alembic
- Caddy
- Podman
- Podman Compose
- Ansible
- Uvicorn

---

# 🔒 Security

Do not commit production credentials or authentication tokens to the repository.

Secrets such as the following should be provided through environment configuration:

```text
ADMIN_TOKEN
DATABASE_URL
REDIS_URL
```

Local `.env` files containing real credentials should be excluded from Git.

---

# 📜 License

Add the project's license here.