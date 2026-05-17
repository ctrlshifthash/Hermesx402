"""Integration: Privy/dev auth, multi-wallet scoping, run + payment logging."""
from __future__ import annotations

import asyncio

import pytest

pytestmark = pytest.mark.asyncio

U1 = {"X-Dev-User": "alice"}
U2 = {"X-Dev-User": "bob"}


async def test_me_upserts_identity(client):
    r = await client.get("/api/auth/me", headers=U1)
    assert r.status_code == 200
    assert r.json()["privy_did"] == "dev:alice"


async def test_auth_config_reports_mode(client):
    r = await client.get("/api/auth/config")
    assert r.status_code == 200 and r.json()["mode"] == "dev"


async def test_fresh_user_auto_provisioned(client):
    # Every account starts ready: a default wallet + $1 credit, no manual
    # connect/link. So resource endpoints work immediately.
    me = await client.get("/api/auth/me", headers=U1)
    assert float(me.json()["credit_remaining"]) == 1.0
    ws = await client.get("/api/wallets", headers=U1)
    assert ws.status_code == 200 and len(ws.json()) >= 1
    assert any(w["is_primary"] for w in ws.json())
    r = await client.get("/api/runs", headers=U1)
    assert r.status_code == 200 and r.json() == []


async def test_wallet_crud_and_default_budget(client):
    # The account already has an auto default wallet; this adds a second.
    w = await client.post(
        "/api/wallets", headers=U1,
        json={"address": "0xabc", "label": "Main"},
    )
    assert w.status_code == 201
    wid = w.json()["id"]
    assert w.json()["is_primary"] is False  # default Trial wallet is primary
    b = await client.get("/api/budget", headers={**U1, "X-Wallet-Id": wid})
    assert b.status_code == 200 and float(b.json()["per_tx_cap"]) == 0.5


async def test_per_user_wallet_isolation(client):
    w1 = (
        await client.post(
            "/api/wallets", headers=U1, json={"address": "0xaaa1", "label": "A"}
        )
    ).json()
    await client.post(
        "/api/wallets", headers=U2, json={"address": "0xbbb2", "label": "B"}
    )
    # bob cannot see alice's wallet
    bob = await client.get("/api/wallets", headers=U2)
    assert all(x["id"] != w1["id"] for x in bob.json())
    # Bob passing Alice's wallet id must NOT leak her data. Self-healing
    # falls back to Bob's own wallet → 200 with only Bob's (empty) data.
    r = await client.get(
        "/api/runs", headers={**U2, "X-Wallet-Id": w1["id"]}
    )
    assert r.status_code == 200 and r.json() == []
    # And it definitely isn't scoped to Alice's wallet.
    r2 = await client.get(
        "/api/dashboard", headers={**U2, "X-Wallet-Id": w1["id"]}
    )
    assert r2.status_code == 200  # Bob's own dashboard, never Alice's


async def test_run_creation_and_payment_logging(client):
    w = (
        await client.post(
            "/api/wallets", headers=U1, json={"address": "0xrun", "label": "R"}
        )
    ).json()
    h = {**U1, "X-Wallet-Id": w["id"]}
    aid = (
        await client.post("/api/agents", headers=h, json={"name": "Scout"})
    ).json()["id"]
    run = (
        await client.post(
            "/api/runs", headers=h,
            json={"agent_id": aid, "goal": "research best gpus under 500"},
        )
    ).json()
    rid = run["id"]
    assert run["wallet_id"] == w["id"]

    for _ in range(60):
        await asyncio.sleep(0.2)
        body = (await client.get(f"/api/runs/{rid}", headers=h)).json()
        if body["status"] in ("done", "failed", "stopped"):
            break
    assert body["status"] == "done", body
    assert float(body["total_spend"]) > 0

    pays = (await client.get(f"/api/payments?run_id={rid}", headers=h)).json()
    assert any(
        p["status"] == "settled"
        and p["facilitator_ref"] == "platform-credit"
        and p["tx_hash"] is None
        for p in pays
    )
    dash = (await client.get("/api/dashboard", headers=h)).json()
    assert float(dash["total_spend"]) > 0 and dash["total_runs"] == 1


async def test_identities_are_isolated(client):
    # Distinct identities never see each other's data, even though every
    # account is auto-provisioned. (In dev mode no header => dev:local.)
    await client.post("/api/agents", headers=U1, json={"name": "Alice Bot"})
    bob_agents = await client.get("/api/agents", headers=U2)
    assert bob_agents.status_code == 200
    assert all(a["name"] != "Alice Bot" for a in bob_agents.json())
