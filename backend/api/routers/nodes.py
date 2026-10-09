from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import Node

router = APIRouter(prefix="/api/v1/nodes", tags=["Nodes"])

@router.get("")
def list_nodes(db: Session = Depends(get_db)):
    nodes = db.query(Node).all()
    return nodes

@router.get("/{node_id}/readings")
def get_node_readings(node_id: str, limit: int = 50, db: Session = Depends(get_db)):
    node = db.query(Node).filter(Node.node_id == node_id).first()
    if not node:
        return {"error": "Node not found"}
    return node.readings[-limit:]
