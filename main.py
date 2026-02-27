from fastapi import FastAPI, Request, Form, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from db import Session, Dispositivo, Historial
from ping3 import ping
import datetime
import time
import os

app = FastAPI()

# Crear directorios si no existen
os.makedirs("templates", exist_ok=True)
os.makedirs("static", exist_ok=True)

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Variable temporal para guardar resultados del último ping
ultimo_ping_resultado = {}

# Lista ESTÁTICA de tipos/categorías disponibles
TIPOS_DISPONIBLES = [
    'APs',
    'Switches',
    'Servidores',
    'Servidores Suecia',
    'Impresoras',
    'Cajas',
    'Pinpads/Datáfonos'
]

# --- FUNCIÓN PARA OBTENER TODAS LAS TIENDAS DINÁMICAMENTE ---
def obtener_todas_las_tiendas():
    """Obtiene todas las tiendas que existen en la base de datos"""
    db = Session()
    try:
        tiendas = db.query(Dispositivo.tienda).distinct().all()
        tiendas_list = sorted(list(set([t[0] for t in tiendas])))
        return tiendas_list if tiendas_list else ['STO277', 'STO283']
    finally:
        db.close()

# --- PÁGINA PRINCIPAL: MENÚ POR TIENDA ---
@app.get("/")
def menu(request: Request, tienda: str = Query("STO277")):
    db = Session()
    try:
        # Obtener todas las tiendas dinámicamente
        todas_tiendas = obtener_todas_las_tiendas()
        
        # Si la tienda actual no existe en la lista, añadirla
        if tienda not in todas_tiendas:
            todas_tiendas.append(tienda)
            todas_tiendas.sort()
        
        # Filtramos dispositivos según la tienda seleccionada
        dispositivos_tienda = db.query(Dispositivo).filter(Dispositivo.tienda == tienda).all()
        
        # Crear un diccionario con el conteo de dispositivos por tipo
        conteo_por_tipo = {}
        for tipo in TIPOS_DISPONIBLES:
            conteo_por_tipo[tipo] = len([d for d in dispositivos_tienda if d.tipo == tipo])
        
        return templates.TemplateResponse("menu.html", {
            "request": request,
            "tienda_actual": tienda,
            "todas_tiendas": todas_tiendas,
            "tipos": TIPOS_DISPONIBLES,
            "conteo_por_tipo": conteo_por_tipo
        })
    finally:
        db.close()

# --- RUTA PARA HACER PING POR TIPO Y TIENDA ---
@app.post("/ping_tipo")
def ping_tipo(
    tipo: str = Form(...),
    tienda: str = Form(...)
):
    db = Session()
    try:
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
                try:
                    r = ping(d.ip, timeout=2)
                    if r and r is not False:
                        exito = True
                except Exception as e:
                    print(f"Error pinging {d.ip}: {e}")
                time.sleep(0.1)
            
            estado = "🟢 Online" if exito else "🔴 Offline"
            resultados.append({
                "nombre": d.nombre, 
                "ip": d.ip,
                "estado": estado, 
                "intentos": intentos
            })
            
            # Guardar en historial
            historial = Historial(
                dispositivo=d.nombre, 
                estado=estado, 
                fecha=datetime.datetime.now()
            )
            db.add(historial)
        
        db.commit()

        global ultimo_ping_resultado
        ultimo_ping_resultado = {
            "tipo": tipo, 
            "tienda": tienda, 
            "resultados": resultados
        }

        return RedirectResponse("/resultado", status_code=303)
    finally:
        db.close()

# --- FORMULARIO PARA AÑADIR DISPOSITIVO ---
@app.get("/add_dispositivo")
def add_dispositivo_form(request: Request):
    todas_tiendas = obtener_todas_las_tiendas()
    return templates.TemplateResponse("add_dispositivo.html", {
        "request": request,
        "tipos": TIPOS_DISPONIBLES,
        "todas_tiendas": todas_tiendas
    })

# --- RUTA POST PARA GUARDAR DISPOSITIVO ---
@app.post("/add_dispositivo")
def add_dispositivo_post(
    nombre: str = Form(...),
    ip: str = Form(...),
    tipo: str = Form(...),
    tipo_tienda: str = Form(...),
    tienda: str = Form(default=""),
    nueva_tienda: str = Form(default="")
):
    db = Session()
    try:
        # Determinar cuál tienda usar
        tienda_final = ""
        
        if tipo_tienda == "existente" and tienda:
            tienda_final = tienda
        elif tipo_tienda == "nueva" and nueva_tienda:
            tienda_final = nueva_tienda.strip().upper()
        
        # Validación
        if not tienda_final:
            todas_tiendas = obtener_todas_las_tiendas()
            return templates.TemplateResponse("add_dispositivo.html", {
                "request": request,
                "tipos": TIPOS_DISPONIBLES,
                "todas_tiendas": todas_tiendas,
                "error": "Por favor, selecciona o crea una tienda válida"
            }, status_code=400)
        
        nuevo_dispositivo = Dispositivo(
            nombre=nombre, 
            ip=ip, 
            tipo=tipo, 
            tienda=tienda_final
        )
        db.add(nuevo_dispositivo)
        db.commit()
        
        return RedirectResponse("/?tienda=" + tienda_final, status_code=303)
    except Exception as e:
        print(f"Error al añadir dispositivo: {e}")
        todas_tiendas = obtener_todas_las_tiendas()
        return templates.TemplateResponse("add_dispositivo.html", {
            "request": request,
            "tipos": TIPOS_DISPONIBLES,
            "todas_tiendas": todas_tiendas,
            "error": f"Error al guardar: {str(e)}"
        }, status_code=400)
    finally:
        db.close()

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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)