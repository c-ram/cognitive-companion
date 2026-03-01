from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from database import get_db, Sensor

router = APIRouter()

# --- Pydantic Models ---

class SensorCreate(BaseModel):
    id: str # User defined ID (e.g., "recamera-001")
    name: str
    room_name: str
    type: str = "camera"
    enabled: bool = True

class SensorUpdate(BaseModel):
    name: Optional[str] = None
    room_name: Optional[str] = None
    type: Optional[str] = None
    enabled: Optional[bool] = None

# --- Routes ---

@router.get("/sensors")
def get_sensors(db: Session = Depends(get_db)):
    sensors = db.query(Sensor).all()
    return sensors

@router.post("/sensors")
def create_sensor(sensor: SensorCreate, db: Session = Depends(get_db)):
    db_sensor = db.query(Sensor).filter(Sensor.id == sensor.id).first()
    if db_sensor:
        raise HTTPException(status_code=400, detail="Sensor ID already exists")
    
    db_sensor = Sensor(**sensor.dict())
    db.add(db_sensor)
    db.commit()
    db.refresh(db_sensor)
    return db_sensor

@router.put("/sensors/{sensor_id}")
def update_sensor(sensor_id: str, sensor: SensorUpdate, db: Session = Depends(get_db)):
    db_sensor = db.query(Sensor).filter(Sensor.id == sensor_id).first()
    if not db_sensor:
        raise HTTPException(status_code=404, detail="Sensor not found")
    
    update_data = sensor.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_sensor, key, value)
    
    db.commit()
    db.refresh(db_sensor)
    return db_sensor

@router.delete("/sensors/{sensor_id}")
def delete_sensor(sensor_id: str, db: Session = Depends(get_db)):
    db_sensor = db.query(Sensor).filter(Sensor.id == sensor_id).first()
    if not db_sensor:
        raise HTTPException(status_code=404, detail="Sensor not found")
    
    db.delete(db_sensor)
    db.commit()
    return {"status": "deleted"}
