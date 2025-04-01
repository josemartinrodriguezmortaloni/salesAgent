from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from datetime import datetime, timedelta
from .models import (
    SalesReportRequest,
    AgentLogEntry,
    AgentLogResponse,
    AgentLogFilter
)
from ..db.database import (
    get_products,
    get_purchase_types,
    generate_sales_report,
    get_agent_logs,
    save_agent_log
)
from ..db.supabase_client import supabase

app = FastAPI(
    title="Dashboard API",
    description="API para mostrar datos del dashboard y logs de agentes",
    version="1.0.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especifica los orígenes permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Endpoints para datos
@app.get("/products")
async def products():
    """Obtener lista de productos"""
    try:
        products_data = await get_products(None)  # None como contexto temporal
        return {"status": "success", "data": eval(products_data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/payment-types")
async def payment_types():
    """Obtener tipos de pago disponibles"""
    try:
        types_data = await get_purchase_types(None)
        return {"status": "success", "data": eval(types_data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/sales-report")
async def sales_report(request: SalesReportRequest):
    """Generar reporte de ventas para un período específico"""
    try:
        report_data = await generate_sales_report(None, request)
        return {"status": "success", "data": eval(report_data)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Endpoints para logs de agentes
@app.get("/agent-logs", response_model=AgentLogResponse)
async def get_agent_logs_endpoint(
    filter_params: AgentLogFilter = Depends()
):
    """Obtener logs de actividad de los agentes con filtros"""
    try:
        logs_data = await get_agent_logs(None, filter_params)
        return eval(logs_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agent-logs/summary")
async def get_agent_logs_summary():
    """Obtener un resumen de la actividad de los agentes"""
    try:
        yesterday = datetime.now() - timedelta(days=1)
        query = supabase.table("agent_logs")\
            .select("agent_name, activity_type, count(*)")\
            .gte("timestamp", yesterday.isoformat())\
            .group_by("agent_name, activity_type")\
            .execute()

        return {
            "status": "success",
            "data": {
                "last_24h": query.data,
                "agents": list(set(log["agent_name"] for log in query.data)),
                "activity_types": list(set(log["activity_type"] for log in query.data))
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/agent-logs/recent")
async def get_recent_agent_logs(limit: int = Query(10, ge=1, le=50)):
    """Obtener los logs más recientes de los agentes"""
    try:
        logs = supabase.table("agent_logs")\
            .select("*")\
            .order("timestamp", desc=True)\
            .limit(limit)\
            .execute()

        return {
            "status": "success",
            "data": [AgentLogEntry(**log) for log in logs.data]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
