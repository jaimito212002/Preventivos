from fastapi import FastAPI, Request, Form, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from db import Session, Dispositivo, Historial
from ping3 import ping
import datetime
import time
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Dispositivo(Base):
    __tablename__ = "dispositivos"
    id = Column(Integer, primary_key=True)
    nombre = Column(String, nullable=False)
    ip = Column(String, nullable=False)
    tipo = Column(String, nullable=False)
    tienda = Column(String, nullable=False)  # ← esta línea es nueva

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Variable temporal para guardar resultados del último ping
ultimo_ping_resultado = {}

# --- PÁGINA PRINCIPAL: MENÚ POR TIENDA ---
@app.get("/")
def menu(request: Request, tienda: str = Query("STO277")):
    db = Session()
    # Filtramos dispositivos según la tienda seleccionada
    dispositivos = db.query(Dispositivo).filter(Dispositivo.tienda == tienda).all()
    db.close()
    
    # Sacamos los tipos disponibles en esa tienda
    tipos = list(set([d.tipo for d in dispositivos]))
    
    # Lista de tiendas disponibles (puede ser dinámica luego)
    todas_tiendas = ['STO277', 'STO283']
    
    return templates.TemplateResponse("menu.html", {
        "request": request,
        "tienda_actual": tienda,
        "todas_tiendas": todas_tiendas,
        "tipos": tipos
    })

# --- RUTA PARA HACER PING POR TIPO Y TIENDA ---
@app.post("/ping_tipo")
def ping_tipo(
    tipo: str = Form(...),
    tienda: str = Form(...)
):
    db = Session()
    dispositivos = db.query(Dispositivo).filter(
        Dispositivo.tipo == tipo,
        Dispositivo.tienda == tienda
    ).all()
    resultados = []

    for d in dispositivos:
        intentos = 0
        exito = False
        while intentos < 3 and not exito:
            intentos += 1
            r = ping(d.ip, timeout=1)
            if r:
                exito = True
            time.sleep(0.2)
        estado = "Online" if exito else "Offline"
        resultados.append({"nombre": d.nombre, "estado": estado, "intentos": intentos})
        db.add(Historial(dispositivo=d.nombre, estado=estado, fecha=datetime.datetime.now()))
        db.commit()
    db.close()

    global ultimo_ping_resultado
    ultimo_ping_resultado = {"tipo": tipo, "tienda": tienda, "resultados": resultados}

    return RedirectResponse("/resultado", status_code=303)

# --- FORMULARIO PARA AÑADIR DISPOSITIVO ---
@app.get("/add_dispositivo")
def add_dispositivo_form(request: Request):
    tipos = ['APs','Switches','Servidores','Servidores Suecia','Impresoras','Cajas','Pinpads/Datáfonos']
    todas_tiendas = ['STO277', 'STO283']
    return templates.TemplateResponse("add_dispositivo.html", {
        "request": request,
        "tipos": tipos,
        "todas_tiendas": todas_tiendas
    })

# --- RUTA POST PARA GUARDAR DISPOSITIVO ---
@app.post("/add_dispositivo")
def add_dispositivo_post(
    nombre: str = Form(...),
    ip: str = Form(...),
    tipo: str = Form(...),
    tienda: str = Form(...),
    nueva_tienda: str = Form(None)
):
    db = Session()
    # Si el usuario indica una nueva tienda, la usamos
    if nueva_tienda:
        tienda = nueva_tienda
    db.add(Dispositivo(nombre=nombre, ip=ip, tipo=tipo, tienda=tienda))
    db.commit()
    db.close()
    return RedirectResponse("/", status_code=303)

# --- PÁGINA DE RESULTADOS DEL ÚLTIMO PING ---
@app.get("/resultado")
def resultado(request: Request):
    global ultimo_ping_resultado
    return templates.TemplateResponse("resultado.html", {
        "request": request,
        "tipo": ultimo_ping_resultado.get("tipo", ""),
        "tienda": ultimo_ping_resultado.get("tienda", ""),
        "resultados": ultimo_ping_resultado.get("resultados", [])
    })