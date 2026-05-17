"""Live smoke: hits a running server, exercises the full money pipeline."""
import asyncio
import sys

import httpx

BASE = "http://127.0.0.1:8000"


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as c:
        r = await c.post(
            "/api/auth/register",
            json={"email": f"smoke{asyncio.get_event_loop().time()}@t.com",
                  "password": "password123"},
        )
        assert r.status_code == 201, r.text
        aid = (await c.post("/api/agents", json={"name": "Smoke"})).json()["id"]
        run = (
            await c.post(
                "/api/runs",
                json={"agent_id": aid, "goal": "research best gpus under 500"},
            )
        ).json()
        rid = run["id"]
        print("run:", rid)

        for _ in range(80):
            await asyncio.sleep(0.25)
            body = (await c.get(f"/api/runs/{rid}")).json()
            if body["status"] in ("done", "failed", "stopped"):
                break
        print("status:", body["status"], "spend:", body["total_spend"])
        assert body["status"] == "done", body
        assert float(body["total_spend"]) > 0, "no spend recorded"

        pays = (await c.get(f"/api/payments?run_id={rid}")).json()
        settled = [p for p in pays if p["status"] == "settled" and p["tx_hash"]]
        assert settled, "no settled payments with tx hash"
        dash = (await c.get("/api/dashboard")).json()
        assert float(dash["total_spend"]) > 0
        print(f"OK — {len(settled)} settled payments, "
              f"dashboard spend {dash['total_spend']}")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
