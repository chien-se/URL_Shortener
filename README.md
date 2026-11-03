# URL Shortener on AWS EC2

Paste a long URL, get a short link. Visiting the short link redirects to the original URL and counts the click. Links are stored in PostgreSQL.

**Live app:** http://3.133.58.0
**Health check:** http://3.133.58.0/health

## Architecture

![Architecture](docs/architecture.png)

1. The browser sends an HTTP request to the instance's public IP on port 80.
2. The security group allows it.
3. The FastAPI app, run by systemd, handles the request and queries PostgreSQL on `localhost:5432`.
4. The app returns an HTML page or a 302 redirect.

## How it works

| Route | What it does |
|---|---|
| `GET /` | Web page with a form and the list of saved links |
| `POST /shorten` | Saves the URL; the code is the first 7 characters of its SHA-256 hash, so the same URL always gets the same code |
| `GET /{code}` | Adds 1 click and redirects (302) to the original URL, or returns 404 |
| `GET /health` | Runs `SELECT 1`; returns 200 if the database is reachable, 503 if not |

## How I deployed it

1. Created a $1 AWS Budget alert.
2. Launched a t3.micro EC2 instance with Ubuntu 24.04. The security group allows HTTP 80 from anywhere and SSH 22 from my IP only.
3. On the server:

```bash
sudo apt update && sudo apt install -y postgresql python3-venv git

PW=$(openssl rand -hex 16)
sudo -u postgres psql -c "CREATE USER shortener WITH PASSWORD '$PW';"
sudo -u postgres createdb -O shortener shortener
echo "DATABASE_URL=postgresql://shortener:$PW@localhost:5432/shortener" | sudo tee /etc/url-shortener.env > /dev/null
sudo chmod 600 /etc/url-shortener.env

git clone https://github.com/chien-se/URL_Shortener.git url-shortener
cd url-shortener
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

sudo cp url-shortener.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now url-shortener
curl localhost/health
```

## Main choices

| Choice | Picked | Considered | Why |
|---|---|---|---|
| Instance | t3.micro | t2.micro | Both free tier; t3 is newer |
| Linux | Ubuntu 24.04 | Amazon Linux 2023 | Familiar; PostgreSQL installs with one command |
| Database | PostgreSQL on the same EC2 | Amazon RDS | Simplest, one server. Tradeoff: no managed backups |
| Process manager | systemd | Docker | Fewer moving parts; restarts on crash and reboot |
| Traffic | Direct to public IP | Load balancer | Not needed for one server; costs extra |

## Security and cost

1. No secrets in the repo. The database password is in `/etc/url-shortener.env`, readable only by root.
2. Only port 80 is open to everyone. SSH is limited to my IP. PostgreSQL listens on localhost only.
3. The app runs as a regular user, not root. SQL uses parameterized queries, and only `http(s)://` URLs are accepted.
4. One free-tier instance and a $1 budget alert.

## Before real customers

1. HTTPS with a domain and certificate.
2. Amazon RDS with automated backups.
3. A load balancer with two or more instances.
4. Rate limiting on `/shorten`.
5. CloudWatch alarms on `/health`.
6. SSM Session Manager instead of SSH.