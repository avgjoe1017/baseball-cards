# Baseball Card Deal Finder

A CLI tool to surface undervalued graded baseball cards on eBay by comparing live listings against 90-day market comps.

## Features
- Crawl eBay Browse API for listings
- Normalize listings to canonical cards
- Store data in PostgreSQL via SQLAlchemy
- Analyze comps (30/90-day median & velocity)
- Alert when listing ≤ 70% of median price (≥ 3 recent comps)
- CLI output and email notifications
- Dockerized with cron for hourly runs
- Prometheus metrics and Grafana dashboard

## Setup

1. Copy `.env.example` to `.env` and fill in credentials
2. `make setup`
3. `make lint`
4. `make test`

## Usage

- Crawl: `make crawl`
- Analyze: `make analyze`

## Docker

Build: `make docker-build`

## Generating an eBay OAuth Refresh Token

1. Log in to the eBay Developer Portal.
2. Go to **Application Keys → User Tokens → Get a Token from eBay via Your Application**.
3. Select the “Production” environment, grant the `https://api.ebay.com/oauth/api_scope/buy.*` scopes, and complete the web‑flow.
4. Copy the long‑lived *refresh* token (valid two years) into `.env`.
5. The collector exchanges it for short‑lived access tokens automatically.

## CI/CD

GitHub Actions runs lint and tests on push and PR. Docker image builds on `main`.
