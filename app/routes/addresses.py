"""
Clean IP address management routes.
"""
from fastapi import APIRouter, Request, Depends, HTTPException
from app.security import require_auth
from app import state
from app.database import execute as db_exec
from app.utils import validate_address

router = APIRouter()


@router.get("/api/addresses")
async def list_addresses(_=Depends(require_auth)):
    async with state.addresses_lock:
        return {"addresses": list(state.addresses)}


@router.post("/api/addresses")
async def add_address(request: Request, _=Depends(require_auth)):
    body = await request.json()
    addr = (body.get("address") or "").strip()
    if not addr or not validate_address(addr):
        raise HTTPException(status_code=400, detail="Invalid address")
    async with state.addresses_lock:
        if addr in state.addresses:
            raise HTTPException(status_code=400, detail="Already exists")
        state.addresses.append(addr)
    try:
        await db_exec("INSERT INTO custom_addresses (address) VALUES (?)", "INSERT INTO custom_addresses (address) VALUES ($1)", (addr,))
    except Exception:
        pass
    state.log_event("Clean IP", f"Added {addr}")
    return {"ok": True, "addresses": list(state.addresses)}


@router.post("/api/addresses/batch")
async def batch_add(request: Request, _=Depends(require_auth)):
    body = await request.json()
    addresses = body.get("addresses", [])
    added = 0
    for addr in addresses:
        if not isinstance(addr, str):
            continue
        addr = addr.strip()
        if not addr or not validate_address(addr):
            continue
        async with state.addresses_lock:
            if addr not in state.addresses:
                state.addresses.append(addr)
                try:
                    await db_exec("INSERT INTO custom_addresses (address) VALUES (?)", "INSERT INTO custom_addresses (address) VALUES ($1)", (addr,))
                except Exception:
                    pass
                added += 1
    return {"ok": True, "added": added}


@router.delete("/api/addresses")
async def delete_all(_=Depends(require_auth)):
    async with state.addresses_lock:
        state.addresses.clear()
    await db_exec("DELETE FROM custom_addresses", "DELETE FROM custom_addresses")
    return {"ok": True}


@router.post("/api/addresses/bulk-delete")
async def bulk_delete(request: Request, _=Depends(require_auth)):
    body = await request.json()
    indices = body.get("indices", [])
    removed = 0
    async with state.addresses_lock:
        for idx in sorted({int(i) for i in indices if str(i).lstrip("-").isdigit()}, reverse=True):
            if 0 <= idx < len(state.addresses):
                addr = state.addresses.pop(idx)
                await db_exec(
                    "DELETE FROM custom_addresses WHERE address = ?",
                    "DELETE FROM custom_addresses WHERE address = $1",
                    (addr,),
                )
                removed += 1
    state.log_event("Clean IP", f"Bulk deleted {removed} addresses")
    return {"ok": True, "removed": removed, "addresses": list(state.addresses)}


@router.patch("/api/addresses/{index}")
async def edit_one(index: int, request: Request, _=Depends(require_auth)):
    body = await request.json()
    new_addr = (body.get("address") or "").strip()
    if not new_addr or not validate_address(new_addr):
        raise HTTPException(status_code=400, detail="Invalid address")
    async with state.addresses_lock:
        if not (0 <= index < len(state.addresses)):
            raise HTTPException(status_code=404, detail="Not found")
        if new_addr in state.addresses and state.addresses[index] != new_addr:
            raise HTTPException(status_code=400, detail="Already exists")
        old = state.addresses[index]
        state.addresses[index] = new_addr
        await db_exec(
            "UPDATE custom_addresses SET address = ? WHERE address = ?",
            "UPDATE custom_addresses SET address = $1 WHERE address = $2",
            (new_addr, old),
        )
    state.log_event("Clean IP", f"Edited {old} -> {new_addr}")
    return {"ok": True, "addresses": list(state.addresses)}


@router.delete("/api/addresses/{index}")
async def delete_one(index: int, _=Depends(require_auth)):
    async with state.addresses_lock:
        if 0 <= index < len(state.addresses):
            addr = state.addresses.pop(index)
            await db_exec("DELETE FROM custom_addresses WHERE address = ?", "DELETE FROM custom_addresses WHERE address = $1", (addr,))
        else:
            raise HTTPException(status_code=404, detail="Not found")
    return {"ok": True, "addresses": list(state.addresses)}
