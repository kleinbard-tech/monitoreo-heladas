import csv
import os
import threading
import time
import math
from datetime import datetime, timezone, timedelta

import requests
from flask import Flask, jsonify, send_from_directory, send_file


# ============================================================
# CONFIGURACIÓN
# ============================================================

THINGSPEAK_CHANNEL_ID = "3506543"

# Se recomienda colocar esta clave como variable de entorno
# en Render:
#
# THINGSPEAK_READ_API_KEY=xxxxxxxxxxxxxxxx
#
THINGSPEAK_READ_API_KEY = os.environ.get(
    "THINGSPEAK_READ_API_KEY",
    ""
)

# Por ahora consultamos ThingSpeak cada 20 segundos.
# Más adelante lo podemos cambiar a 5 minutos sincronizados.
INTERVALO_THINGSPEAK = 20


# ============================================================
# FLASK
# ============================================================

app = Flask(__name__)


# ============================================================
# VARIABLES GLOBALES
# ============================================================

datos_actuales = {}

historial = []

ultimo_entry_id_procesado = None


# ============================================================
# PUNTO DE ROCÍO
# ============================================================

def calcular_punto_rocio(temperatura, humedad):

    a = 17.27
    b = 237.7

    if humedad <= 0:
        return None

    if humedad > 100:
        humedad = 100

    alpha = (
        (a * temperatura) / (b + temperatura)
        + math.log(humedad / 100.0)
    )

    punto_rocio = (b * alpha) / (a - alpha)

    return round(punto_rocio, 2)


# ============================================================
# ESTADO DE HELADA
# ============================================================

def determinar_estado(temperatura, punto_rocio):

    if punto_rocio is None:
        return "NORMAL"

    # Helada
    if temperatura <= 0:
        return "HELADA"

    # Riesgo de helada
    diferencia = temperatura - punto_rocio

    if temperatura <= 3 and diferencia <= 2:
        return "RIESGO"

    return "NORMAL"


# ============================================================
# GUARDAR REGISTRO EN CSV
# ============================================================

def guardar_en_csv(registro):

    try:

        fecha = registro.get("fechaHora")

        if not fecha:
            return

        nodo = registro.get("nodo", 1)

        # ----------------------------------------------------
        # Extraer año y mes
        #
        # Ejemplo:
        # 2026-09-24 15:20:04
        #
        # queda:
        # 2026-09
        # ----------------------------------------------------

        anio_mes = fecha[:7]

        # ----------------------------------------------------
        # Archivo:
        #
        # historial_NODO1_2026-09.csv
        # historial_NODO2_2026-09.csv
        # ----------------------------------------------------

        nombre_archivo = (
            f"registros/historial_NODO{nodo}_{anio_mes}.csv"
        )

        os.makedirs("registros", exist_ok=True)

        archivo_nuevo = not os.path.exists(nombre_archivo)

        with open(
            nombre_archivo,
            "a",
            newline="",
            encoding="utf-8-sig"
        ) as archivo:

            escritor = csv.writer(
                archivo,
                delimiter=";"
            )

            # ------------------------------------------------
            # Encabezado
            # ------------------------------------------------

            if archivo_nuevo:

                escritor.writerow([
                    "FechaHora",
                    "Nodo",
                    "Medicion",
                    "TemperaturaDS",
                    "TemperaturaDHT",
                    "Humedad",
                    "PuntoRocio",
                    "Estado"
                ])

            # ------------------------------------------------
            # Conversión numérica
            #
            # Python:
            # 10.947923
            #
            # CSV:
            # 10,95
            # ------------------------------------------------

            def numero_csv(valor):

                if valor is None:
                    return ""

                try:

                    return (
                        f"{float(valor):.2f}"
                        .replace(".", ",")
                    )

                except:

                    return ""

            # ------------------------------------------------
            # Escribir registro
            # ------------------------------------------------

            escritor.writerow([

                fecha,

                nodo,

                registro.get(
                    "medicion",
                    ""
                ),

                numero_csv(
                    registro.get(
                        "temperaturaDS"
                    )
                ),

                numero_csv(
                    registro.get(
                        "temperaturaDHT"
                    )
                ),

                numero_csv(
                    registro.get(
                        "humedad"
                    )
                ),

                numero_csv(
                    registro.get(
                        "puntoRocio"
                    )
                ),

                registro.get(
                    "estado",
                    ""
                )
            ])

        print(
            f"[CSV] Registro guardado: "
            f"{nombre_archivo}"
        )

    except Exception as e:

        print(
            f"[CSV] Error guardando registro: {e}"
        )


# ============================================================
# CORREGIR CSV EXISTENTES
# ============================================================

def corregir_csv_existentes():

    carpeta = "registros"

    if not os.path.exists(carpeta):
        return

    for nombre_archivo in os.listdir(carpeta):

        if not nombre_archivo.endswith(".csv"):
            continue

        ruta = os.path.join(
            carpeta,
            nombre_archivo
        )

        try:

            with open(
                ruta,
                "r",
                encoding="utf-8-sig",
                newline=""
            ) as archivo:

                lector = csv.reader(
                    archivo,
                    delimiter=","
                )

                filas = list(lector)

            if not filas:
                continue

            # Si ya utiliza ; no tocarlo
            with open(
                ruta,
                "r",
                encoding="utf-8-sig"
            ) as archivo:

                contenido = archivo.read()

            if ";" in contenido:
                continue

            # Reescribir usando ;
            with open(
                ruta,
                "w",
                encoding="utf-8-sig",
                newline=""
            ) as archivo:

                escritor = csv.writer(
                    archivo,
                    delimiter=";"
                )

                for fila in filas:
                    escritor.writerow(fila)

            print(
                f"[CSV] Convertido: {nombre_archivo}"
            )

        except Exception as e:

            print(
                f"[CSV] Error convirtiendo "
                f"{nombre_archivo}: {e}"
            )


# ============================================================
# CONVERTIR FECHA THINGSPEAK A HORA ARGENTINA
# ============================================================

def convertir_fecha_argentina(fecha_utc):

    try:

        fecha = datetime.fromisoformat(
            fecha_utc.replace(
                "Z",
                "+00:00"
            )
        )

        zona_argentina = timezone(
            timedelta(hours=-3)
        )

        fecha_argentina = fecha.astimezone(
            zona_argentina
        )

        return fecha_argentina.strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    except Exception as e:

        print(
            f"[FECHA] Error convirtiendo fecha: {e}"
        )

        return fecha_utc


# ============================================================
# PROCESAR REGISTRO THINGSPEAK
# ============================================================

def procesar_registro_thingspeak(feed):

    try:

        # ----------------------------------------------------
        # ThingSpeak actualmente contiene solamente Nodo 1
        # ----------------------------------------------------

        nodo = 1

        # ----------------------------------------------------
        # Medición
        # ----------------------------------------------------

        medicion = None

        if feed.get("field1") is not None:

            # Actualmente field1 de ThingSpeak es
            # temperatura DS18B20.
            #
            # La medición original del nodo no está
            # almacenada en los fields actuales.
            #
            # Se conserva entry_id como referencia.
            pass

        # ----------------------------------------------------
        # Temperatura DS18B20
        # ----------------------------------------------------

        temperatura_ds = None

        if feed.get("field1") not in [
            None,
            ""
        ]:

            temperatura_ds = float(
                feed["field1"]
            )

        # ----------------------------------------------------
        # Temperatura DHT22
        # ----------------------------------------------------

        temperatura_dht = None

        if feed.get("field2") not in [
            None,
            ""
        ]:

            temperatura_dht = float(
                feed["field2"]
            )

        # ----------------------------------------------------
        # Humedad DHT22
        # ----------------------------------------------------

        humedad = None

        if feed.get("field3") not in [
            None,
            ""
        ]:

            humedad = float(
                feed["field3"]
            )

        # ----------------------------------------------------
        # Punto de rocío
        #
        # Usamos temperatura DHT22 + humedad DHT22
        # ----------------------------------------------------

        punto_rocio = None

        if (
            temperatura_dht is not None
            and humedad is not None
        ):

            punto_rocio = calcular_punto_rocio(
                temperatura_dht,
                humedad
            )

        # ----------------------------------------------------
        # Estado
        #
        # Se utiliza DS18B20 como temperatura principal.
        # ----------------------------------------------------

        temperatura_para_estado = temperatura_ds

        if temperatura_para_estado is None:
            temperatura_para_estado = temperatura_dht

        estado = determinar_estado(
            temperatura_para_estado,
            punto_rocio
        )

        # ----------------------------------------------------
        # Fecha
        # ----------------------------------------------------

        fecha_utc = feed.get(
            "created_at",
            ""
        )

        fecha_hora = convertir_fecha_argentina(
            fecha_utc
        )

        # ----------------------------------------------------
        # Medición
        # ----------------------------------------------------
        #
        # Como actualmente ThingSpeak no está guardando
        # el contador "medicion", utilizamos entry_id.
        #
        # Esto nos permite identificar cada registro.
        # ----------------------------------------------------

        medicion = feed.get(
            "entry_id",
            ""
        )

        # ----------------------------------------------------
        # Crear registro
        # ----------------------------------------------------

        registro = {

            "nodo": nodo,

            "medicion": medicion,

            "temperaturaDS": (
                round(
                    temperatura_ds,
                    2
                )
                if temperatura_ds is not None
                else None
            ),

            "temperaturaDHT": (
                round(
                    temperatura_dht,
                    2
                )
                if temperatura_dht is not None
                else None
            ),

            "humedad": (
                round(
                    humedad,
                    2
                )
                if humedad is not None
                else None
            ),

            "puntoRocio": punto_rocio,

            "estado": estado,

            "fechaHora": fecha_hora,

            "conectado": True
        }

        return registro

    except Exception as e:

        print(
            f"[THINGSPEAK] Error procesando "
            f"registro: {e}"
        )

        return None


# ============================================================
# CONSULTAR THINGSPEAK
# ============================================================

def consultar_thingspeak():

    global ultimo_entry_id_procesado

    print(
        "[THINGSPEAK] Hilo de consulta iniciado"
    )

    while True:

        try:

            # ------------------------------------------------
            # URL de lectura
            # ------------------------------------------------

            url = (
                "https://api.thingspeak.com/"
                f"channels/{THINGSPEAK_CHANNEL_ID}/feeds.json"
            )

            parametros = {
                "results": 1
            }

            # ------------------------------------------------
            # Si existe API KEY, agregarla
            # ------------------------------------------------

            if THINGSPEAK_READ_API_KEY:

                parametros[
                    "api_key"
                ] = THINGSPEAK_READ_API_KEY

            # ------------------------------------------------
            # Consulta
            # ------------------------------------------------

            respuesta = requests.get(
                url,
                params=parametros,
                timeout=10
            )

            respuesta.raise_for_status()

            datos = respuesta.json()

            feeds = datos.get(
                "feeds",
                []
            )

            # ------------------------------------------------
            # Verificar que haya datos
            # ------------------------------------------------

            if not feeds:

                print(
                    "[THINGSPEAK] "
                    "No hay registros"
                )

            else:

                feed = feeds[-1]

                entry_id = feed.get(
                    "entry_id"
                )

                # ------------------------------------------------
                # Evitar procesar dos veces el mismo registro
                # ------------------------------------------------

                if entry_id != ultimo_entry_id_procesado:

                    registro = procesar_registro_thingspeak(
                        feed
                    )

                    if registro is not None:

                        # ----------------------------------------
                        # Actualizar datos actuales
                        # ----------------------------------------

                        datos_actuales[
                            str(
                                registro["nodo"]
                            )
                        ] = registro

                        # ----------------------------------------
                        # Agregar al historial
                        # ----------------------------------------

                        historial.append(
                            registro
                        )

                        # ----------------------------------------
                        # Mantener historial limitado
                        # ----------------------------------------

                        if len(historial) > 1000:

                            del historial[
                                :-1000
                            ]

                        # ----------------------------------------
                        # Guardar CSV
                        # ----------------------------------------

                        guardar_en_csv(
                            registro
                        )

                        # ----------------------------------------
                        # Actualizar entry ID
                        # ----------------------------------------

                        ultimo_entry_id_procesado = (
                            entry_id
                        )

                        print(
                            "[THINGSPEAK] "
                            f"Nuevo registro: "
                            f"Nodo {registro['nodo']} | "
                            f"Medición {registro['medicion']} | "
                            f"DS18B20 "
                            f"{registro['temperaturaDS']} °C | "
                            f"DHT22 "
                            f"{registro['temperaturaDHT']} °C | "
                            f"HR "
                            f"{registro['humedad']} % | "
                            f"Rocío "
                            f"{registro['puntoRocio']} °C | "
                            f"Estado "
                            f"{registro['estado']}"
                        )

                else:

                    print(
                        "[THINGSPEAK] "
                        "Sin registro nuevo"
                    )

        except requests.exceptions.RequestException as e:

            print(
                f"[THINGSPEAK] Error de conexión: {e}"
            )

        except Exception as e:

            print(
                f"[THINGSPEAK] Error: {e}"
            )

        # ----------------------------------------------------
        # Esperar antes de consultar nuevamente
        # ----------------------------------------------------

        time.sleep(
            INTERVALO_THINGSPEAK
        )


# ============================================================
# RUTA PRINCIPAL
# ============================================================

@app.route("/")
def inicio():

    return send_from_directory(
        ".",
        "index.html"
    )


# ============================================================
# CSS
# ============================================================

@app.route("/estilo.css")
def estilo_css():

    return send_from_directory(
        ".",
        "estilo.css"
    )


# ============================================================
# JAVASCRIPT
# ============================================================

@app.route("/script.js")
def script_js():

    return send_from_directory(
        ".",
        "script.js"
    )


# ============================================================
# LOGO UNCO
# ============================================================

@app.route("/logo-unco.jpg")
def logo_unco():

    return send_from_directory(
        ".",
        "logo-unco.jpg"
    )


# ============================================================
# LOGO FAIN
# ============================================================

@app.route("/logo-fain.jpg")
def logo_fain():

    return send_from_directory(
        ".",
        "logo-fain.jpg"
    )


# ============================================================
# LOGO FACA
# ============================================================

@app.route("/logo-faca.jpg")
def logo_faca():

    return send_from_directory(
        ".",
        "logo-faca.jpg"
    )


# ============================================================
# DATOS ACTUALES
# ============================================================

@app.route("/datos")
def obtener_datos():

    return jsonify(
        datos_actuales
    )


# ============================================================
# HISTORIAL
# ============================================================

@app.route("/historial")
def obtener_historial():

    return jsonify(
        historial
    )


# ============================================================
# LISTA DE ARCHIVOS CSV
# ============================================================

@app.route("/api/archivos-csv")
def listar_archivos_csv():

    carpeta = "registros"

    archivos = []

    if os.path.exists(carpeta):

        for nombre in os.listdir(carpeta):

            if nombre.lower().endswith(".csv"):

                ruta = os.path.join(
                    carpeta,
                    nombre
                )

                if os.path.isfile(ruta):

                    archivos.append(
                        nombre
                    )

    # Ordenar alfabéticamente
    archivos.sort()

    return jsonify(
        archivos
    )


# ============================================================
# DESCARGAR CSV
# ============================================================

@app.route("/descargar/<nombre_archivo>")
def descargar_csv(nombre_archivo):

    carpeta = "registros"

    ruta = os.path.join(
        carpeta,
        nombre_archivo
    )

    # Evitar rutas externas
    if not os.path.isfile(ruta):

        return (
            "Archivo no encontrado",
            404
        )

    return send_file(
        ruta,
        as_attachment=True,
        download_name=nombre_archivo,
        mimetype="text/csv"
    )


# ============================================================
# API DE MEDICIÓN
# ============================================================

@app.route("/api/medicion")
def api_medicion():

    if not datos_actuales:

        return jsonify({
            "conectado": False,
            "mensaje": "Sin datos"
        })

    # Nodo 1 actualmente
    if "1" in datos_actuales:

        return jsonify(
            datos_actuales["1"]
        )

    return jsonify({
        "conectado": False,
        "mensaje": "Nodo no disponible"
    })


# ============================================================
# INICIO
# ============================================================

if __name__ == "__main__":

    print(
        "=============================================="
    )

    print(
        "       MONITOREO DE HELADAS"
    )

    print(
        "       ThingSpeak + Flask"
    )

    print(
        "=============================================="
    )

    # --------------------------------------------------------
    # Crear carpeta de registros
    # --------------------------------------------------------

    os.makedirs(
        "registros",
        exist_ok=True
    )

    # --------------------------------------------------------
    # Intentar corregir CSV antiguos
    # --------------------------------------------------------

    corregir_csv_existentes()

    # --------------------------------------------------------
    # Iniciar hilo de ThingSpeak
    # --------------------------------------------------------

    hilo_thingspeak = threading.Thread(
        target=consultar_thingspeak,
        daemon=True
    )

    hilo_thingspeak.start()

    # --------------------------------------------------------
    # Iniciar Flask
    # --------------------------------------------------------

    puerto = int(
        os.environ.get(
            "PORT",
            5000
        )
    )

    app.run(
        host="0.0.0.0",
        port=puerto,
        debug=False
    )
