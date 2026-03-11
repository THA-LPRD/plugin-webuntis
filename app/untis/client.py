import base64
import random
import time
from datetime import date
from typing import Any

import httpx
from loguru import logger

from app.untis.models import UntisElementWrapper, UntisPeriod

_logger = logger.bind(classname="UntisClient")


class UntisClient:
    def __init__(self, school: str, url: str) -> None:
        self._school = school
        self._base_url = url.rstrip("/")
        self._session_id: str | None = None
        self._http: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "UntisClient":
        self._http = httpx.AsyncClient(
            timeout=15.0,
            headers={
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        await self.login()
        return self

    async def __aexit__(self, *_: object) -> None:
        try:
            await self.logout()
        finally:
            if self._http:
                await self._http.aclose()

    async def login(self) -> None:
        """Two-step anonymous login via jsonrpc_intern.do with fixed OTP 100170."""
        _logger.debug(f"Authenticating anonymously for school={self._school}")
        assert self._http is not None

        identity = str(random.randint(1, 999999))

        step1 = await self._http.post(
            f"{self._base_url}/WebUntis/jsonrpc_intern.do",
            params={"m": "getAppSharedSecret", "school": self._school, "v": "i3.5"},
            json={
                "id": identity,
                "method": "getAppSharedSecret",
                "params": [{"userName": "#anonymous#", "password": ""}],
                "jsonrpc": "2.0",
            },
        )

        ts = int(time.time() * 1000)
        step2 = await self._http.post(
            f"{self._base_url}/WebUntis/jsonrpc_intern.do",
            params={"m": "getUserData2017", "school": self._school, "v": "i2.2"},
            json={
                "id": identity,
                "method": "getUserData2017",
                "params": [
                    {"auth": {"clientTime": ts, "user": "#anonymous#", "otp": 100170}}
                ],
                "jsonrpc": "2.0",
            },
        )

        self._session_id = step2.cookies.get("JSESSIONID") or step1.cookies.get(
            "JSESSIONID"
        )
        if not self._session_id:
            raise RuntimeError(
                "Anonymous login failed: no JSESSIONID cookie in response"
            )

        _logger.debug("Anonymous session established")

    async def logout(self) -> None:
        if not self._session_id:
            return
        await self._jsonrpc("logout", {})
        self._session_id = None

    async def get_rooms(self) -> list[dict[str, Any]]:
        return await self._jsonrpc("getRooms", {})

    async def get_timetable_for_week(
        self, element_id: int, ref_date: date
    ) -> list[UntisPeriod]:
        assert self._http is not None

        resp = await self._http.get(
            f"{self._base_url}/WebUntis/api/public/timetable/weekly/data",
            params={
                "elementType": 4,
                "elementId": element_id,
                "date": ref_date.strftime("%Y-%m-%d"),
                "formatId": 1,
            },
            headers=self._cookie_headers(),
        )
        resp.raise_for_status()

        try:
            result_data = resp.json()["data"]["result"]["data"]
        except (KeyError, TypeError) as exc:
            raise RuntimeError(
                f"Unexpected timetable response structure: {exc}"
            ) from exc

        elements_by_id: dict[int, dict[str, Any]] = {
            e["id"]: e for e in result_data.get("elements", [])
        }
        raw_periods: list[dict[str, Any]] = result_data.get("elementPeriods", {}).get(
            str(element_id), []
        )

        return [_parse_period(p, elements_by_id) for p in raw_periods]

    async def _jsonrpc(self, method: str, params: dict[str, Any]) -> Any:
        assert self._http is not None

        resp = await self._http.post(
            f"{self._base_url}/WebUntis/jsonrpc.do",
            params={"school": self._school},
            json={
                "id": str(random.randint(1, 999999)),
                "method": method,
                "params": params,
                "jsonrpc": "2.0",
            },
            headers=self._cookie_headers(),
        )
        resp.raise_for_status()

        body = resp.json()
        if "error" in body:
            err = body["error"]
            msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            raise RuntimeError(f"WebUntis API error in '{method}': {msg}")

        return body["result"]

    def _cookie_headers(self) -> dict[str, str]:
        encoded_school = base64.b64encode(self._school.encode()).decode()
        return {
            "Cookie": f"JSESSIONID={self._session_id}; schoolname=_{encoded_school}"
        }


def _parse_period(
    period: dict[str, Any], elements_by_id: dict[int, dict[str, Any]]
) -> UntisPeriod:
    refs = period.get("elements", [])

    def collect(type_id: int) -> list[dict[str, Any]]:
        return [
            {"element": elements_by_id[r["id"]]}
            for r in refs
            if r.get("type") == type_id and r.get("id") in elements_by_id
        ]

    period["subjects"] = collect(3)
    period["teachers"] = collect(2)
    period["classes"] = collect(1)
    period["rooms"] = collect(4)

    return UntisPeriod.model_validate(period)