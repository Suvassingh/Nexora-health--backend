
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())  
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import appointments
from app.routes import doctors
from app.routes.calls import router as calls_router
from server.turn_token_server import router as turn_router
from app.routes.health_records import router as health_records_router
from app.routes.prescriptions import router as prescriptions_router 
from app.routes.referrals import router as referrals_router 
from app.routes import facilities
from app.routes import healthposts

app = FastAPI(title="HealthPost API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    appointments.router,
    prefix="/api/appointments",
    tags=["Appointments"]
)
app.include_router(doctors.router, prefix="/api/doctors", tags=["doctors"])

app.include_router(calls_router, prefix="/api", tags=["calls"])
app.include_router(turn_router, prefix="/api", tags=["turn"])
app.include_router(health_records_router, prefix="/api/health-records", tags=["health-records"])
app.include_router(prescriptions_router, prefix="/api/prescriptions", tags=["prescriptions"])
app.include_router(
referrals_router,
prefix="/api/referrals",
tags=["referrals"]
)
app.include_router(facilities.router, prefix="/api/facilities", tags=["facilities"])
app.include_router(healthposts.router, prefix="/api/healthposts", tags=["healthposts"])

