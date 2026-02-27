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
        return tiendas_list
    finally:
        db.close()

# --- PÁGINA PRINCIPAL: MENÚ POR TIENDA ---
@app.get("/")
def menu(request: Request, tienda: str = Query(None)):
    db = Session()
    try:
        # Obtener todas las tiendas dinámicamente
        todas_tiendas = obtener_todas_las_tiendas()
        
        # Si no hay tiendas, mostrar página vacía
        if not todas_tiendas:
            return templates.TemplateResponse("menu_vacio.html", {
                "request": request
            })
        
        # Si no se especifica tienda, usar la primera
        if not tienda:
            tienda = todas_tiendas[0]
        
        # Si la tienda actual no existe en la lista, redirigir a la primera
        if tienda not in todas_tiendas:
            tienda = todas_tiendas[0]
        
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

# --- PÁGINA DE GESTIÓN DE DISPOSITIVOS ---
@app.get("/dispositivos")
def dispositivos(request: Request, tienda: str = Query(None)):
    db = Session()
    try:
        # Obtener todas las tiendas dinámicamente
        todas_tiendas = obtener_todas_las_tiendas()
        
        # Si no hay tiendas, mostrar página vacía
        if not todas_tiendas:
            return templates.TemplateResponse("dispositivos_vacio.html", {
                "request": request
            })
        
        # Si no se especifica tienda, usar la primera
        if not tienda:
            tienda = todas_tiendas[0]
        
        # Si la tienda actual no existe en la lista, usar la primera
        if tienda not in todas_tiendas:
            tienda = todas_tiendas[0]
        
        # Filtramos dispositivos según la tienda seleccionada
        dispositivos_tienda = db.query(Dispositivo).filter(Dispositivo.tienda == tienda).all()
        
        # Crear un diccionario con el conteo de dispositivos por tipo
        conteo_por_tipo = {}
        for tipo in TIPOS_DISPONIBLES:
            conteo_por_tipo[tipo] = len([d for d in dispositivos_tienda if d.tipo == tipo])
        
        return templates.TemplateResponse("dispositivos.html", {
            "request": request,
            "tienda_actual": tienda,
            "todas_tiendas": todas_tiendas,
            "tipos": TIPOS_DISPONIBLES,
            "conteo_por_tipo": conteo_por_tipo
        })
    finally:
        db.close()

# --- PÁGINA DE DETALLES DE DISPOSITIVOS POR TIPO ---
@app.get("/dispositivos/tipo")
def dispositivos_por_tipo(request: Request, tipo: str = Query(...), tienda: str = Query(None)):
    db = Session()
    try:
        todas_tiendas = obtener_todas_las_tiendas()
        
        # Si no hay tiendas
        if not todas_tiendas:
            return templates.TemplateResponse("dispositivos_vacio.html", {
                "request": request
            })
        
        # Si no se especifica tienda, usar la primera
        if not tienda:
            tienda = todas_tiendas[0]
        
        # Si la tienda actual no existe, usar la primera
        if tienda not in todas_tiendas:
            tienda = todas_tiendas[0]
        
        # Obtener dispositivos de ese tipo y tienda
        dispositivos = db.query(Dispositivo).filter(
            Dispositivo.tipo == tipo,
            Dispositivo.tienda == tienda
        ).all()
        
        return templates.TemplateResponse("dispositivos_tipo.html", {
            "request": request,
            "tienda_actual": tienda,
            "todas_tiendas": todas_tiendas,
            "tipo": tipo,
            "dispositivos": dispositivos
        })
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

# --- RUTA PARA ACTUALIZAR DISPOSITIVO ---
@app.post("/actualizar_dispositivo/{dispositivo_id}")
def actualizar_dispositivo(
    dispositivo_id: int,
    nombre: str = Form(...),
    ip: str = Form(...),
    tipo: str = Form(...),
    tienda: str = Form(...)
):
    db = Session()
    try:
        dispositivo = db.query(Dispositivo).filter(Dispositivo.id == dispositivo_id).first()
        
        if dispositivo:
            dispositivo.nombre = nombre
            dispositivo.ip = ip
            dispositivo.tipo = tipo
            db.commit()
            print(f"✅ Dispositivo {dispositivo_id} actualizado correctamente")
        
        return RedirectResponse(f"/dispositivos/tipo?tipo={tipo}&tienda={tienda}&actualizado={dispositivo_id}", status_code=303)
    except Exception as e:
        print(f"Error al actualizar dispositivo: {e}")
        return RedirectResponse(f"/dispositivos?tienda={tienda}", status_code=303)
    finally:
        db.close()

# --- RUTA PARA ELIMINAR DISPOSITIVO ---
@app.post("/eliminar_dispositivo/{dispositivo_id}")
def eliminar_dispositivo(dispositivo_id: int, tipo: str = Form(...), tienda: str = Form(...)):
    db = Session()
    try:
        dispositivo = db.query(Dispositivo).filter(Dispositivo.id == dispositivo_id).first()
        
        if dispositivo:
            nombre_dispositivo = dispositivo.nombre
            db.delete(dispositivo)
            db.commit()
            print(f"✅ Dispositivo {nombre_dispositivo} ({dispositivo_id}) eliminado correctamente")
        
        return RedirectResponse(f"/dispositivos/tipo?tipo={tipo}&tienda={tienda}&eliminado={dispositivo_id}", status_code=303)
    except Exception as e:
        print(f"Error al eliminar dispositivo: {e}")
        return RedirectResponse(f"/dispositivos/tipo?tipo={tipo}&tienda={tienda}", status_code=303)
    finally:
        db.close()

# --- RUTA PARA ELIMINAR TIENDA COMPLETA ---
@app.post("/eliminar_tienda")
def eliminar_tienda(tienda: str = Form(...)):
    db = Session()
    try:
        # Eliminar todos los dispositivos de esa tienda
        dispositivos = db.query(Dispositivo).filter(Dispositivo.tienda == tienda).all()
        for dispositivo in dispositivos:
            db.delete(dispositivo)
        
        db.commit()
        print(f"✅ Tienda {tienda} y todos sus dispositivos eliminados")
        
        # Redirigir a la primera tienda disponible
        todas_tiendas = obtener_todas_las_tiendas()
        
        if todas_tiendas:
            tienda_redireccion = todas_tiendas[0]
            return RedirectResponse(f"/?tienda={tienda_redireccion}", status_code=303)
        else:
            # Si no hay más tiendas, redirigir a la página vacía
            return RedirectResponse("/", status_code=303)
    except Exception as e:
        print(f"Error al eliminar tienda: {e}")
        return RedirectResponse(f"/?tienda={tienda}", status_code=303)
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